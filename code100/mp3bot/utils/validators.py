"""
Функции валидации входных данных
"""
import re


TON_ADDRESS_REGEX = re.compile(r'^[EUk0][Q][A-Za-z0-9_-]{46}$')


def is_valid_ton_address(addr: str) -> bool:
    """Проверяет корректность TON-адреса"""
    return bool(TON_ADDRESS_REGEX.match(addr.strip()))


def is_valid_amount(amount_str: str) -> bool:
    """Проверяет корректность суммы"""
    try:
        if amount_str.count('.') > 1:
            return False
        if not all(c.isdigit() or c == '.' for c in amount_str):
            return False
        float(amount_str)
        return True
    except:
        return False