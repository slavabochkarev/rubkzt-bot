import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Service role key

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def execute_sql(query):
    try:
        url = f"{SUPABASE_URL}/rest/v1/rpc/exec_query"
        payload = {"sql_text": query}
        r = requests.post(url, headers=HEADERS, json=payload)
        r.raise_for_status()
        data = r.json()

        if not data:
            return []

        keys = list(data[0].keys())
        matrix = [keys]  # заголовки
        for row in data:
            matrix.append([row[key] for key in keys])
        return matrix

    except Exception as e:
        print(f"❌ Ошибка выполнения запроса: {e}")
        return []
