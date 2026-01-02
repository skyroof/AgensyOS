"""
Генератор Share Card (PNG) для результатов диагностики.

Создаёт красивую картинку для шаринга в соцсетях.
"""
import io
import math
from PIL import Image, ImageDraw, ImageFont
from typing import Optional


# Размеры карточки (оптимально для соцсетей)
CARD_WIDTH = 1200
CARD_HEIGHT = 630

# Цветовая палитра
COLORS = {
    "bg_start": (26, 32, 44),      # Тёмно-синий
    "bg_end": (45, 55, 72),        # Синий
    "accent": (99, 179, 237),      # Голубой
    "accent_bright": (129, 230, 217),  # Бирюзовый
    "text_primary": (255, 255, 255),
    "text_secondary": (160, 174, 192),
    "score_bg": (45, 55, 72),
    "chart_fill": (99, 179, 237, 80),   # С прозрачностью
    "chart_stroke": (99, 179, 237),
    "chart_grid": (74, 85, 104),
}

# Уровни по баллам (на русском)
LEVELS = {
    (0, 25): ("Junior", "🌱"),
    (25, 40): ("Junior+", "🌿"),
    (40, 60): ("Middle", "📈"),
    (60, 75): ("Middle+", "💪"),
    (75, 85): ("Senior", "⭐"),
    (85, 101): ("Lead", "🏆"),
}


def get_level(score: int) -> tuple[str, str]:
    """Определение уровня по баллам."""
    for (min_score, max_score), (level, emoji) in LEVELS.items():
        if min_score <= score < max_score:
            return level, emoji
    return "Специалист", "✨"


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Загрузка шрифта с поддержкой кириллицы."""
    # Приоритетные пути для поиска шрифтов
    font_paths = [
        "assets/fonts/Montserrat-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",  # Windows
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
        "arial.ttf",
    ]
    
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
            
    # Fallback (может не поддерживать кириллицу)
    return ImageFont.load_default()


def create_gradient(width: int, height: int, start_color: tuple, end_color: tuple) -> Image.Image:
    """Создание вертикального градиента."""
    gradient = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(gradient)
    
    for y in range(height):
        ratio = y / height
        r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    return gradient


def draw_radar_chart(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    radius: int,
    values: dict[str, float],
    colors: dict,
):
    """Рисование radar chart."""
    n = len(values)
    if n == 0:
        return
    
    angle_step = 2 * math.pi / n
    
    # Сетка (3 уровня)
    for level in [0.33, 0.66, 1.0]:
        points = []
        for i in range(n):
            angle = i * angle_step - math.pi / 2
            x = center[0] + int(radius * level * math.cos(angle))
            y = center[1] + int(radius * level * math.sin(angle))
            points.append((x, y))
        points.append(points[0])  # Замыкаем
        draw.polygon(points, outline=colors["chart_grid"], width=1)
    
    # Оси
    for i in range(n):
        angle = i * angle_step - math.pi / 2
        x = center[0] + int(radius * math.cos(angle))
        y = center[1] + int(radius * math.sin(angle))
        draw.line([center, (x, y)], fill=colors["chart_grid"], width=1)
    
    # Данные
    data_points = []
    labels = list(values.keys())
    scores = list(values.values())
    
    for i, score in enumerate(scores):
        normalized = score / 10  # Предполагаем шкалу 0-10
        angle = i * angle_step - math.pi / 2
        x = center[0] + int(radius * normalized * math.cos(angle))
        y = center[1] + int(radius * normalized * math.sin(angle))
        data_points.append((x, y))
    
    # Заливка области
    if data_points:
        # PIL не поддерживает полупрозрачные полигоны напрямую,
        # поэтому рисуем только контур с заливкой
        draw.polygon(data_points, fill=colors.get("chart_fill_solid", (99, 179, 237)), outline=colors["chart_stroke"], width=2)
        
        # Точки на вершинах
        for point in data_points:
            draw.ellipse(
                [point[0] - 4, point[1] - 4, point[0] + 4, point[1] + 4],
                fill=colors["accent_bright"],
            )


def draw_score_circle(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    radius: int,
    score: int,
    font_large: ImageFont.FreeTypeFont,
    font_small: ImageFont.FreeTypeFont,
    colors: dict,
):
    """Рисование круга с баллом."""
    # Фон круга
    draw.ellipse(
        [center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius],
        fill=colors["score_bg"],
        outline=colors["accent"],
        width=4,
    )
    
    # Дуга прогресса
    progress_angle = int(360 * score / 100)
    draw.arc(
        [center[0] - radius + 5, center[1] - radius + 5, center[0] + radius - 5, center[1] + radius - 5],
        start=-90,
        end=-90 + progress_angle,
        fill=colors["accent_bright"],
        width=8,
    )
    
    # Текст балла
    score_text = str(score)
    bbox = draw.textbbox((0, 0), score_text, font=font_large)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    draw.text(
        (center[0] - text_width // 2, center[1] - text_height // 2 - 20),
        score_text,
        font=font_large,
        fill=colors["text_primary"],
    )
    
    # "/100"
    sub_text = "/100"
    bbox = draw.textbbox((0, 0), sub_text, font=font_small)
    text_width = bbox[2] - bbox[0]
    
    draw.text(
        (center[0] - text_width // 2, center[1] + 25),
        sub_text,
        font=font_small,
        fill=colors["text_secondary"],
    )


def generate_share_card(
    total_score: int,
    role_name: str,
    category_scores: dict[str, int],
    username: Optional[str] = None,
) -> bytes:
    """
    Генерация PNG share card.
    
    Args:
        total_score: Общий балл (0-100)
        role_name: Роль (Дизайнер/Продакт-менеджер)
        category_scores: Баллы по категориям (Hard Skills, Soft Skills, Thinking, Mindset)
        username: Имя пользователя (опционально)
    
    Returns:
        PNG в байтах
    """
    # Создаём изображение с градиентом
    img = create_gradient(CARD_WIDTH, CARD_HEIGHT, COLORS["bg_start"], COLORS["bg_end"])
    draw = ImageDraw.Draw(img)
    
    # Загружаем шрифты
    font_title = load_font(48)
    font_large = load_font(72)
    font_medium = load_font(32)
    font_small = load_font(24)
    
    # === ЗАГОЛОВОК ===
    title = "MAX Diagnostic Bot"
    draw.text((50, 30), title, font=font_title, fill=COLORS["text_primary"])
    
    # === РОЛЬ И УРОВЕНЬ ===
    level, emoji = get_level(total_score)
    subtitle = f"{role_name} • {level}"
    draw.text((50, 95), subtitle, font=font_medium, fill=COLORS["accent"])
    
    # === КРУГ С БАЛЛОМ ===
    score_center = (950, 315)
    draw_score_circle(
        draw, score_center, 120, total_score,
        font_large, font_small, COLORS
    )
    
    # Уровень под кругом с баллом
    level_full = f"{level}"
    bbox = draw.textbbox((0, 0), level_full, font=font_medium)
    level_width = bbox[2] - bbox[0]
    draw.text(
        (score_center[0] - level_width // 2, score_center[1] + 130),
        level_full,
        font=font_medium,
        fill=COLORS["accent_bright"],
    )
    
    # === КАТЕГОРИИ (слева, на русском) ===
    categories_y = 180
    category_labels = {
        "hard_skills": ("Навыки", 30),      # (название, макс балл)
        "soft_skills": ("Коммуникация", 25),
        "thinking": ("Мышление", 25),
        "mindset": ("Майндсет", 20),
    }
    
    for key, (label, max_score) in category_labels.items():
        score = category_scores.get(key, 0)
        
        # Название
        draw.text((50, categories_y), label, font=font_medium, fill=COLORS["text_primary"])
        
        # Прогресс-бар
        bar_x = 50
        bar_y = categories_y + 45
        bar_width = 400
        bar_height = 20
        
        # Фон бара
        draw.rounded_rectangle(
            [bar_x, bar_y, bar_x + bar_width, bar_y + bar_height],
            radius=10,
            fill=COLORS["chart_grid"],
        )
        
        # Заполнение (относительно максимального балла категории)
        fill_ratio = score / max_score if max_score > 0 else 0
        fill_width = int(bar_width * fill_ratio)
        if fill_width > 0:
            draw.rounded_rectangle(
                [bar_x, bar_y, bar_x + fill_width, bar_y + bar_height],
                radius=10,
                fill=COLORS["accent"],
            )
        
        # Балл справа от бара (с максимумом)
        draw.text(
            (bar_x + bar_width + 20, categories_y + 10),
            f"{score}/{max_score}",
            font=font_medium,
            fill=COLORS["text_primary"],
        )
        
        categories_y += 100
    
    # === RADAR CHART (миниатюрный, справа от категорий) ===
    # Можно добавить позже, пока оставим простой вариант
    
    # === WATERMARK ===
    watermark = "t.me/VISUALMAXAGENCY_BOT"
    draw.text((50, CARD_HEIGHT - 50), watermark, font=font_small, fill=COLORS["text_secondary"])
    
    # Декоративные элементы
    draw.ellipse([CARD_WIDTH - 150, -50, CARD_WIDTH + 50, 150], fill=COLORS["accent"] + (30,), outline=None)
    draw.ellipse([CARD_WIDTH - 100, CARD_HEIGHT - 100, CARD_WIDTH + 100, CARD_HEIGHT + 100], fill=COLORS["accent"] + (20,), outline=None)
    
    # Сохраняем в байты
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", quality=95)
    buffer.seek(0)
    
    return buffer.getvalue()


def generate_share_card_simple(
    total_score: int,
    role_name: str,
    level_name: str,
) -> bytes:
    """
    Упрощённая версия share card (без категорий).
    Минималистичный дизайн для быстрого шаринга.
    """
    width, height = 800, 418  # Соотношение для Telegram
    
    img = create_gradient(width, height, COLORS["bg_start"], COLORS["bg_end"])
    draw = ImageDraw.Draw(img)
    
    font_title = load_font(36)
    font_score = load_font(96)
    font_level = load_font(28)
    font_small = load_font(20)
    
    # Заголовок
    draw.text((40, 30), "MAX Diagnostic Bot", font=font_title, fill=COLORS["text_primary"])
    
    # Роль
    draw.text((40, 80), role_name, font=font_level, fill=COLORS["accent"])
    
    # Балл (большой, по центру)
    score_text = str(total_score)
    bbox = draw.textbbox((0, 0), score_text, font=font_score)
    text_width = bbox[2] - bbox[0]
    draw.text(
        ((width - text_width) // 2, 150),
        score_text,
        font=font_score,
        fill=COLORS["text_primary"],
    )
    
    # "/100"
    sub = "/100"
    bbox = draw.textbbox((0, 0), sub, font=font_level)
    sub_width = bbox[2] - bbox[0]
    draw.text(
        ((width - sub_width) // 2, 245),
        sub,
        font=font_level,
        fill=COLORS["text_secondary"],
    )
    
    # Уровень
    level, emoji = get_level(total_score)
    level_text = f"{level}"
    bbox = draw.textbbox((0, 0), level_text, font=font_level)
    level_width = bbox[2] - bbox[0]
    draw.text(
        ((width - level_width) // 2, 310),
        level_text,
        font=font_level,
        fill=COLORS["accent_bright"],
    )
    
    # Watermark
    draw.text((40, height - 40), "t.me/VISUALMAXAGENCY_BOT", font=font_small, fill=COLORS["text_secondary"])
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", quality=95)
    buffer.seek(0)
    
    return buffer.getvalue()

