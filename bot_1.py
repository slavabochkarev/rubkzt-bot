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
from handlers.converter import try_convert_amount

# Глобальный кэш
cached_data = None
last_updated = None
CACHE_TTL = datetime.timedelta(hours=1)  # Время жизни кэша: 1 час

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

        
# 📊 Общее — USD и EUR
async def course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_currency_data()
    if data:
        usd_rate = data["Valute"]["USD"]["Value"]
        eur_rate = data["Valute"]["EUR"]["Value"]
        kzt_rate = 1 / (data["Valute"]["KZT"]["Value"] / data["Valute"]["KZT"]["Nominal"])
        date_rf = last_updated.strftime('%d.%m.%Y')
        msg = (
            f"Курсы валют по данным ЦБ РФ на {date_rf}:\n"
            f"💵 1 USD = {usd_rate:.2f} RUB\n"
            f"💵 1 RUB = {kzt_rate:.2f} KZT\n"
            f"💶 1 EUR = {eur_rate:.2f} RUB"
        )
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("Не удалось получить данные от ЦБ РФ.")

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
    print("🔔 Команда /start получена")

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
    text = update.message.text.lower()

    #if "usd" in text:
        #await usd(update, context)
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
                await update.message.reply_text(result)
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
    data = get_kurskz_rub_buy_sell_avg()
    if not data:
        await update.message.reply_text("Не удалось получить данные об обменниках.")
        return

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

# 🔄 Функция обновления кеша курсов
def update_currency_data():
    global cached_data, last_updated
    try:
        response = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=10)
        response.raise_for_status()
        cached_data = response.json()
        last_updated = datetime.datetime.now()
        print(f"🔁 Данные обновлены из сети: {last_updated}")
    except Exception as e:
        print("❌ Ошибка при обновлении курса:", e)

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Данные ЦБ РФ с www.cbr-xml-daily.ru \n"
        f"Данные НБ РК с nationalbank.kz \n"
        f"И данные обменников kurs.kz\n\n\n"        
        f"Обратная связь - @SlavaBochkarev\n"
    )

async def setup_bot_commands(application):
    await application.bot.set_my_commands([
        BotCommand("start", "Запустить бота"),
        BotCommand("help", "Описание"),
        BotCommand("kurs", "Курсы ЦБ/НБ и средние по обменникам"),
        BotCommand("course", "Курс валют ЦБ РФ"),
        BotCommand("kurs_oral", "Обменники Уральска"),
        BotCommand("kurs_almaty", "Обменники Алматы")
        # Добавь свои команды
    ])

    await application.bot.set_chat_menu_button(
        menu_button=MenuButtonCommands()
    )       
    
# 🕒 Задача для JobQueue
async def update_currency_data_job(context: ContextTypes.DEFAULT_TYPE):
    update_currency_data()
           
async def post_init(application):
    print("🤖 Бот запущен")
    
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
    app.add_handler(CommandHandler("kurskz", kurskz))
    app.add_handler(CommandHandler("kurs_oral", kurskz_oral))
    app.add_handler(CommandHandler("kurs_almaty", kurskz_detail_almaty))
    app.add_handler(CommandHandler("nbrk", rub_nbrk))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # 🕒 Обновление курса каждый час
    app.job_queue.run_repeating(update_currency_data_job, interval=3600, first=0)
    print("🤖 Бот запущен")
    await app.run_polling()

if __name__ == "__main__":
    nest_asyncio.apply()    
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "cannot close a running event loop" not in str(e).lower():
        raise
    
#if __name__ == "__main__":
    #nest_asyncio.apply()
    #asyncio.get_event_loop().run_until_complete(main())   
#asyncio.run(main())
