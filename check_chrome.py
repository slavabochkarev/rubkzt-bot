import shutil
import subprocess

def check_binary(name: str) -> str:
    """Проверяет наличие бинарника и его версию"""
    path = shutil.which(name)
    if path:
        try:
            version = subprocess.check_output([path, "--version"], text=True).strip()
        except Exception as e:
            version = f"не удалось получить версию: {e}"
        return f"{name}: найден ({path}), версия: {version}"
    else:
        return f"{name}: не найден"

def run_check() -> str:
    """Возвращает текстовый отчет для Telegram"""
    results = ["=== Проверка бинарников в контейнере ==="]
    for bin_name in ["chromium", "chromium-browser", "google-chrome", "chromedriver"]:
        results.append(check_binary(bin_name))
    return "\n".join(results)
