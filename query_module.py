import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def get_user_activity():
    try:
        url = f"{SUPABASE_URL}/rest/v1/user_activity"
        params = {"select": "*"}  # выбрать все колонки
        r = requests.get(url, headers=HEADERS, params=params)
        r.raise_for_status()
        data = r.json()

        if not data:
            return []

        matrix = [["username", "actions_count"]]
        for row in data:
            matrix.append([row["username"], row["actions_count"]])

        return matrix

    except Exception as e:
        print(f"❌ Ошибка выборки user_activity: {e}")
        return []
