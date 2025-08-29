from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from telegram import Update
from telegram.ext import ContextTypes
import os

def load_font(size=20):
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


# --- валюты + iso код страны (для названия файла PNG) ---
CURRENCY_CODES = [
    ("BYN", "Белорусский рубль", "by"),
    ("KGS", "Киргизский сом", "kg"),
    ("KZT", "Казахский тенге", "kz"),
    ("EGP", "Египетский фунт", "eg"),
    ("AED", "Дирхам (ОАЭ)", "ae"),
    ("TRY", "Турецкая лира", "tr"),
    ("CNY", "Китайский юань", "cn"),
    ("UZS", "Узбекский сум", "uz"),
    ("INR", "Индийская рупия", "in"),
    ("DKK", "Датская крона", "dk"),
]

FLAGS_DIR = "flags"  # папка с PNG флагами


async def codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row_height = 60
    width, height = 600, row_height * len(CURRENCY_CODES) + 80

    img = Image.new("RGB", (width, height), (255, 255, 224))  # светло-жёлтый
    draw = ImageDraw.Draw(img)

    title_font = load_font(28)
    text_font = load_font(22)

    draw.text((20, 20), "Коды валют", font=title_font, fill="black")

    y = 80
    for code, name, iso in CURRENCY_CODES:
        flag_path = os.path.join(FLAGS_DIR, f"{iso}.png")
        if os.path.exists(flag_path):
            try:
                flag = Image.open(flag_path).convert("RGBA")
                flag = flag.resize((40, 30))
                img.paste(flag, (40, y), flag)
            except Exception as e:
                print(f"⚠️ Ошибка при загрузке флага {iso}: {e}")

        draw.text((100, y), f"{code} — {name}", font=text_font, fill="black")
        y += row_height

    bio = BytesIO()
    bio.name = "codes.png"
    img.save(bio, "PNG")
    bio.seek(0)

    await update.message.reply_photo(photo=bio, caption="📋 Список валютных кодов")
