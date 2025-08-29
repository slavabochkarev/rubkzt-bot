from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from telegram import Update
from telegram.ext import ContextTypes

CURRENCY_CODES = [
    ("BYN", "Белорусский рубль"),
    ("BZD", "Белизский доллар"),
    ("CAD", "Канадский доллар"),
    ("CDF", "Конголезский франк"),
    ("CNY", "Китайский юань"),
    ("CZK", "Чешская крона"),
    ("DKK", "Датская крона"),
    ("EGP", "Египетский фунт"),
]

async def codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Настройки
    width, height = 600, 50 + len(CURRENCY_CODES) * 40
    background_color = (245, 245, 245)  # светло-серый
    text_color = (20, 20, 20)

    # Создаём картинку
    img = Image.new("RGB", (width, height), color=background_color)
    draw = ImageDraw.Draw(img)

    # Шрифт (лучше подключить TTF)
    try:
        font = ImageFont.truetype("arial.ttf", 24)  # на Render может не быть arial
    except:
        font = ImageFont.load_default()

    # Заголовок
    draw.text((20, 10), "Коды валют", font=font, fill=text_color)

    # Выводим список
    y = 50
    for code, name in CURRENCY_CODES:
        draw.text((40, y), f"{code} — {name}", font=font, fill=text_color)
        y += 35

    # Сохраняем в память
    bio = BytesIO()
    bio.name = "codes.png"
    img.save(bio, "PNG")
    bio.seek(0)

    # Отправляем картинку пользователю
    await update.message.reply_photo(photo=bio)
