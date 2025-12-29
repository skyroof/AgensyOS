"""
Генератор красивых PDF-отчётов с визуализациями.

Включает:
- Radar chart компетенций (12 метрик)
- Цветные progress bars
- Стильный современный дизайн
- Визуальное сравнение с бенчмарком
"""
import io
import logging
import math
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, Flowable, Image
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Polygon, Circle, Line, String, Rect
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics import renderPDF

logger = logging.getLogger(__name__)

# ========================================
# ЦВЕТОВАЯ ПАЛИТРА
# ========================================

class Colors:
    """Премиальная цветовая схема отчёта (McKinsey-style)."""
    
    # Основные — глубокий синий
    PRIMARY = colors.HexColor('#1E3A5F')      # Deep Navy
    SECONDARY = colors.HexColor('#2C5282')    # Royal Blue
    ACCENT = colors.HexColor('#FF6B35')       # Vibrant Orange (акцент)
    HIGHLIGHT = colors.HexColor('#FF6B35')    # Акцент
    
    # Уровни (градации)
    EXCELLENT = colors.HexColor('#10B981')    # Emerald Green
    GOOD = colors.HexColor('#3B82F6')         # Blue
    AVERAGE = colors.HexColor('#F59E0B')      # Amber
    LOW = colors.HexColor('#EF4444')          # Red
    
    # Категории — премиальная палитра
    HARD_SKILLS = colors.HexColor('#6366F1')  # Indigo
    SOFT_SKILLS = colors.HexColor('#8B5CF6')  # Purple
    THINKING = colors.HexColor('#14B8A6')     # Teal
    MINDSET = colors.HexColor('#F97316')      # Orange
    
    # Фоны
    LIGHT_BG = colors.HexColor('#F8FAFC')     # Slate 50
    CARD_BG = colors.HexColor('#FFFFFF')
    BORDER = colors.HexColor('#E2E8F0')       # Slate 200
    DARK_BG = colors.HexColor('#0F172A')      # Slate 900 (для header)
    
    # Текст
    TEXT_PRIMARY = colors.HexColor('#1E293B')   # Slate 800
    TEXT_SECONDARY = colors.HexColor('#64748B') # Slate 500
    TEXT_MUTED = colors.HexColor('#94A3B8')     # Slate 400
    TEXT_WHITE = colors.HexColor('#FFFFFF')
    
    # Градиент эффекты
    GRADIENT_START = colors.HexColor('#1E3A5F')
    GRADIENT_END = colors.HexColor('#3B82F6')


# ========================================
# РЕГИСТРАЦИЯ ШРИФТОВ
# ========================================

import os

# Шрифты Montserrat (приоритет) и fallback на системные
FONT_PATHS = {
    "regular": [
        # Montserrat (Docker)
        "/app/assets/fonts/Montserrat-Regular.ttf",
        # Montserrat (Local)
        "assets/fonts/Montserrat-Regular.ttf",
        # Fallback: DejaVu (Linux)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        # Fallback: Windows
        "C:/Windows/Fonts/arial.ttf",
    ],
    "medium": [
        "/app/assets/fonts/Montserrat-Medium.ttf",
        "assets/fonts/Montserrat-Medium.ttf",
    ],
    "semibold": [
        "/app/assets/fonts/Montserrat-SemiBold.ttf",
        "assets/fonts/Montserrat-SemiBold.ttf",
    ],
    "bold": [
        "/app/assets/fonts/Montserrat-Bold.ttf",
        "assets/fonts/Montserrat-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ],
}

# Дефолтные шрифты
FONT_REGULAR = 'Helvetica'
FONT_MEDIUM = 'Helvetica'
FONT_SEMIBOLD = 'Helvetica-Bold'
FONT_BOLD = 'Helvetica-Bold'

def register_font(name: str, paths: list[str]) -> str:
    """Регистрирует первый найденный шрифт из списка путей."""
    for path in paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                logger.info(f"✅ Registered font '{name}': {path}")
                return name
            except Exception as e:
                logger.warning(f"Failed to register {path}: {e}")
    return None

# Регистрация шрифтов
try:
    if reg := register_font('Montserrat', FONT_PATHS["regular"]):
        FONT_REGULAR = reg
    if reg := register_font('Montserrat-Medium', FONT_PATHS["medium"]):
        FONT_MEDIUM = reg
    if reg := register_font('Montserrat-SemiBold', FONT_PATHS["semibold"]):
        FONT_SEMIBOLD = reg
    if reg := register_font('Montserrat-Bold', FONT_PATHS["bold"]):
        FONT_BOLD = reg
        
    # Регистрируем font family для использования в HTML
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    if FONT_REGULAR.startswith('Montserrat'):
        registerFontFamily(
            'Montserrat',
            normal=FONT_REGULAR,
            bold=FONT_BOLD,
        )
        logger.info("✅ Montserrat font family registered")
        
except Exception as e:
    logger.warning(f"Font registration error: {e}")

# Aliases для совместимости
FONT_NAME = FONT_REGULAR


# ========================================
# КАСТОМНЫЕ FLOWABLES (КОМПОНЕНТЫ)
# ========================================

class RadarChart(Flowable):
    """Radar chart для 12 компетенций."""
    
    def __init__(self, metrics: dict[str, float], width: float = 180, height: float = 180):
        Flowable.__init__(self)
        self.metrics = metrics
        self.width = width
        self.height = height
        self.center_x = width / 2
        self.center_y = height / 2
        self.radius = min(width, height) / 2 - 25
    
    def draw(self):
        canvas = self.canv
        
        # Метрики в порядке отображения
        metric_order = [
            ("expertise", "Экспертиза"),
            ("methodology", "Методология"),
            ("tools_proficiency", "Инструменты"),
            ("articulation", "Коммуникация"),
            ("self_awareness", "Самосознание"),
            ("conflict_handling", "Конфликты"),
            ("depth", "Глубина"),
            ("structure", "Структура"),
            ("systems_thinking", "Системность"),
            ("creativity", "Креативность"),
            ("honesty", "Честность"),
            ("growth_orientation", "Рост"),
        ]
        
        n_metrics = len(metric_order)
        angle_step = 2 * math.pi / n_metrics
        
        # Рисуем сетку (круги)
        for level in [2.5, 5, 7.5, 10]:
            r = self.radius * (level / 10)
            canvas.setStrokeColor(Colors.BORDER)
            canvas.setLineWidth(0.5)
            canvas.circle(self.center_x, self.center_y, r, stroke=1, fill=0)
        
        # Рисуем лучи и подписи
        canvas.setFont(FONT_NAME, 6)
        for i, (metric_key, metric_name) in enumerate(metric_order):
            angle = -math.pi / 2 + i * angle_step  # Начинаем сверху
            
            # Луч
            x_end = self.center_x + self.radius * math.cos(angle)
            y_end = self.center_y + self.radius * math.sin(angle)
            canvas.setStrokeColor(Colors.BORDER)
            canvas.setLineWidth(0.3)
            canvas.line(self.center_x, self.center_y, x_end, y_end)
            
            # Подпись
            label_r = self.radius + 12
            x_label = self.center_x + label_r * math.cos(angle)
            y_label = self.center_y + label_r * math.sin(angle)
            
            canvas.setFillColor(Colors.TEXT_SECONDARY)
            
            # Выравнивание подписей
            if abs(math.cos(angle)) < 0.1:  # Сверху/снизу
                canvas.drawCentredString(x_label, y_label - 2, metric_name)
            elif math.cos(angle) > 0:  # Справа
                canvas.drawString(x_label, y_label - 2, metric_name)
            else:  # Слева
                canvas.drawRightString(x_label, y_label - 2, metric_name)
        
        # Рисуем полигон значений
        points = []
        for i, (metric_key, _) in enumerate(metric_order):
            value = self.metrics.get(metric_key, 5)
            angle = -math.pi / 2 + i * angle_step
            r = self.radius * (value / 10)
            x = self.center_x + r * math.cos(angle)
            y = self.center_y + r * math.sin(angle)
            points.append((x, y))
        
        # Заливка полигона
        path = canvas.beginPath()
        path.moveTo(points[0][0], points[0][1])
        for x, y in points[1:]:
            path.lineTo(x, y)
        path.close()
        
        canvas.setFillColor(colors.Color(0.23, 0.65, 0.98, alpha=0.3))
        canvas.setStrokeColor(Colors.HARD_SKILLS)
        canvas.setLineWidth(2)
        canvas.drawPath(path, stroke=1, fill=1)
        
        # Точки на вершинах
        for x, y in points:
            canvas.setFillColor(Colors.HARD_SKILLS)
            canvas.circle(x, y, 3, stroke=0, fill=1)


class ScoreCircle(Flowable):
    """Большой круговой индикатор с баллом в центре."""
    
    def __init__(
        self, 
        score: int, 
        max_score: int = 100, 
        size: float = 120,
        label: str = "из 100",
        sublabel: str = "",
    ):
        Flowable.__init__(self)
        self.score = score
        self.max_score = max_score
        self.size = size
        self.label = label
        self.sublabel = sublabel
        self.width = size
        self.height = size
    
    def draw(self):
        canvas = self.canv
        cx, cy = self.size / 2, self.size / 2
        radius = self.size / 2 - 8
        
        # Определяем цвет по баллу
        if self.score >= 80:
            color = Colors.EXCELLENT
        elif self.score >= 60:
            color = Colors.GOOD
        elif self.score >= 40:
            color = Colors.AVERAGE
        else:
            color = Colors.LOW
        
        # Фоновый круг (серый)
        canvas.setStrokeColor(Colors.BORDER)
        canvas.setLineWidth(12)
        canvas.circle(cx, cy, radius, stroke=1, fill=0)
        
        # Прогресс-дуга
        progress = self.score / self.max_score
        start_angle = 90  # Начинаем сверху
        extent = -360 * progress  # По часовой стрелке
        
        canvas.setStrokeColor(color)
        canvas.setLineWidth(12)
        # Рисуем дугу
        from reportlab.graphics.shapes import Wedge
        canvas.arc(
            cx - radius, cy - radius,
            cx + radius, cy + radius,
            start_angle, extent
        )
        
        # Балл в центре
        canvas.setFillColor(Colors.TEXT_PRIMARY)
        canvas.setFont(FONT_BOLD, 42)
        canvas.drawCentredString(cx, cy + 5, str(self.score))
        
        # Подпись "из 100"
        canvas.setFillColor(Colors.TEXT_SECONDARY)
        canvas.setFont(FONT_REGULAR, 11)
        canvas.drawCentredString(cx, cy - 18, self.label)
        
        # Дополнительная подпись (уровень)
        if self.sublabel:
            canvas.setFillColor(color)
            canvas.setFont(FONT_SEMIBOLD, 10)
            canvas.drawCentredString(cx, cy - 32, self.sublabel)


class CategoryBadge(Flowable):
    """Цветной badge для категории с баллом."""
    
    def __init__(
        self, 
        score: int, 
        max_score: int, 
        label: str,
        color: colors.Color,
        width: float = 70,
        height: float = 55,
    ):
        Flowable.__init__(self)
        self.score = score
        self.max_score = max_score
        self.label = label
        self.color = color
        self.width = width
        self.height = height
    
    def draw(self):
        canvas = self.canv
        
        # Фон badge
        canvas.setFillColor(self.color)
        canvas.roundRect(0, 0, self.width, self.height, 8, stroke=0, fill=1)
        
        # Балл
        canvas.setFillColor(Colors.TEXT_WHITE)
        canvas.setFont(FONT_BOLD, 22)
        canvas.drawCentredString(self.width / 2, self.height - 25, str(self.score))
        
        # Максимум
        canvas.setFont(FONT_REGULAR, 9)
        canvas.drawCentredString(self.width / 2, self.height - 38, f"/ {self.max_score}")
        
        # Подпись
        canvas.setFont(FONT_REGULAR, 8)
        canvas.drawCentredString(self.width / 2, 6, self.label)


class ProgressBar(Flowable):
    """Цветной progress bar."""
    
    def __init__(
        self, 
        value: float, 
        max_value: float, 
        width: float = 120, 
        height: float = 12,
        color: colors.Color = None,
        show_value: bool = True,
        label: str = "",
    ):
        Flowable.__init__(self)
        self.value = value
        self.max_value = max_value
        self.width = width
        self.height = height
        self.show_value = show_value
        self.label = label
        
        # Автоцвет по значению
        if color:
            self.color = color
        else:
            pct = value / max_value if max_value > 0 else 0
            if pct >= 0.8:
                self.color = Colors.EXCELLENT
            elif pct >= 0.6:
                self.color = Colors.GOOD
            elif pct >= 0.4:
                self.color = Colors.AVERAGE
            else:
                self.color = Colors.LOW
    
    def draw(self):
        canvas = self.canv
        
        label_width = 0
        if self.label:
            canvas.setFont(FONT_NAME, 8)
            canvas.setFillColor(Colors.TEXT_SECONDARY)
            canvas.drawString(0, self.height / 2 - 3, self.label)
            label_width = 80
        
        bar_x = label_width
        bar_width = self.width - label_width - (25 if self.show_value else 0)
        
        # Фон
        canvas.setFillColor(Colors.LIGHT_BG)
        canvas.roundRect(bar_x, 0, bar_width, self.height, 3, stroke=0, fill=1)
        
        # Заполненная часть
        fill_width = bar_width * (self.value / self.max_value) if self.max_value > 0 else 0
        if fill_width > 0:
            canvas.setFillColor(self.color)
            canvas.roundRect(bar_x, 0, fill_width, self.height, 3, stroke=0, fill=1)
        
        # Значение
        if self.show_value:
            canvas.setFont(FONT_BOLD, 9)
            canvas.setFillColor(Colors.TEXT_PRIMARY)
            canvas.drawString(bar_x + bar_width + 5, self.height / 2 - 3, f"{self.value:.1f}")


class ScoreCard(Flowable):
    """Премиальная карточка с баллом категории."""
    
    def __init__(
        self, 
        title: str, 
        score: int, 
        max_score: int,
        color: colors.Color,
        width: float = 45,
        height: float = 55,
    ):
        Flowable.__init__(self)
        self.title = title
        self.score = score
        self.max_score = max_score
        self.color = color
        self.width = width
        self.height = height
    
    def draw(self):
        canvas = self.canv
        
        # Фон карточки с закруглёнными углами
        canvas.setFillColor(self.color)
        canvas.roundRect(0, 0, self.width, self.height, 8, stroke=0, fill=1)
        
        # Балл (крупный, белый)
        canvas.setFillColor(Colors.TEXT_WHITE)
        canvas.setFont(FONT_BOLD, 22)
        canvas.drawCentredString(self.width / 2, self.height - 26, str(self.score))
        
        # Максимум (меньше, полупрозрачный)
        canvas.setFillColor(colors.Color(1, 1, 1, alpha=0.8))
        canvas.setFont(FONT_REGULAR, 10)
        canvas.drawCentredString(self.width / 2, self.height - 40, f"/ {self.max_score}")
        
        # Название категории (внизу)
        canvas.setFillColor(Colors.TEXT_WHITE)
        canvas.setFont(FONT_MEDIUM, 8)
        canvas.drawCentredString(self.width / 2, 8, self.title)


class TotalScoreWidget(Flowable):
    """Премиальный виджет общего балла с круговым прогрессом."""
    
    def __init__(self, score: int, level: str, width: float = 100, height: float = 100):
        Flowable.__init__(self)
        self.score = score
        self.level = level
        self.width = width
        self.height = height
    
    def draw(self):
        canvas = self.canv
        
        # Определяем цвет по баллу
        if self.score >= 80:
            color = Colors.EXCELLENT
            gradient_color = colors.HexColor('#059669')  # Darker green
        elif self.score >= 60:
            color = Colors.GOOD
            gradient_color = colors.HexColor('#2563EB')
        elif self.score >= 40:
            color = Colors.AVERAGE
            gradient_color = colors.HexColor('#D97706')
        else:
            color = Colors.LOW
            gradient_color = colors.HexColor('#DC2626')
        
        cx, cy = self.width / 2, self.height / 2
        radius = min(self.width, self.height) / 2 - 8
        
        # Фоновый круг (тонкий, серый)
        canvas.setStrokeColor(Colors.BORDER)
        canvas.setLineWidth(10)
        canvas.circle(cx, cy, radius, stroke=1, fill=0)
        
        # Прогресс-дуга (толстая, цветная)
        canvas.setStrokeColor(color)
        canvas.setLineWidth(10)
        canvas.setLineCap(1)  # Rounded ends
        
        # Рисуем дугу (от 90° против часовой стрелки)
        angle = 360 * (self.score / 100)
        canvas.arc(
            cx - radius, cy - radius,
            cx + radius, cy + radius,
            90, -angle
        )
        
        # Балл в центре (крупный)
        canvas.setFillColor(Colors.TEXT_PRIMARY)
        canvas.setFont(FONT_BOLD, 36)
        canvas.drawCentredString(cx, cy + 8, str(self.score))
        
        # "из 100"
        canvas.setFont(FONT_REGULAR, 11)
        canvas.setFillColor(Colors.TEXT_SECONDARY)
        canvas.drawCentredString(cx, cy - 14, "из 100")
        
        # Уровень снизу (с подсветкой)
        canvas.setFont(FONT_SEMIBOLD, 10)
        canvas.setFillColor(color)
        canvas.drawCentredString(cx, 3, self.level)


class BenchmarkBar(Flowable):
    """Визуальное сравнение с бенчмарком."""
    
    def __init__(
        self,
        user_score: int,
        avg_score: float,
        label: str = "Ваш результат vs Среднее",
        width: float = 150,
        height: float = 30,
    ):
        Flowable.__init__(self)
        self.user_score = user_score
        self.avg_score = avg_score
        self.label = label
        self.width = width
        self.height = height
    
    def draw(self):
        canvas = self.canv
        
        bar_y = 10
        bar_height = 12
        
        # Подпись
        canvas.setFont(FONT_NAME, 7)
        canvas.setFillColor(Colors.TEXT_SECONDARY)
        canvas.drawString(0, self.height - 5, self.label)
        
        # Фон бара
        canvas.setFillColor(Colors.LIGHT_BG)
        canvas.roundRect(0, bar_y, self.width, bar_height, 3, stroke=0, fill=1)
        
        # Среднее (серый)
        avg_x = self.width * (self.avg_score / 100)
        canvas.setFillColor(Colors.TEXT_MUTED)
        canvas.roundRect(0, bar_y, avg_x, bar_height, 3, stroke=0, fill=1)
        
        # Юзер (цветной)
        user_x = self.width * (self.user_score / 100)
        if self.user_score >= self.avg_score:
            color = Colors.EXCELLENT
        else:
            color = Colors.AVERAGE
        
        canvas.setFillColor(color)
        canvas.roundRect(0, bar_y, user_x, bar_height, 3, stroke=0, fill=1)
        
        # Маркер среднего
        canvas.setStrokeColor(Colors.TEXT_PRIMARY)
        canvas.setLineWidth(2)
        canvas.line(avg_x, bar_y - 2, avg_x, bar_y + bar_height + 2)
        
        # Подписи значений
        canvas.setFont(FONT_NAME, 6)
        canvas.setFillColor(Colors.TEXT_SECONDARY)
        canvas.drawCentredString(avg_x, 2, f"Ср: {self.avg_score:.0f}")
        
        canvas.setFillColor(color)
        canvas.setFont(FONT_BOLD, 7)
        canvas.drawString(self.width + 5, bar_y + 2, f"{self.user_score}")


# ========================================
# ОСНОВНОЙ ГЕНЕРАТОР
# ========================================

def generate_pdf_report(
    role_name: str,
    experience: str,
    scores: dict,
    report_text: str,
    conversation_history: list[dict],
    user_name: str = "Кандидат",
    profile_data: dict | None = None,
    pdp_data: dict | None = None,
    benchmark_data: dict | None = None,
    raw_averages: dict | None = None,
) -> bytes:
    """
    Сгенерировать красивый PDF-отчёт.
    
    Args:
        role_name: Название роли
        experience: Опыт
        scores: Баллы по категориям
        report_text: Текст отчёта (HTML)
        conversation_history: История диалога
        user_name: Имя пользователя
        profile_data: Данные профиля компетенций
        pdp_data: Данные PDP
        benchmark_data: Данные бенчмарка
        raw_averages: Сырые средние по 12 метрикам
        
    Returns:
        PDF как bytes
    """
    buffer = io.BytesIO()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=15*mm,
        bottomMargin=15*mm,
    )
    
    # Стили
    styles = getSampleStyleSheet()
    
    # Кастомные стили
    title_style = ParagraphStyle(
        'Title',
        fontName=FONT_BOLD,
        fontSize=28,
        leading=32,
        textColor=Colors.PRIMARY,
        spaceAfter=5,
    )
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        fontName=FONT_NAME,
        fontSize=12,
        textColor=Colors.TEXT_SECONDARY,
        spaceAfter=20,
    )
    
    heading_style = ParagraphStyle(
        'Heading',
        fontName=FONT_BOLD,
        fontSize=14,
        textColor=Colors.PRIMARY,
        spaceBefore=15,
        spaceAfter=10,
        borderPadding=5,
    )
    
    subheading_style = ParagraphStyle(
        'Subheading',
        fontName=FONT_BOLD,
        fontSize=11,
        textColor=Colors.SECONDARY,
        spaceBefore=10,
        spaceAfter=5,
    )
    
    body_style = ParagraphStyle(
        'Body',
        fontName=FONT_NAME,
        fontSize=9,
        leading=13,
        textColor=Colors.TEXT_PRIMARY,
        spaceAfter=4,
    )
    
    small_style = ParagraphStyle(
        'Small',
        fontName=FONT_NAME,
        fontSize=8,
        textColor=Colors.TEXT_SECONDARY,
    )
    
    accent_style = ParagraphStyle(
        'Accent',
        fontName=FONT_BOLD,
        fontSize=10,
        textColor=Colors.HIGHLIGHT,
        spaceBefore=5,
        spaceAfter=5,
    )
    
    # Элементы документа
    elements = []
    
    total = scores.get('total', 0)
    
    # Определяем уровень
    if total >= 80:
        level = "Senior / Lead"
        level_emoji = "🏆"
    elif total >= 60:
        level = "Middle+"
        level_emoji = "💪"
    elif total >= 40:
        level = "Middle"
        level_emoji = "📈"
    else:
        level = "Junior / Junior+"
        level_emoji = "🌱"
    
    # ========================================
    # СТРАНИЦА 1: ТИТУЛЬНАЯ
    # ========================================
    
    # Большой заголовок
    big_title_style = ParagraphStyle(
        'BigTitle',
        fontName=FONT_BOLD,
        fontSize=36,
        leading=40,
        textColor=Colors.PRIMARY,
        alignment=TA_CENTER,
        spaceAfter=5,
    )
    elements.append(Spacer(1, 20*mm))
    elements.append(Paragraph("DEEP DIAGNOSTIC", big_title_style))
    
    # Подзаголовок
    tagline_style = ParagraphStyle(
        'Tagline',
        fontName=FONT_NAME,
        fontSize=14,
        textColor=Colors.TEXT_SECONDARY,
        alignment=TA_CENTER,
        spaceAfter=25,
    )
    elements.append(Paragraph("Профессиональная диагностика специалиста", tagline_style))
    
    # Дата отчёта
    date_style = ParagraphStyle(
        'Date',
        fontName=FONT_NAME,
        fontSize=10,
        textColor=Colors.TEXT_MUTED,
        alignment=TA_CENTER,
        spaceAfter=15,
    )
    elements.append(Paragraph(datetime.now().strftime('%d %B %Y').replace(
        'January', 'Января').replace('February', 'Февраля').replace('March', 'Марта').replace(
        'April', 'Апреля').replace('May', 'Мая').replace('June', 'Июня').replace(
        'July', 'Июля').replace('August', 'Августа').replace('September', 'Сентября').replace(
        'October', 'Октября').replace('November', 'Ноября').replace('December', 'Декабря'
    ), date_style))
    
    elements.append(Spacer(1, 10*mm))
    
    # Информация о кандидате (карточка)
    info_data = [
        [Paragraph(f"<b>{user_name}</b>", body_style)],
        [Paragraph(f"{role_name} • {experience}", small_style)],
    ]
    
    info_table = Table(info_data, colWidths=[120*mm])
    info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (0, 0), (-1, -1), Colors.LIGHT_BG),
        ('BOX', (0, 0), (-1, -1), 1, Colors.PRIMARY),
        ('ROUNDEDCORNERS', [5, 5, 5, 5]),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 15*mm))
    
    # ========================================
    # СЕКЦИЯ: ОБЩИЙ РЕЗУЛЬТАТ
    # ========================================
    
    elements.append(Paragraph("ОБЩИЙ РЕЗУЛЬТАТ", heading_style))
    
    # Виджеты баллов (на русском)
    score_widgets = Table(
        [[
            TotalScoreWidget(total, level, width=80, height=80),
            Spacer(10, 1),
            Table([
                [
                    ScoreCard("Hard", scores.get('hard_skills', 0), 30, Colors.HARD_SKILLS, width=42, height=52),
                    ScoreCard("Soft", scores.get('soft_skills', 0), 25, Colors.SOFT_SKILLS, width=42, height=52),
                    ScoreCard("Think", scores.get('thinking', 0), 25, Colors.THINKING, width=42, height=52),
                    ScoreCard("Mind", scores.get('mindset', 0), 20, Colors.MINDSET, width=42, height=52),
                ]
            ], colWidths=[44*mm, 44*mm, 44*mm, 44*mm]),
        ]],
        colWidths=[85*mm, 5*mm, 90*mm]
    )
    score_widgets.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
    ]))
    elements.append(score_widgets)
    elements.append(Spacer(1, 8*mm))
    
    # Бенчмарк (если есть)
    if benchmark_data:
        avg_score = benchmark_data.get("avg_score", 50)
        elements.append(
            BenchmarkBar(total, avg_score, "Твой результат vs Среднее", width=170, height=28)
        )
        elements.append(Spacer(1, 5*mm))
    
    # ========================================
    # СЕКЦИЯ: RADAR CHART КОМПЕТЕНЦИЙ
    # ========================================
    
    if raw_averages:
        elements.append(Paragraph("КАРТА КОМПЕТЕНЦИЙ", heading_style))
        
        # Radar chart + легенда
        radar_section = Table(
            [[
                RadarChart(raw_averages, width=160, height=160),
                Spacer(10, 1),
                # Легенда с progress bars
                Table([
                    [ProgressBar(raw_averages.get("expertise", 5), 10, width=100, height=10, label="Экспертиза", color=Colors.HARD_SKILLS)],
                    [ProgressBar(raw_averages.get("methodology", 5), 10, width=100, height=10, label="Методология", color=Colors.HARD_SKILLS)],
                    [ProgressBar(raw_averages.get("tools_proficiency", 5), 10, width=100, height=10, label="Инструменты", color=Colors.HARD_SKILLS)],
                    [Spacer(1, 3)],
                    [ProgressBar(raw_averages.get("articulation", 5), 10, width=100, height=10, label="Коммуникация", color=Colors.SOFT_SKILLS)],
                    [ProgressBar(raw_averages.get("self_awareness", 5), 10, width=100, height=10, label="Самосознание", color=Colors.SOFT_SKILLS)],
                    [ProgressBar(raw_averages.get("conflict_handling", 5), 10, width=100, height=10, label="Конфликты", color=Colors.SOFT_SKILLS)],
                    [Spacer(1, 3)],
                    [ProgressBar(raw_averages.get("depth", 5), 10, width=100, height=10, label="Глубина", color=Colors.THINKING)],
                    [ProgressBar(raw_averages.get("structure", 5), 10, width=100, height=10, label="Структура", color=Colors.THINKING)],
                    [ProgressBar(raw_averages.get("systems_thinking", 5), 10, width=100, height=10, label="Системность", color=Colors.THINKING)],
                    [ProgressBar(raw_averages.get("creativity", 5), 10, width=100, height=10, label="Креативность", color=Colors.THINKING)],
                    [Spacer(1, 3)],
                    [ProgressBar(raw_averages.get("honesty", 5), 10, width=100, height=10, label="Честность", color=Colors.MINDSET)],
                    [ProgressBar(raw_averages.get("growth_orientation", 5), 10, width=100, height=10, label="Рост", color=Colors.MINDSET)],
                ], colWidths=[110*mm]),
            ]],
            colWidths=[90*mm, 5*mm, 85*mm]
        )
        radar_section.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(radar_section)
        elements.append(Spacer(1, 8*mm))
    
    # ========================================
    # СЕКЦИЯ: ПРОФИЛЬ КОМПЕТЕНЦИЙ
    # ========================================
    
    if profile_data:
        elements.append(Paragraph("ПРОФИЛЬ КОМПЕТЕНЦИЙ", heading_style))
        
        # Две колонки: сильные стороны + зоны роста
        strengths = profile_data.get("strengths", [])
        growth = profile_data.get("growth_areas", [])
        
        col1_content = []
        col2_content = []
        
        col1_content.append(Paragraph("<b>💪 Сильные стороны</b>", subheading_style))
        for s in strengths[:3]:
            col1_content.append(Paragraph(f"• {s}", body_style))
        
        col2_content.append(Paragraph("<b>📈 Зоны развития</b>", subheading_style))
        for g in growth[:3]:
            col2_content.append(Paragraph(f"• {g}", body_style))
        
        profile_cols = Table(
            [[col1_content, col2_content]],
            colWidths=[90*mm, 90*mm]
        )
        profile_cols.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(profile_cols)
        elements.append(Spacer(1, 5*mm))
        
        # Стили мышления
        thinking_style = profile_data.get("thinking_style", "")
        comm_style = profile_data.get("communication_style", "")
        
        if thinking_style or comm_style:
            styles_data = []
            if thinking_style:
                styles_data.append(["🧠 Стиль мышления:", thinking_style[:80]])
            if comm_style:
                styles_data.append(["💬 Коммуникация:", comm_style[:80]])
            
            styles_table = Table(styles_data, colWidths=[45*mm, 135*mm])
            styles_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), FONT_BOLD),
                ('FONTNAME', (1, 0), (1, -1), FONT_NAME),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('TEXTCOLOR', (0, 0), (-1, -1), Colors.TEXT_PRIMARY),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            elements.append(styles_table)
    
    # ========================================
    # СТРАНИЦА 2: PDP
    # ========================================
    
    if pdp_data:
        elements.append(PageBreak())
        elements.append(Paragraph("ПЛАН РАЗВИТИЯ НА 30 ДНЕЙ", heading_style))
        
        # Главный фокус (без эмодзи)
        main_focus = pdp_data.get("main_focus", "")
        if main_focus:
            elements.append(Paragraph(f"<b>Главный фокус:</b> {main_focus}", body_style))
            elements.append(Spacer(1, 5*mm))
        
        # Приоритетные цели
        primary_goals = pdp_data.get("primary_goals", [])
        if primary_goals:
            elements.append(Paragraph("<b>Приоритетные зоны развития</b>", subheading_style))
            
            for i, goal in enumerate(primary_goals[:3], 1):
                metric_name = goal.get("metric_name", "")
                current = goal.get("current_score", 0)
                target = goal.get("target_score", 0)
                priority_reason = goal.get("priority_reason", "")
                timeline = goal.get("timeline", "")
                
                # Заголовок цели
                goal_header = f"<b>{i}. {metric_name}</b>"
                elements.append(Paragraph(goal_header, body_style))
                
                # Прогресс
                progress_text = f"   Текущий уровень: {current:.1f}/10 → Цель: {target:.1f}/10"
                elements.append(Paragraph(progress_text, small_style))
                
                if priority_reason:
                    elements.append(Paragraph(f"   Почему важно: {priority_reason[:100]}", small_style))
                if timeline:
                    elements.append(Paragraph(f"   Срок: {timeline}", small_style))
                
                # Действия
                actions = goal.get("actions", [])
                if actions:
                    elements.append(Paragraph("   <b>Что делать:</b>", small_style))
                    for action in actions[:3]:
                        action_text = action.get("action", "") if isinstance(action, dict) else str(action)
                        if action_text:
                            elements.append(Paragraph(f"   • {action_text[:80]}", small_style))
                
                # Ресурсы для этой цели
                resources = goal.get("resources", [])
                if resources:
                    elements.append(Paragraph("   <b>Ресурсы:</b>", small_style))
                    for res in resources[:2]:
                        res_title = res.get("title", "") if isinstance(res, dict) else str(res)
                        res_author = res.get("author", "") if isinstance(res, dict) else ""
                        res_type = res.get("type", "") if isinstance(res, dict) else ""
                        type_icon = {"book": "[Книга]", "course": "[Курс]", "practice": "[Практика]", "tool": "[Инструмент]"}.get(res_type, "")
                        res_line = f"   • {type_icon} {res_title}"
                        if res_author:
                            res_line += f" — {res_author}"
                        elements.append(Paragraph(res_line[:100], small_style))
                
                elements.append(Spacer(1, 3*mm))
            
            elements.append(Spacer(1, 5*mm))
        
        # План на 30 дней (только один срок)
        plan_30 = pdp_data.get("plan_30_days", [])
        if plan_30:
            elements.append(Paragraph("<b>План действий (30 дней)</b>", subheading_style))
            for i, item in enumerate(plan_30[:6], 1):
                # Убираем эмодзи
                clean_item = item.lstrip("📚✅🎯▸• ")
                elements.append(Paragraph(f"{i}. {clean_item}", body_style))
        
        # Метрики успеха
        success_metrics = pdp_data.get("success_metrics", [])
        if success_metrics:
            elements.append(Spacer(1, 5*mm))
            elements.append(Paragraph("<b>📈 Как измерить успех</b>", subheading_style))
            for item in success_metrics[:4]:
                clean_item = item.lstrip("📈✅🔄📚▸• ")
                elements.append(Paragraph(f"• {clean_item}", body_style))
    
    # ========================================
    # СТРАНИЦА 3: ДЕТАЛЬНЫЙ АНАЛИЗ
    # ========================================
    
    elements.append(PageBreak())
    elements.append(Paragraph("ДЕТАЛЬНЫЙ АНАЛИЗ", heading_style))
    
    # Очищаем HTML теги и конвертируем
    clean_report = report_text
    clean_report = clean_report.replace('━', '—')
    clean_report = clean_report.replace('•', '•')
    clean_report = clean_report.replace('▸', '•')
    
    # Убираем лишние эмодзи для PDF
    import re
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE
    )
    clean_report = emoji_pattern.sub('', clean_report)
    
    # Разбиваем на параграфы
    paragraphs = clean_report.split('\n\n')
    for para in paragraphs:
        if para.strip():
            para = para.replace('\n', ' ').strip()
            if para:
                try:
                    elements.append(Paragraph(para, body_style))
                except Exception:
                    elements.append(Paragraph(
                        para.replace('<', '&lt;').replace('>', '&gt;'),
                        body_style
                    ))
    
    # ========================================
    # СТРАНИЦА 4: ИСТОРИЯ ДИАЛОГА (опционально)
    # ========================================
    
    if conversation_history and len(conversation_history) > 0:
        elements.append(PageBreak())
        elements.append(Paragraph("ИСТОРИЯ ДИАЛОГА", heading_style))
        elements.append(Paragraph(
            "Полная запись вопросов и ответов диагностики",
            small_style
        ))
        elements.append(Spacer(1, 5*mm))
        
        for i, item in enumerate(conversation_history, 1):
            # Вопрос
            q_style = ParagraphStyle(
                'Question',
                fontName=FONT_BOLD,
                fontSize=9,
                textColor=Colors.SECONDARY,
                spaceBefore=8,
                spaceAfter=3,
            )
            question = item.get('question', '')[:200]
            elements.append(Paragraph(f"Вопрос {i}: {question}", q_style))
            
            # Ответ
            answer = item.get('answer', '')[:400]
            if len(item.get('answer', '')) > 400:
                answer += "..."
            
            a_style = ParagraphStyle(
                'Answer',
                fontName=FONT_NAME,
                fontSize=8,
                textColor=Colors.TEXT_PRIMARY,
                leftIndent=10,
                spaceAfter=5,
                leading=11,
            )
            elements.append(Paragraph(answer, a_style))
    
    # ========================================
    # СТРАНИЦА: МЕТОДОЛОГИЯ
    # ========================================
    
    elements.append(PageBreak())
    elements.append(Paragraph("МЕТОДОЛОГИЯ ОЦЕНКИ", heading_style))
    
    methodology_intro = ParagraphStyle(
        'MethodologyIntro',
        fontName=FONT_NAME,
        fontSize=9,
        textColor=Colors.TEXT_SECONDARY,
        spaceAfter=10,
    )
    elements.append(Paragraph(
        "Диагностика основана на анализе ответов по 12 ключевым метрикам, "
        "сгруппированным в 4 категории. AI-модель оценивает глубину, структуру "
        "и содержание каждого ответа.",
        methodology_intro
    ))
    
    # Категории с описаниями
    categories_info = [
        ("Профессиональные навыки (30 баллов)", [
            "Экспертиза — глубина знаний в своей области",
            "Методология — владение фреймворками и процессами",
            "Инструменты — практическое владение инструментарием",
        ]),
        ("Коммуникация (25 баллов)", [
            "Артикуляция — ясность изложения мыслей",
            "Самосознание — понимание своих сильных и слабых сторон",
            "Работа с конфликтами — умение находить компромиссы",
        ]),
        ("Мышление (25 баллов)", [
            "Глубина — способность к детальному анализу",
            "Структура — логичность и последовательность",
            "Системность — видение связей и закономерностей",
            "Креативность — нестандартные подходы",
        ]),
        ("Майндсет (20 баллов)", [
            "Честность — искренность и аутентичность ответов",
            "Ориентация на рост — стремление к развитию",
        ]),
    ]
    
    for cat_title, metrics in categories_info:
        elements.append(Paragraph(f"<b>{cat_title}</b>", subheading_style))
        for metric in metrics:
            elements.append(Paragraph(f"• {metric}", body_style))
    
    elements.append(Spacer(1, 8*mm))
    
    # Disclaimer
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        fontName=FONT_NAME,
        fontSize=8,
        textColor=Colors.TEXT_MUTED,
        spaceAfter=5,
        backColor=Colors.LIGHT_BG,
        leftIndent=5,
        rightIndent=5,
        borderPadding=5,
    )
    elements.append(Paragraph(
        "<b>Важно:</b> Результаты диагностики носят рекомендательный характер. "
        "Они основаны на анализе текстовых ответов и могут не отражать полную картину компетенций. "
        "Для комплексной оценки рекомендуется использовать дополнительные методы.",
        disclaimer_style
    ))
    
    # ========================================
    # ФУТЕР
    # ========================================
    
    elements.append(Spacer(1, 15*mm))
    
    footer_style = ParagraphStyle(
        'Footer',
        fontName=FONT_NAME,
        fontSize=8,
        textColor=Colors.TEXT_MUTED,
        alignment=TA_CENTER,
    )
    elements.append(Paragraph(
        f"Сгенерировано Deep Diagnostic Bot • {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        footer_style
    ))
    elements.append(Paragraph(
        "Этот отчёт создан с использованием AI-технологий",
        footer_style
    ))
    
    # Генерируем PDF
    doc.build(elements)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes
