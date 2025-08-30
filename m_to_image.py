from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from telegram import Update
from telegram.ext import ContextTypes

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


async def matrix_to_image(update: Update, context: ContextTypes.DEFAULT_TYPE, matrix, title="Таблица"):
    """
    Отображает матрицу в виде изображения и отправляет в Telegram.
    
    :param matrix: список списков, первая строка — заголовки
    :param title: заголовок таблицы
    """
    if not matrix:
        await update.message.reply_text("Нет данных для отображения.")
        return

    row_height = 40
    padding = 20
    num_columns = len(matrix[0])
    col_widths = [max([len(str(row[i])) for row in matrix]) * 12 for i in range(num_columns)]

    width = sum(col_widths) + padding * 2
    height = row_height * len(matrix) + row_height + padding

    img = Image.new("RGB", (width, height), (255, 255, 224))  # светло-жёлтый фон
    draw = ImageDraw.Draw(img)

    title_font = load_font(28)
    text_font = load_font(22)

    draw.text((padding, 10), title, font=title_font, fill="black")

    y = row_height + 10
    for row_idx, row in enumerate(matrix):
        x = padding
        for col_idx, cell in enumerate(row):
            draw.text((x, y), str(cell), font=text_font, fill="black")
            x += col_widths[col_idx]
        y += row_height

    bio = BytesIO()
    bio.name = "matrix.png"
    img.save(bio, "PNG")
    bio.seek(0)

    await update.message.reply_photo(photo=bio)
