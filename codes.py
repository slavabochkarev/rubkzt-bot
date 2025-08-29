from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from telegram import Update
from telegram.ext import ContextTypes

# ✅ Функция для подгрузки шрифта с поддержкой кириллицы
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


async def codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Данные для вывода
    text = """\
BYN  Белорусский рубль
KGS  Киргизкий сом
KZT  Казахский тенге
EGP  Египетский фунт
AED  Дирхам (ОАЭ)
TRY  Турецкая лира
CNY  Юань
UZS  Узбекский сум
INR  Индийская рупия
DKK  Датская крона

"""

    # Создаём картинку
    img = Image.new("RGB", (500, 200), color="white")
    draw = ImageDraw.Draw(img)

    # Загружаем шрифт
    font = load_font(24)

    # Печатаем текст
    draw.text((20, 20), text, font=font, fill="black")

    # Сохраняем в буфер
    bio = BytesIO()
    bio.name = "codes.png"
    img.save(bio, "PNG")
    bio.seek(0)

    # Отправляем пользователю
    await update.message.reply_photo(photo=bio, caption="Коды валют")
