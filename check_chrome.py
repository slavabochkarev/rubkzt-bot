import shutil
import subprocess

def check_binary(name):
    path = shutil.which(name)
    if path:
        try:
            version = subprocess.check_output([path, "--version"], text=True).strip()
        except Exception as e:
            version = f"не удалось получить версию: {e}"
        return f"{name} найден: {path}, версия: {version}"
    else:
        return f"{name} не найден"

def main():
    print("=== Проверка бинарников в контейнере ===")
    for bin_name in ["chromium", "chromium-browser", "google-chrome", "chromedriver"]:
        print(check_binary(bin_name))

if __name__ == "__main__":
    main()
