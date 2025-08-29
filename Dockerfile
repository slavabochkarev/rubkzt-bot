# Базовый образ с Python
FROM python:3.11-slim

# Устанавливаем зависимости для Chrome и Selenium
RUN apt-get update && apt-get install -y \
    wget unzip curl gnupg \
    chromium chromium-driver \
    fonts-liberation libappindicator3-1 libasound2 libatk-bridge2.0-0 \
    libatk1.0-0 libc6 libcairo2 libcups2 libdbus-1-3 \
    libexpat1 libfontconfig1 libgbm1 libgcc1 libglib2.0-0 \
    libgtk-3-0 libnspr4 libnss3 libpango-1.0-0 libpangocairo-1.0-0 \
    libstdc++6 libx11-6 libx11-xcb1 libxcb1 libxcomposite1 \
    libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 \
    libxrandr2 libxrender1 libxss1 libxtst6 xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Python-библиотеки
RUN pip install --no-cache-dir \
    python-telegram-bot==20.* \
    selenium \
    pillow \
    instaloader \
    requests \
    python-dotenv

# Копируем проект в контейнер
WORKDIR /app
COPY . .

# Указываем переменную окружения (чтобы не ругался Telegram)
ENV PYTHONUNBUFFERED=1

# Запускаем бота
CMD ["python", "bot_1.py"]
