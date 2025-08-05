def try_convert_amount(message: str, data: dict) -> str | None:
    """Пробует распознать сообщение в формате '<amount> <currency>' и умножить на курс ЦБ РФ."""
    try:
        parts = message.strip().lower().split()
        if len(parts) != 2:
            return None

        amount_str, currency_code = parts
        amount = float(amount_str.replace(",", "."))
        currency_code = currency_code.upper()

        if currency_code not in data["Valute"]:
            return f"❌ Валюта '{currency_code}' не найдена в данных ЦБ РФ."

        rate = data["Valute"][currency_code]["Value"]
        converted = round(amount * rate, 2)
        name = data["Valute"][currency_code]["Name"]

        return f"💰 {amount} {currency_code} ({name}) × {rate} = {converted} RUB"
    except Exception:
        return None
