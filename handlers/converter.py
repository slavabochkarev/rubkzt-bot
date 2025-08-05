def try_convert_amount(message: str, data: dict) -> str | None:
    """Пробует распознать сообщение в формате '<amount> <currency>' и умножить на курс ЦБ РФ."""
    try:
        parts = message.strip().lower().split()
        if len(parts) != 2:
            return None

        amount_str, currency_code = parts
        amount = float(amount_str.replace(",", "."))
        currency_code = currency_code.upper()

        # Проверка наличия валюты
        if currency_code not in data["Valute"]:
            return f"❌ Валюта '{currency_code}' не найдена в данных ЦБ РФ."

        valute = data["Valute"][currency_code]
        nominal = valute["Nominal"]
        value = valute["Value"]
        name = valute["Name"]

        # Если пользователь вводит KZT — пересчитываем как "обратный курс"
        if currency_code == "KZT":
            valute = data["Valute"]["KZT"]
            nominal = valute["Nominal"]
            value = valute["Value"]
            rub_per_1_kzt = value / nominal
            kzt_per_1_rub = 1 / rub_per_1_kzt
            
            #rate = value / nominal
            converted = round(amount / kzt_per_1_rub, 2)
            return f"💰 {amount} {currency_code} ({name}) / {kzt_per_1_rub:.4f} = {converted} RUB"
        else:
            rate = value / nominal
            converted = round(amount * rate, 2)
            return f"💰 {amount} {currency_code} ({name}) × {rate:.4f} = {converted} RUB"

    except Exception:
        return None
