from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from telegram import Update
from telegram.ext import ContextTypes
import matplotlib.pyplot as plt
import plotly.graph_objects as go

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
    if not matrix:
        await update.message.reply_text("Нет данных для отображения.")
        return

    row_height = 40
    padding = 20
    num_columns = len(matrix[0])
    col_widths = [max([len(str(row[i])) for row in matrix]) * 12 + 20 for i in range(num_columns)]

    width = sum(col_widths) + padding * 2
    height = row_height * len(matrix) + row_height + padding * 2

    img = Image.new("RGB", (width, height), (255, 255, 224))  # светло-жёлтый фон
    draw = ImageDraw.Draw(img)

    title_font = load_font(24)
    header_font = load_font(20)
    text_font = load_font(18)

    # Заголовок таблицы
    draw.text((padding, 10), title, font=title_font, fill="black")

    y = row_height + 20
    for row_idx, row in enumerate(matrix):
        x = padding

        # Заливка строки
        if row_idx == 0:  # заголовок
            row_color = (200, 200, 200)  # серый фон
            font = header_font
        elif row_idx % 2 == 0:
            row_color = (245, 245, 245)  # светло-серый для четных строк
            font = text_font
        else:
            row_color = (255, 255, 255)  # белый фон
            font = text_font

        # Фон строки
        draw.rectangle([padding, y, width - padding, y + row_height], fill=row_color)

        # Текст + границы
        for col_idx, cell in enumerate(row):
            cell_text = str(cell)
            col_width = col_widths[col_idx]

            # Рисуем текст по центру ячейки
            draw.text((x + 5, y + 10), cell_text, font=font, fill="black")

            # Вертикальная граница
            draw.line([(x, y), (x, y + row_height)], fill="black", width=1)

            x += col_width

        draw.line([(width - padding, y), (width - padding, y + row_height)], fill="black", width=1)
        # Горизонтальная граница
        draw.line([(padding, y), (width - padding, y)], fill="black", width=1)

        y += row_height

    # Нижняя граница
    draw.line([(padding, y), (width - padding, y)], fill="black", width=1)

    bio = BytesIO()
    bio.name = "matrix.png"
    img.save(bio, "PNG")
    bio.seek(0)

    await update.message.reply_photo(photo=bio)

async def matrix_to_pie_chart(update: Update, context: ContextTypes.DEFAULT_TYPE, matrix, title="Диаграмма"):
    """
    Строит круговую диаграмму по данным из матрицы и отправляет в Telegram.
    Ожидается, что в матрице:
    - первая строка: ['username', 'actions_count']
    - остальные строки: ['имя', число]
    """
    if not matrix or len(matrix) <= 1:
        await update.message.reply_text("Нет данных для отображения.")
        return

    # Берём данные (пропускаем заголовок)
    labels = [row[0] for row in matrix[1:]]
    values = [row[1] for row in matrix[1:]]

    # Создаём диаграмму
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=90, counterclock=False)
    ax.set_title(title)

    # Сохраняем в память
    bio = BytesIO()
    bio.name = "chart.png"
    plt.savefig(bio, format="png", bbox_inches="tight")
    plt.close(fig)
    bio.seek(0)

    await update.message.reply_photo(photo=bio)

import plotly.graph_objects as go
from io import BytesIO

async def matrix_to_pie_chart_3d(update, context, matrix, title="3D Диаграмма"):
    """
    Строит "3D"-круговую диаграмму (эффект пончика) с помощью Plotly и отправляет в Telegram.
    - matrix: [['username', 'actions_count'], ['user1', 10], ...]
    """
    if not matrix or len(matrix) <= 1:
        await update.message.reply_text("Нет данных для отображения.")
        return

    # Данные (пропускаем заголовок)
    labels = [str(row[0]) for row in matrix[1:]]
    values = [row[1] for row in matrix[1:]]

    if not labels or not values:
        await update.message.reply_text("Недостаточно данных для диаграммы.")
        return

    # Создаём фигуру
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.4,                # пончик
        pull=[0.05]*len(labels), # лёгкий вынос секторов
    )])

    fig.update_traces(textinfo='percent+label')  # проценты + подписи
    fig.update_layout(title_text=title)

    # Сохраняем картинку в память
    bio = BytesIO()
    try:
        fig.write_image(bio, format="png", engine="kaleido")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Ошибка при создании диаграммы: {e}")
        return

    bio.seek(0)
    bio.name = "chart3d.png"

    # Отправляем в чат
    await update.message.reply_photo(photo=bio)
