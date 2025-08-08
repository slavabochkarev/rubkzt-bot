import os
import requests
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Service role key

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

def save_user_info(user):
    """Сохраняет или обновляет пользователя"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/users"
        data = {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "language_code": user.language_code,
            "is_premium": getattr(user, "is_premium", False)
        }
        r = requests.post(url, headers=HEADERS, params={"on_conflict": "id"}, json=data)
        r.raise_for_status()
        print("✅ Пользователь сохранён в базе.")
    except Exception as e:
        print(f"❌ Ошибка сохранения пользователя: {e}")

def save_location(user_id, latitude, longitude, address):
    """Сохраняет геолокацию пользователя"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/locations"
        data = {
            "user_id": user_id,
            "latitude": latitude,
            "longitude": longitude,
            "address": address
        }
        r = requests.post(url, headers=HEADERS, json=data)
        r.raise_for_status()
        print("📍 Геолокация сохранена.")
    except Exception as e:
        print(f"❌ Ошибка сохранения геолокации: {e}")

def save_action(user_id, action):
    """Сохраняет действие пользователя"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/activity_log"
        data = {
            "user_id": user_id,
            "action": action
        }
        r = requests.post(url, headers=HEADERS, json=data)
        r.raise_for_status()
        print("💬 Действие сохранено.")
    except Exception as e:
        print(f"❌ Ошибка сохранения действия: {e}")
