import pytest
from datetime import datetime, timedelta
from src.bot.scheduler import format_reminder_text

def test_format_reminder_text_basic():
    text = format_reminder_text(last_score=85, days_ago=30)
    assert "Прошло 30 дней" in text
    assert "85/100" in text
    assert "Твоя зона роста" not in text

def test_format_reminder_text_with_skill():
    text = format_reminder_text(last_score=70, focus_skill="Communication", days_ago=45)
    assert "Прошло 45 дней" in text
    assert "70/100" in text
    assert "Communication" in text
