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
        if currency_code not in data["Valute"] or currency_code in ("KZT", "KZ", "КЗ"):
            return f"❌ Валюта '{currency_code}' не найдена в данных ЦБ РФ."

        valute = data["Valute"][currency_code]
        nominal = valute["Nominal"]
        value = valute["Value"]
        name = valute["Name"]

        # Если пользователь вводит KZT — пересчитываем как "обратный курс"
        if currency_code.lower() in ("kzt", "kz", "кз"):
            try:
                local_rate = get_kursz_data()  
            except Exception:
                local_rate = None
                
            valute = data["Valute"]["KZT"]
            nominal = valute["Nominal"]
            value = valute["Value"]
            rub_per_1_kzt = value / nominal
            kzt_per_1_rub = 1 / rub_per_1_kzt
                       
            converted = round(amount / kzt_per_1_rub, 2)
            line_cb = f"💰 По курсу ЦБ {amount} {currency_code} / {kzt_per_1_rub:.4f} = {converted} RUB"
            if local_rate and local_rate > 0:
                converted_local = round(amount / local_rate, 2)
                line_local = f"По обменному курсу {amount} {currency_code} / {local_rate:.4f} = {converted_local} RUB"
                return f"{line_cb}\n{line_local}"
            else:
                return line_cb
        else:
            rate = value / nominal
            converted = round(amount * rate, 2)
            return f"💰 {amount} {currency_code} × {rate:.4f} = {converted} RUB"

    except Exception:
        return None
