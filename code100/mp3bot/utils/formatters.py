"""
Функции форматирования сообщений и интерфейса
"""


def shorten_address(address: str, start: int = 6, end: int = 6) -> str:
    """Сокращает адрес (например: EQ123...XYZ)"""
    if not address or len(address) < (start + end + 3):
        return address
    return f"{address[:start]}...{address[-end:]}"


def format_wallet_list_label(wallet: dict) -> str:
    """Форматирует метку кошелька д��я списка"""
    emoji = "⭐" if wallet.get("is_primary") else "💎"
    name = wallet.get("name")
    short = wallet.get("short", "unknown")
    
    if name:
        return f"{emoji} │ {name}"
    else:
        return f"{emoji} │ {short}"


def format_wallet_success_message(wallet: dict) -> str:
    """Форматирует сообщение об успешном добавлении кошелька"""
    short = wallet.get("short", "unknown")
    return (
        "<b>🟢 Wallet successfully added!</b>\n\n"
        "<blockquote>"
        f"<b>Address:</b> <code>{short}</code>"
        "</blockquote>"
    )


def get_deal_type_emoji(deal_type: str) -> str:
    """Возвращает emoji для типа сделки"""
    emojis = {
        "gifts": "🎁",
        "channels": "📢",
        "accounts": "👾"
    }
    return emojis.get(deal_type, "💼")