from handlers import globals_store
# предполагается, что get_kursz_data и get_kurskz_rub_buy_sell_avg доступны в области видимости
# если get_kurskz_rub_buy_sell_avg в другом модуле, импортируй его явно:
# from some_module import get_kurskz_rub_buy_sell_avg

def try_convert_amount(message: str, data: dict) -> str | None:
    """Пробует распознать сообщение '<amount> <currency>' и умножить на курс ЦБ РФ."""
    try:
        print("[DEBUG] start try_convert_amount, message:", message)
        parts = message.strip().lower().split()
        if len(parts) != 2:
            print("[DEBUG] parts len != 2 -> None")
            return None

        amount_str, currency_code = parts
        try:
            amount = float(amount_str.replace(",", "."))
        except Exception as e:
            print("[DEBUG] invalid amount:", amount_str, "error:", e)
            return None

        currency_code = currency_code.upper()

        # Проверка наличия валюты
        if currency_code not in data.get("Valute", {}) and currency_code not in ("KZT", "KZ", "КЗ", "ЛЯ"):
            print(f"[DEBUG] currency {currency_code} not found in data")
            return f"❌ Валюта '{currency_code}' не найдена в данных ЦБ РФ."

        # Если пользователь вводит KZT — пересчитываем как "обратный курс"
        if currency_code in ("KZT", "KZ", "КЗ", "ЛЯ"):
            print("[DEBUG] enter KZT-branch")
            # Попытка получить локальный курс (из globals_store через get_kursz_data)
            try:
                local_rate = get_kursz_data()
            except Exception as e:
                print("[DEBUG] get_kursz_data() raised:", e)
                local_rate = None

            # Если local_rate нет — попробуем синхронно обновить globals_store (фоллбэк)
            if local_rate is None:
                print("[DEBUG] local_rate is None -> trying fallback update via get_kurskz_rub_buy_sell_avg()")
                try:
                    # Если у тебя есть функция get_kurskz_rub_buy_sell_avg в скоупе, используем её
                    data_fallback = get_kurskz_rub_buy_sell_avg()
                    if data_fallback and "avg_sell" in data_fallback:
                        try:
                            globals_store.avg_sell_global = float(data_fallback["avg_sell"])
                            print("[DEBUG] fallback assigned globals_store.avg_sell_global =", globals_store.avg_sell_global)
                        except Exception as e:
                            print("[ERROR] cannot convert fallback avg_sell to float:", e)
                            globals_store.avg_sell_global = None
                    else:
                        print("[DEBUG] fallback returned no data or no avg_sell")
                except NameError:
                    # функция не найдена в текущей скоупе, просто пропускаем
                    print("[DEBUG] get_kurskz_rub_buy_sell_avg() not available (NameError)")
                except Exception as e:
                    print("[ERROR] fallback get_kurskz_rub_buy_sell_avg() raised:", e)

                # повторная попытка взять курс из globals_store
                try:
                    local_rate = get_kursz_data()
                except Exception as e:
                    print("[DEBUG] second get_kursz_data() raised:", e)
                    local_rate = None

            # Пытаемся привести к числу
            try:
                local_rate_num = float(local_rate) if local_rate is not None else None
            except Exception as e:
                print("[DEBUG] float(local_rate) failed:", repr(local_rate), "err:", e)
                local_rate_num = None

            # Отладка: подробный лог
            print(f"[DEBUG] local_rate={local_rate!r}, local_rate_num={local_rate_num!r}")
            print("[DEBUG] globals_store info:", getattr(globals_store, "__file__", None), "id=", id(globals_store))

            # Берём данные ЦБ по KZT; если их нет — корректно обработаем
            kzt_valute = data.get("Valute", {}).get("KZT")
            if not kzt_valute:
                print("[DEBUG] data has no Valute['KZT']")
                if local_rate_num is not None and local_rate_num > 0:
                    converted_local = round(amount / local_rate_num, 2)
                    line_local = f"🔁 По обменному курсу {amount} KZT / {local_rate_num:.4f} = {converted_local} RUB"
                    return line_local
                return "❌ Нет данных по KZT в данных ЦБ РФ и локальный курс недоступен."

            nominal = kzt_valute["Nominal"]
            value = kzt_valute["Value"]
            rub_per_1_kzt = value / nominal
            kzt_per_1_rub = 1 / rub_per_1_kzt
            currency_code = "KZT"

            converted_cb = round(amount / kzt_per_1_rub, 2)
            line_cb = f"💰 По курсу ЦБ {amount} {currency_code} / {kzt_per_1_rub:.4f} = {converted_cb} RUB"

            if local_rate_num is not None and local_rate_num > 0:
                converted_local = round(amount / local_rate_num, 2)
                line_local = f"🔁 По обменному курсу {amount} {currency_code} / {local_rate_num:.4f} = {converted_local} RUB"
                print("[DEBUG] returning CB + local")
                return f"{line_cb}\n{line_local}"
            else:
                print("[DEBUG] returning CB only")
                return line_cb

        # Общий случай для других валют
        valute = data["Valute"][currency_code]
        nominal = valute["Nominal"]
        value = valute["Value"]
        rate = value / nominal
        converted = round(amount * rate, 2)
        print("[DEBUG] returning general conversion")
        return f"💰 {amount} {currency_code} × {rate:.4f} = {converted} RUB"

    except Exception as e:
        # Для отладки выводим ошибку (потом можно убрать)
        print("[ERROR] Exception in try_convert_amount:", e)
        return None
