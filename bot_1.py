import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
import datetime
from telegram import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove 
from bs4 import BeautifulSoup
import re
import json
import asyncio
import nest_asyncio
import xml.etree.ElementTree as ET
from telegram import BotCommand, MenuButtonCommands
from dotenv import load_dotenv
import os
from flask import Flask
import threading
from supabase_utils import save_user_info, save_location, save_action

# Глобальный кэш
cached_data = None
avg_sell_global = None
last_updated = None
ADMIN_CHAT_ID = None
CACHE_TTL = datetime.timedelta(hours=1)  # Время жизни кэша: 1 час

def try_convert_amount(message: str, data: dict) -> str | None:
    """Пробует распознать сообщение '<amount> <currency1> [currency2]' и умножить на курс ЦБ РФ."""    
    try:
        print("[DEBUG] start try_convert_amount, message:", message)
        parts = message.strip().lower().split()

        if len(parts) == 1:
            amount_str = parts[0]
            currency_from = "KZT"
            currency_to = None
        elif len(parts) == 2:
            amount_str, currency_from = parts
            currency_to = None
        elif len(parts) == 3:
            amount_str, currency_from, currency_to = parts
        else:
            return None

        # Пробуем преобразовать сумму
        try:
            amount = float(amount_str.replace(",", "."))
        except Exception as e:
            print("[DEBUG] invalid amount:", amount_str, "error:", e)
            return None

        currency_from = currency_from.upper()
        currency_to = currency_to.upper() if currency_to else None

        # --- НОВАЯ ЛОГИКА: цепочка через рубли ---
        if currency_to:
            # проверка, что обе валюты есть
            if currency_from not in data.get("Valute", {}) and currency_from not in ("KZT", "KZ", "КЗ", "ЛЯ"):
                return f"❌ Валюта '{currency_from}' не найдена."
            if currency_to not in data.get("Valute", {}) and currency_to not in ("KZT", "KZ", "КЗ", "ЛЯ"):
                return f"❌ Валюта '{currency_to}' не найдена."

            # шаг 1: currency_from -> RUB
            if currency_from in ("KZT", "KZ", "КЗ", "ЛЯ"):
                kzt_valute = data["Valute"]["KZT"]
                rate_from = kzt_valute["Value"] / kzt_valute["Nominal"]
                amount_rub = amount * rate_from
            else:
                valute_from = data["Valute"][currency_from]
                rate_from = valute_from["Value"] / valute_from["Nominal"]
                amount_rub = amount * rate_from

            # шаг 2: RUB -> currency_to
            if currency_to in ("KZT", "KZ", "КЗ", "ЛЯ"):
                kzt_valute = data["Valute"]["KZT"]
                rate_to = kzt_valute["Value"] / kzt_valute["Nominal"]
                amount_final = amount_rub / rate_to
            else:
                valute_to = data["Valute"][currency_to]
                rate_to = valute_to["Value"] / valute_to["Nominal"]
                amount_final = amount_rub / rate_to

            return f"💱 {amount} {currency_from} → {amount_final:.2f} {currency_to} (через {amount_rub:.2f} RUB)"

        # --- Старая логика (2 аргумента) ---
        if currency_from in ("KZT", "KZ", "КЗ", "ЛЯ"):
            try:
                local_rate = get_kursz_data()
            except Exception as e:
                print("[DEBUG] get_kursz_data() raised:", e)
                local_rate = None

															 
            try:
                local_rate_num = float(local_rate) if local_rate is not None else None
            except Exception as e:
                print("[DEBUG] float(local_rate) failed:", repr(local_rate), "err:", e)
                local_rate_num = None

																													 
            kzt_valute = data.get("Valute", {}).get("KZT")
            lines = []

            if kzt_valute:
                nominal = kzt_valute["Nominal"]
                value = kzt_valute["Value"]
                rub_per_1_kzt = value / nominal
                kzt_per_1_rub = 1 / rub_per_1_kzt

                converted_cb = round(amount / kzt_per_1_rub, 2)
																													
                lines.append(f"По курсу ЦБ РФ: {converted_cb} ({kzt_per_1_rub:.4f})")
            else:
                print("[DEBUG] data has no Valute['KZT']")

																													 
            if local_rate_num is not None and local_rate_num > 0:
                converted_local = round(amount / local_rate_num, 2)
															 
                lines.append(f"По обмен курсу: {converted_local} ({local_rate_num:.4f})")                
                diff = converted_cb - converted_local
                lines.append(f"Разница: <b>{diff:.2f}</b>\n")
                
            if lines:
																											  
                return "\n".join(lines)
							 
            else:
                return "❌ Нет данных по KZT в данных ЦБ РФ и локальный курс недоступен."

																
        valute = data["Valute"][currency_from]
        nominal = valute["Nominal"]
        value = valute["Value"]
        rate = value / nominal
        converted = round(amount * rate, 2)
        return f"💰 {amount} {currency_from} × {rate:.4f} = {converted} RUB"

    except Exception as e:
        print("[ERROR] Exception in try_convert_amount:", e)
        return None

#тут только рубли
def get_nbrk_rub():
    url = "https://nationalbank.kz/rss/rates_all.xml"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()

        root = ET.fromstring(response.content)

        for item in root.findall(".//item"):
            title = item.find("title").text
            if title == "RUB":
                rate = item.find("description").text
                date = item.find("pubDate").text 
                return {
                        "rate": float(rate.replace(",", ".")),
                        "date": date
                }
        return None
    except Exception as e:
        print(f"Ошибка при получении курса из НБРК: {e}")
        return None        


def get_nbrk_course():
    """
    Получает курсы валют с сайта НБРК и возвращает их в виде словаря, 
    похожего на формат daily_json.js от ЦБ РФ.
    """
    url = "https://nationalbank.kz/rss/rates_all.xml"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        root = ET.fromstring(response.content)

        valutes = {}

        for item in root.findall(".//item"):
            code = item.find("title").text.strip().upper()
            rate_str = item.find("description").text.strip()
            nominal_str = item.find("quant").text.strip() if item.find("quant") is not None else "1"

            try:
                rate = float(rate_str.replace(",", "."))
                nominal = int(nominal_str)
            except ValueError:
                continue

            valutes[code] = {
                "CharCode": code,
                "Nominal": nominal,
                "Value": rate
            }

        return {
            "Date": root.find(".//pubDate").text if root.find(".//pubDate") is not None else None,
            "Valute": valutes
        }

    except Exception as e:
        print(f"Ошибка при получении курса из НБРК: {e}")
        return None

def get_kurskz_rub_buy_sell_avg():
    kurs_list = get_kurskz_rub_buy_sell_all()
    
    if not kurs_list:
        return None

    total_buy = sum(k["buy"] for k in kurs_list)
    total_sell = sum(k["sell"] for k in kurs_list)
    count = len(kurs_list)

    avg_buy = total_buy / count if count else 0
    avg_sell = total_sell / count if count else 0

    return {
        "avg_buy": avg_buy,
        "avg_sell": avg_sell,
        "count": count
    }

def get_kurskz_rub_buy_sell_avg_almaty():
    kurs_list = get_kurskz_rub_buy_sell_almaty()
    
    if not kurs_list:
        return None

    total_buy = sum(k["buy"] for k in kurs_list)
    total_sell = sum(k["sell"] for k in kurs_list)
    count = len(kurs_list)

    avg_buy = total_buy / count if count else 0
    avg_sell = total_sell / count if count else 0

    return {
        "avg_buy": avg_buy,
        "avg_sell": avg_sell,
        "count": count
    }


def get_kurskz_rub_buy_sell_all():
    url = "https://kurs.kz/site/index?city=uralsk"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        match = re.search(r"var punkts = (\[.*?\]);", response.text, re.DOTALL)
        if not match:
            return []

        punkts_json = match.group(1)
        punkts = json.loads(punkts_json)

        result = []
        for punkt in punkts:
            rub = punkt.get("data", {}).get("RUB")
            if rub and isinstance(rub, list) and len(rub) >= 2 and rub[0] > 0 and rub[1] > 0:
                result.append({
                    "name": punkt.get("name", "—"),
                    "address": punkt.get("mainaddress", "—"),
                    "buy": rub[0],
                    "sell": rub[1],
                })

        return result

    except Exception as e:
        print("Ошибка при получении данных с kurs.kz:", e)
        return []
        
def get_kurskz_rub_buy_sell_almaty():
    url = "https://kurs.kz/site/index?city=almaty"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        match = re.search(r"var punkts = (\[.*?\]);", response.text, re.DOTALL)
        if not match:
            return []

        punkts = json.loads(match.group(1))

        result = []
        for punkt in punkts:
            name = punkt.get("name", "")
            rub = punkt.get("data", {}).get("RUB")
            name_lc = name.lower()
            if (
                ("exchange" in name_lc or name_lc == "миг 1")
                and rub and isinstance(rub, list)
                and len(rub) >= 2 and rub[0] > 0 and rub[1] > 0
            ):
                result.append({
                    "name": name,
                    "address": punkt.get("mainaddress", "—"),
                    "buy": rub[0],
                    "sell": rub[1],
                })
        return result

    except Exception as e:
        print("Ошибка при получении данных с kurs.kz:", e)
        return []
        
def get_flag(code):
    """Возвращает эмодзи-флаг по коду страны (например 'US' → 🇺🇸)."""
    if code == "EU":
        return "🇪🇺"  # Евросоюз не имеет официального флага-эмодзи, это стандарт
    return ''.join([chr(ord(c) + 127397) for c in code.upper()])
    
    
# 💵 Курс доллара
async def usd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_currency_data()
    if data:
        rate = data["Valute"]["USD"]["Value"]
        flag = get_flag("US")
        await update.message.reply_text(f"{flag} Курс доллара по данным ЦБ РФ: 1 USD = {rate:.2f} RUB")
    else:
        await update.message.reply_text("Не удалось получить данные от ЦБ.")

# 💶 Курс евро
async def eur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_currency_data()
    if data:
        rate = data["Valute"]["EUR"]["Value"]
        flag = get_flag("EU")
        await update.message.reply_text(f"{flag} Курс евро по данным ЦБ РФ: 1 EUR = {rate:.2f} RUB")
    else:
        await update.message.reply_text("Не удалось получить данные от ЦБ.")
        
# 💶 Курс тенге
async def kzt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_currency_data()
    if data:
        valute = data["Valute"]["KZT"]
        nominal = valute["Nominal"]
        value = valute["Value"]

        rub_per_1_kzt = value / nominal
        kzt_per_1_rub = 1 / rub_per_1_kzt
        flag = get_flag("KZ")

        await update.message.reply_text(
            f"{flag} Курс тенге:\n"
            f"1 KZT = {rub_per_1_kzt:.4f} RUB\n"
            f"1 RUB = {kzt_per_1_rub:.2f} KZT"
        )
    else:
        await update.message.reply_text("Не удалось получить данные от ЦБ.")

        
# 📊 Общее — ЦБ РФ основные валюты
async def course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_currency_data()
    if data:
        usd_rate = data["Valute"]["USD"]["Value"]
        eur_rate = data["Valute"]["EUR"]["Value"]       
        
        by_rate = data["Valute"]["BYN"]["Value"]
        kzt_rate = 1 / (data["Valute"]["KZT"]["Value"] / data["Valute"]["KZT"]["Nominal"])
        som_rate = 1 / (data["Valute"]["KGS"]["Value"] / data["Valute"]["KGS"]["Nominal"])
        date_rf = last_updated.strftime('%d.%m.%Y')
        msg = (
            f"Курсы валют по данным ЦБ РФ на {date_rf}:\n"
            f"💵 1 RUB = {kzt_rate:.2f} KZT\n"
            f"💵 1 RUB = {som_rate:.2f} KGS\n"
            f"💵 1 BYN = {by_rate:.2f} RUB\n"
            f"💵 1 USD = {usd_rate:.2f} RUB\n"
            f"💶 1 EUR = {eur_rate:.2f} RUB"
        )
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("Не удалось получить данные от ЦБ РФ.")


# 📊 Общее — НБ КЗ основные валюты
async def coursekz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_nbrk_course()
    if data:
        usd_rate = data["Valute"]["USD"]["Value"]
        eur_rate = data["Valute"]["EUR"]["Value"]       
        
        by_rate = data["Valute"]["BYN"]["Value"]
        rub_rate = data["Valute"]["RUB"]["Value"] 
        som_rate = data["Valute"]["KGS"]["Value"] 
        date_rk = data["Date"]
        msg = (
            f"Курсы валют по данным НБ КЗ на {date_rk}:\n"
            f"💵 1 RUB = {rub_rate:.2f} KZT\n"
            f"💵 1 KGS = {som_rate:.2f} KZT\n"
            f"💵 1 BYN = {by_rate:.2f} KZT\n"
            f"💵 1 USD = {usd_rate:.2f} KZT\n"
            f"💶 1 EUR = {eur_rate:.2f} KZT"
        )
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("Не удалось получить данные от НБ РК.")


# 📊 Общее от ЦБ
async def course_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dataRF = get_currency_data()
    dataKZ = get_nbrk_rub()

    if dataRF and dataKZ:
        rub_rf = dataRF["Valute"]["KZT"]["Value"] / dataRF["Valute"]["KZT"]["Nominal"]
        rub_kz = dataKZ["rate"]
        date_kz = dataKZ["date"]
        date_rf = last_updated.strftime('%d.%m.%Y')

        msg = (
            f"📅 Дата: {date_kz}\n\n"
            f"🇷🇺 ЦБ РФ: 1 RUB = {1/rub_rf:.2f} KZT\n"
            f"🇰🇿 НБ РК: 1 RUB = {rub_kz:.2f} KZT"
        )
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("Не удалось получить данные от ЦБ или НБРК.")
        
# Приветствие
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ADMIN_CHAT_ID
    
    print("🔔 Команда /start получена")
    user = update.effective_user
    save_user_info(user)
    save_action(user.id, "/start")
    
    ADMIN_CHAT_ID = update.effective_chat.id

    keyboard = [
        [KeyboardButton("📊 Курсы RUB/KZT"), KeyboardButton("Обменники Уральска"), KeyboardButton("Обменники Алматы")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await asyncio.sleep(0.5)  # небольшая задержка
    await update.message.reply_text(
        "Привет! Я бот с курсами RUB/KZT.\nНажми на кнопку или используй команду.",
        reply_markup=reply_markup
    )

async def rub_kzt_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await course_cb(update, context)
    await kurskz(update, context)
    await kurskz_almaty(update, context)  
    
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message.text
    save_action(user.id, f"{message}")       
    text = message.lower()

    if "обменники уральска" in text:
        await kurskz_oral(update, context)
    elif "обменники алматы" in text:
        await kurskz_detail_almaty(update, context)
    elif "📊 курсы rub/kzt" in text:
        await rub_kzt_all(update, context)
    else:
        data = get_currency_data()
        if data:
            result = try_convert_amount(update.message.text, data)
            if result:
                await update.message.reply_text(result, parse_mode="HTML")
                return
        await update.message.reply_text("Не понимаю. Используй кнопки или команды.")

async def kurskz_oral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kurs_list = get_kurskz_rub_buy_sell_all()
    if kurs_list:
         messages = []
         for kurs in kurs_list:
             messages.append(
                 f"🏦 <b>{kurs['name']}</b>\n"
                 f"📍 {kurs['address']}\n"
                 f"🔻 Покупка: {kurs['buy']} ₸\n"
                 f"🔺 Продажа: {kurs['sell']} ₸\n"
                 f"— — —\n"
             )
         full_message = "\n".join(messages)
         await update.message.reply_text(full_message, parse_mode="HTML")
    else:
         await update.message.reply_text("Не удалось получить данные об обменниках.")
         
async def kurskz_detail_almaty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kurs_list = get_kurskz_rub_buy_sell_almaty()

    if not kurs_list:
        await update.message.reply_text("Нет подходящих данных.")
        return

    MAX_LENGTH = 4000
    result_text = ""

    for k in kurs_list:
        entry = (
            f"🏦 {k['name']}\n"
            f"📍 {k['address']}\n"
            f"{k['buy']} / {k['sell']}\n"
            f"— — —\n"
        )
        if len(result_text) + len(entry) > MAX_LENGTH:
            break
        result_text += entry

    await update.message.reply_text(result_text)
         
async def kurskz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global avg_sell_global
    data = get_kurskz_rub_buy_sell_avg()
    if not data:
        await update.message.reply_text("Не удалось получить данные об обменниках.")
        return

    # Обновляем глобальную переменную
    try:
        avg_sell_global = float(data['avg_sell'])
        print(f"[DEBUG] kurskz handler assigned avg_sell_global = {avg_sell_global}")
    except Exception as e:
        print("[ERROR] kurskz: cannot convert avg_sell:", e)
        avg_sell_global = None

    message = (
        f"📊 <b>Средний курс RUB по {data['count']} обменникам Уральска:</b>\n"
        f"💰 Покупка: <b>{data['avg_buy']:.2f}</b> ₸\n"
        f"💵 Продажа: <b>{data['avg_sell']:.2f}</b> ₸"
    )
    await update.message.reply_text(message, parse_mode="HTML")

async def kurskz_almaty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_kurskz_rub_buy_sell_avg_almaty()
    if not data:
        await update.message.reply_text("Не удалось получить данные об обменниках.")
        return

    message = (
        f"📊 <b>Средний курс RUB по {data['count']} обменникам Алматы:</b>\n"
        f"💰 Покупка: <b>{data['avg_buy']:.2f}</b> ₸\n"
        f"💵 Продажа: <b>{data['avg_sell']:.2f}</b> ₸"
    )
    await update.message.reply_text(message, parse_mode="HTML")
    
async def rub_nbrk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_nbrk_rub()
    if data:
        await update.message.reply_text(
        f"🇷🇺 Курс рубля на {data['date']} по НБРК:\n"
        f"1 RUB = {data['rate']:.2f} ₸\n"
    )
    else:
        await update.message.reply_text("Не удалось получить курс рубля от НБРК.")    

# 🔄 Получение всех курсов один раз
def get_currency_data():
    return cached_data

def get_kursz_data():
    return avg_sell_global

# 🔄 Функция обновления кеша курсов
def update_currency_data(context: ContextTypes.DEFAULT_TYPE):
    global cached_data, last_updated, avg_sell_global, ADMIN_CHAT_ID
    try:
        response = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=10)
        response.raise_for_status()
        cached_data = response.json()
        last_updated = datetime.datetime.now()
        print(f"🔁 Данные обновлены из сети: {last_updated}")
        
        if ADMIN_CHAT_ID:
            context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"📢 Курс изменился! {last_updated}"
            )
    except Exception as e:
        print("❌ Ошибка при обновлении курса:", e)

    # Пытаемся обновить средний курс обменников (kurs.kz)
    try:
        kurs_data = get_kurskz_rub_buy_sell_avg()  # корректное имя
        if kurs_data and "avg_sell" in kurs_data:
            try:
                avg_sell_global = float(kurs_data['avg_sell'])  # исправлено: kurs_data
                print(f"🔁 avg_sell_global обновлён: {avg_sell_global}")
            except Exception as e:
                print("❌ Не удалось привести avg_sell к float:", e)
                avg_sell_global = None
        else:
            print("⚠️ Не удалось получить avg_sell из kurs.kz (пустой ответ).")
    except Exception as e:
        print("❌ Ошибка при получении данных с kurs.kz:", e)
        
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Данные ЦБ РФ с www.cbr-xml-daily.ru \n"
        f"Данные НБ РК с nationalbank.kz \n"
        f"И данные обменников kurs.kz\n\n"
        f"Введите сумму и код валюты (или два кода ) — и вы получите пересчёт по официальному курсу ЦБ РФ (перевод через рубли)\n"
        f"Примеры: '1000 KZT KGS' или '1000 BYN' или '1000'\n"
        f"Третий параметр по умолчанию RUB, второй по умолчанию KZT\n\n"
        f"💬 Обратная связь — @SlavaBochkarev\n")
    #await update.message.reply_text(ADMIN_CHAT_ID, parse_mode="HTML")      

async def setup_bot_commands(application):
    await application.bot.set_my_commands([
        BotCommand("start", "Запустить бота"),
        BotCommand("help", "Описание"),
        BotCommand("kurs", "Курсы ЦБ/НБ и средние по обменникам"),
        BotCommand("course", "Курс валют ЦБ РФ"),
        BotCommand("coursekz", "Курс валют НБ КЗ"),
        BotCommand("kurs_oral", "Обменники Уральска"),
        BotCommand("kurs_almaty", "Обменники Алматы")
        # Добавь свои команды
    ])

    await application.bot.set_chat_menu_button(
        menu_button=MenuButtonCommands()
    )       
    
# 🕒 Задача для JobQueue
async def update_currency_data_job(context: ContextTypes.DEFAULT_TYPE):
    update_currency_data(context)
    
# URL для автопинга — лучше задать как переменную окружения в Render (PING_URL),
# иначе используется дефолт.
PING_URL = os.environ.get("PING_URL", "https://rubkzt-bot.onrender.com/")

async def ping_self(context: "ContextTypes.DEFAULT_TYPE"):
    """Пытаемся пинговать сам сайт, чтобы Render не засыпал (вызывается из JobQueue)."""
    try:
        # Выполняем blocking-запрос в ThreadPool, чтобы не блокировать loop
        await asyncio.to_thread(requests.get, PING_URL, {"timeout": 10})
        # если нужно логировать:
        # print(f"Pinged {PING_URL}")
    except Exception as e:
        # Не падаем на ошибках пинга — просто залогировать
        print("Ошибка автопинга:", e)        
    
async def post_init(application):
    print("🤖 Бот запущен")

# 👇 создаём фейковый Flask-сервер
flask_app = Flask(__name__)

@flask_app.route('/')
def index():
    return "🤖 Telegram bot is running"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)
    
async def main():
    update_currency_data()

    load_dotenv()
    TOKEN = os.getenv("TOKEN")
    if not TOKEN:
        raise ValueError("TOKEN не найден в переменных окружения")

    app = ApplicationBuilder().token(TOKEN).build()

    await setup_bot_commands(app)

    # 👇 Хендлеры
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usd", usd))
    app.add_handler(CommandHandler("eur", eur))
    app.add_handler(CommandHandler("kzt", kzt))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("kurs", rub_kzt_all))
    app.add_handler(CommandHandler("course", course))
    app.add_handler(CommandHandler("coursekz", coursekz))
    app.add_handler(CommandHandler("kurskz", kurskz))
    app.add_handler(CommandHandler("kurs_oral", kurskz_oral))
    app.add_handler(CommandHandler("kurs_almaty", kurskz_detail_almaty))
    app.add_handler(CommandHandler("nbrk", rub_nbrk))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # 🕒 Обновление курса каждый час
    app.job_queue.run_repeating(update_currency_data_job, interval=3600, first=0)
    print("🤖 Бот запущен")
    # 🔔 Автопинг сайта каждые 10 минут, чтобы Render не засыпал
    # первый пинг через 60 секунд (чтобы контейнер успел подняться)
    app.job_queue.run_repeating(ping_self, interval=600, first=60)
    
    await app.run_polling()

if __name__ == "__main__":
    nest_asyncio.apply()    
    # Фейковый веб-сервер для Render
    threading.Thread(target=run_flask).start()
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "cannot close a running event loop" not in str(e).lower():
            raise
