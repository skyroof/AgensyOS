from src.core.config import get_settings

def get_pack_prices() -> dict[str, int]:
    """Получить актуальные цены пакетов (в копейках)."""
    settings = get_settings()
    return {
        "single": settings.price_single,
        "pack3": settings.price_pack3,
        "pack10": settings.price_pack10,
    }

# Количество диагностик в пакете (константы)
PACK_COUNTS = {
    "single": 1,
    "pack3": 3,
    "pack10": 10,
}

# Названия пакетов
PACK_NAMES = {
    "single": "Одна диагностика",
    "pack3": "Пакет 3 диагностики",
    "pack10": "Пакет 10 диагностик",
}

# Описания пакетов
PACK_DESCRIPTIONS = {
    "single": "Полная диагностика: 10 вопросов, PDF-отчёт, план развития",
    "pack3": "3 полные диагностики для отслеживания прогресса (-22%)",
    "pack10": "10 диагностик для команды или активного развития (-33%)",
}
