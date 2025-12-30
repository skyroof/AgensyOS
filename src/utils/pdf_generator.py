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
import os
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

# Шрифты: приоритет Montserrat, fallback DejaVu (Linux) / Arial (Windows)
FONT_PATHS = {
    "regular": [
        # Docker / Linux Montserrat
        "/app/assets/fonts/Montserrat-Regular.ttf",
        "/usr/share/fonts/truetype/montserrat/Montserrat-Regular.ttf",
        # Windows Montserrat (установленный в систему)
        "C:/Windows/Fonts/Montserrat-Regular.ttf",
        # Local assets
        "assets/fonts/Montserrat-Regular.ttf",
        # Fallback: DejaVu (Linux) / Arial (Windows)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ],
    "medium": [
        "/app/assets/fonts/Montserrat-Medium.ttf",
        "/usr/share/fonts/truetype/montserrat/Montserrat-Medium.ttf",
        "C:/Windows/Fonts/Montserrat-Medium.ttf",
        "assets/fonts/Montserrat-Medium.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ],
    "semibold": [
        "/app/assets/fonts/Montserrat-SemiBold.ttf",
        "/usr/share/fonts/truetype/montserrat/Montserrat-SemiBold.ttf",
        "C:/Windows/Fonts/Montserrat-SemiBold.ttf",
        "assets/fonts/Montserrat-SemiBold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ],
    "bold": [
        # Docker / Linux Montserrat
        "/app/assets/fonts/Montserrat-Bold.ttf",
        "/usr/share/fonts/truetype/montserrat/Montserrat-Bold.ttf",
        # Windows Montserrat
        "C:/Windows/Fonts/Montserrat-Bold.ttf",
        # Local assets
        "assets/fonts/Montserrat-Bold.ttf",
        # Fallback
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
                logger.info(f"Registered font '{name}': {path}")
                return name
            except Exception as e:
                logger.warning(f"Failed to register {path}: {e}")
    return None

# Регистрация шрифтов
try:
    # Пытаемся зарегистрировать шрифты по порядку приоритета
    if reg := register_font('CustomFont', FONT_PATHS["regular"]):
        FONT_REGULAR = reg
        FONT_NAME = reg
        logger.info(f"Using font: {reg}")
    
    if reg := register_font('CustomFont-Medium', FONT_PATHS["medium"]):
        FONT_MEDIUM = reg
    else:
        FONT_MEDIUM = FONT_REGULAR
        
    if reg := register_font('CustomFont-SemiBold', FONT_PATHS["semibold"]):
        FONT_SEMIBOLD = reg
    else:
        FONT_SEMIBOLD = FONT_REGULAR
        
    if reg := register_font('CustomFont-Bold', FONT_PATHS["bold"]):
        FONT_BOLD = reg
    else:
        FONT_BOLD = FONT_REGULAR
        
    # Регистрируем font family
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    if FONT_REGULAR != 'Helvetica':
        try:
            registerFontFamily(
                'CustomFont',
                normal=FONT_REGULAR,
                bold=FONT_BOLD,
            )
            logger.info(f"Font family registered: {FONT_REGULAR}/{FONT_BOLD}")
        except:
            pass
            
except Exception as e:
    logger.warning(f"Font registration error: {e}")

# Aliases для совместимости (уже обновлено выше)
# FONT_NAME устанавливается при регистрации шрифта


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
        
        # BENCHMARK: серый полигон для среднего (5.0)
        benchmark_value = 5.0
        benchmark_points = []
        for i, _ in enumerate(metric_order):
            angle = -math.pi / 2 + i * angle_step
            r = self.radius * (benchmark_value / 10)
            x = self.center_x + r * math.cos(angle)
            y = self.center_y + r * math.sin(angle)
            benchmark_points.append((x, y))
        
        # Заливка benchmark (серая, полупрозрачная)
        bench_path = canvas.beginPath()
        bench_path.moveTo(benchmark_points[0][0], benchmark_points[0][1])
        for x, y in benchmark_points[1:]:
            bench_path.lineTo(x, y)
        bench_path.close()
        
        canvas.setFillColor(colors.Color(0.7, 0.7, 0.7, alpha=0.15))
        canvas.setStrokeColor(Colors.TEXT_MUTED)
        canvas.setLineWidth(1)
        canvas.setDash([3, 3])  # Пунктирная линия
        canvas.drawPath(bench_path, stroke=1, fill=1)
        canvas.setDash([])  # Сброс пунктира
        
        # Рисуем полигон значений пользователя
        points = []
        for i, (metric_key, _) in enumerate(metric_order):
            value = self.metrics.get(metric_key, 5)
            angle = -math.pi / 2 + i * angle_step
            r = self.radius * (value / 10)
            x = self.center_x + r * math.cos(angle)
            y = self.center_y + r * math.sin(angle)
            points.append((x, y))
        
        # Заливка полигона (градиент синий)
        path = canvas.beginPath()
        path.moveTo(points[0][0], points[0][1])
        for x, y in points[1:]:
            path.lineTo(x, y)
        path.close()
        
        canvas.setFillColor(colors.Color(0.39, 0.4, 0.95, alpha=0.25))  # Indigo
        canvas.setStrokeColor(Colors.HARD_SKILLS)
        canvas.setLineWidth(2.5)
        canvas.drawPath(path, stroke=1, fill=1)
        
        # Точки на вершинах (с цветовой кодировкой)
        for i, (metric_key, _) in enumerate(metric_order):
            value = self.metrics.get(metric_key, 5)
            x, y = points[i]
            
            # Цвет по значению
            if value >= 7:
                dot_color = Colors.EXCELLENT
            elif value >= 5:
                dot_color = Colors.AVERAGE
            else:
                dot_color = Colors.LOW
            
            canvas.setFillColor(dot_color)
            canvas.circle(x, y, 4, stroke=0, fill=1)
            # Белая обводка
            canvas.setStrokeColor(Colors.CARD_BG)
            canvas.setLineWidth(1.5)
            canvas.circle(x, y, 4, stroke=1, fill=0)


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


class SectionDivider(Flowable):
    """Визуальный разделитель между секциями."""
    
    def __init__(self, width: float = 180*mm, style: str = "line"):
        Flowable.__init__(self)
        self.width = width
        self.height = 15
        self.style = style  # "line", "dots", "gradient"
    
    def draw(self):
        canvas = self.canv
        y = self.height / 2
        
        if self.style == "line":
            # Простая линия с градиентом от краёв
            canvas.setStrokeColor(Colors.BORDER)
            canvas.setLineWidth(1)
            canvas.line(self.width * 0.1, y, self.width * 0.9, y)
            
        elif self.style == "dots":
            # Точки
            canvas.setFillColor(Colors.TEXT_MUTED)
            for i in range(5):
                x = self.width / 2 - 20 + i * 10
                canvas.circle(x, y, 2, stroke=0, fill=1)
                
        elif self.style == "gradient":
            # Акцентная линия
            canvas.setStrokeColor(Colors.ACCENT)
            canvas.setLineWidth(2)
            canvas.line(self.width * 0.3, y, self.width * 0.7, y)


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
        canvas.roundRect(0, 0, self.width, self.height, 6, stroke=0, fill=1)
        
        # Балл (крупный, белый) — пропорционально размеру
        canvas.setFillColor(Colors.TEXT_WHITE)
        font_score = self.width * 0.4
        canvas.setFont(FONT_BOLD, font_score)
        canvas.drawCentredString(self.width / 2, self.height * 0.55, str(self.score))
        
        # Максимум — под баллом
        canvas.setFillColor(colors.Color(1, 1, 1, alpha=0.7))
        font_max = self.width * 0.18
        canvas.setFont(FONT_REGULAR, font_max)
        canvas.drawCentredString(self.width / 2, self.height * 0.35, f"/{self.max_score}")
        
        # Название категории (внизу)
        canvas.setFillColor(Colors.TEXT_WHITE)
        font_title = self.width * 0.14
        canvas.setFont(FONT_MEDIUM, font_title)
        canvas.drawCentredString(self.width / 2, self.height * 0.08, self.title)


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
        
        # Балл в центре (с учетом baseline)
        canvas.setFillColor(Colors.TEXT_PRIMARY)
        font_size = self.width * 0.32
        canvas.setFont(FONT_BOLD, font_size)
        # Смещаем чуть ниже центра
        score_y = cy - font_size * 0.1
        canvas.drawCentredString(cx, score_y, str(self.score))
        
        # "из 100" — под баллом
        font_sub = self.width * 0.11
        canvas.setFont(FONT_REGULAR, font_sub)
        canvas.setFillColor(Colors.TEXT_SECONDARY)
        sub_y = score_y - font_size * 0.65
        canvas.drawCentredString(cx, sub_y, "из 100")


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
        
        # Пропорциональные размеры
        bar_height = self.height * 0.4
        bar_y = self.height * 0.2
        font_label = max(8, self.height * 0.2)
        font_value = max(9, self.height * 0.22)
        
        # Подпись сверху по центру
        canvas.setFont(FONT_NAME, font_label)
        canvas.setFillColor(Colors.TEXT_SECONDARY)
        canvas.drawCentredString(self.width / 2, self.height - font_label - 2, self.label)
        
        # Фон бара
        canvas.setFillColor(Colors.LIGHT_BG)
        canvas.roundRect(0, bar_y, self.width, bar_height, 4, stroke=0, fill=1)
        
        # Среднее (серый)
        avg_x = self.width * (self.avg_score / 100)
        canvas.setFillColor(Colors.TEXT_MUTED)
        canvas.roundRect(0, bar_y, avg_x, bar_height, 4, stroke=0, fill=1)
        
        # Юзер (цветной)
        user_x = self.width * (self.user_score / 100)
        if self.user_score >= self.avg_score:
            color = Colors.EXCELLENT
        else:
            color = Colors.AVERAGE
        
        canvas.setFillColor(color)
        canvas.roundRect(0, bar_y, user_x, bar_height, 4, stroke=0, fill=1)
        
        # Маркер среднего
        canvas.setStrokeColor(Colors.TEXT_PRIMARY)
        canvas.setLineWidth(2)
        canvas.line(avg_x, bar_y - 3, avg_x, bar_y + bar_height + 3)
        
        # Подпись среднего
        canvas.setFont(FONT_NAME, font_value * 0.8)
        canvas.setFillColor(Colors.TEXT_SECONDARY)
        canvas.drawCentredString(avg_x, 1, f"Ср: {self.avg_score:.0f}")
        
        # Значение пользователя справа
        canvas.setFillColor(color)
        canvas.setFont(FONT_BOLD, font_value)
        canvas.drawString(self.width + 8, bar_y + bar_height * 0.25, f"{self.user_score}")


# ========================================
# PAGE TEMPLATES (HEADER/FOOTER)
# ========================================

def _add_page_number(canvas, doc):
    """Добавляет номер страницы в footer."""
    page_num = canvas.getPageNumber()
    canvas.saveState()
    
    # Footer: номер страницы
    canvas.setFont(FONT_REGULAR, 9)
    canvas.setFillColor(Colors.TEXT_MUTED)
    canvas.drawCentredString(A4[0] / 2, 12*mm, f"— {page_num} —")
    
    # Footer: дата справа
    canvas.setFont(FONT_REGULAR, 7)
    canvas.drawRightString(A4[0] - 15*mm, 12*mm, datetime.now().strftime('%d.%m.%Y'))
    
    # Footer: бренд слева
    canvas.drawString(15*mm, 12*mm, "Deep Diagnostic")
    
    canvas.restoreState()


def _add_first_page(canvas, doc):
    """Header для первой страницы — тёмная полоса сверху."""
    canvas.saveState()
    
    # Тёмная полоса-header (gradient эффект)
    header_height = 25*mm
    canvas.setFillColor(Colors.PRIMARY)
    canvas.rect(0, A4[1] - header_height, A4[0], header_height, stroke=0, fill=1)
    
    # Акцентная линия под header
    canvas.setStrokeColor(Colors.ACCENT)
    canvas.setLineWidth(3)
    canvas.line(0, A4[1] - header_height, A4[0], A4[1] - header_height)
    
    canvas.restoreState()
    
    # Номер страницы
    _add_page_number(canvas, doc)


def _add_later_pages(canvas, doc):
    """Header для остальных страниц."""
    canvas.saveState()
    
    # Тонкая линия сверху
    canvas.setStrokeColor(Colors.BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(15*mm, A4[1] - 10*mm, A4[0] - 15*mm, A4[1] - 10*mm)
    
    canvas.restoreState()
    
    # Номер страницы
    _add_page_number(canvas, doc)


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
        topMargin=30*mm,  # Увеличен для header
        bottomMargin=20*mm,  # Место для footer
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
        alignment=TA_CENTER,
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
        level_emoji = "[S]"
    elif total >= 60:
        level = "Middle+"
        level_emoji = "[M+]"
    elif total >= 40:
        level = "Middle"
        level_emoji = "[M]"
    else:
        level = "Junior / Junior+"
        level_emoji = "[J]"
    
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
    
    # Виджеты баллов — большие плашки, компактные отступы
    score_widgets = Table([
        [
            TotalScoreWidget(total, level, width=75, height=75),
            ScoreCard("Hard", scores.get('hard_skills', 0), 30, Colors.HARD_SKILLS, width=55, height=70),
            ScoreCard("Soft", scores.get('soft_skills', 0), 25, Colors.SOFT_SKILLS, width=55, height=70),
            ScoreCard("Think", scores.get('thinking', 0), 25, Colors.THINKING, width=55, height=70),
            ScoreCard("Mind", scores.get('mindset', 0), 20, Colors.MINDSET, width=55, height=70),
        ]
    ], colWidths=[28*mm, 20*mm, 20*mm, 20*mm, 20*mm])
    score_widgets.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 1),
        ('RIGHTPADDING', (0, 0), (-1, -1), 1),
    ]))
    elements.append(score_widgets)
    elements.append(Spacer(1, 5*mm))
    
    # ========================================
    # СЕКЦИЯ: КЛЮЧЕВОЙ ИНСАЙТ + ТОП МЕТРИКИ
    # ========================================
    
    # Карточка с уровнем
    level_card_style = ParagraphStyle(
        'LevelCard',
        fontName=FONT_SEMIBOLD,
        fontSize=11,
        textColor=Colors.TEXT_PRIMARY,
        alignment=TA_CENTER,
    )
    
    # Определяем потенциал
    if total >= 70:
        potential = "Senior / Lead ready"
        potential_color = Colors.EXCELLENT
    elif total >= 50:
        potential = "Middle → Senior potential"
        potential_color = Colors.GOOD
    elif total >= 35:
        potential = "Junior+ → Middle path"
        potential_color = Colors.AVERAGE
    else:
        potential = "Active growth needed"
        potential_color = Colors.LOW
    
    level_text = f'<font color="{potential_color.hexval()}">{level_emoji} {potential}</font>'
    elements.append(Paragraph(level_text, level_card_style))
    elements.append(Spacer(1, 5*mm))
    
    # Топ-3 силы и слабости (если есть raw_averages)
    if raw_averages:
        # Сортируем метрики
        metric_names = {
            "expertise": "Экспертиза",
            "methodology": "Методология", 
            "tools_proficiency": "Инструменты",
            "articulation": "Коммуникация",
            "self_awareness": "Самосознание",
            "conflict_handling": "Конфликты",
            "depth": "Глубина мышления",
            "structure": "Структурность",
            "systems_thinking": "Системность",
            "creativity": "Креативность",
            "honesty": "Честность",
            "growth_orientation": "Рост",
        }
        
        sorted_metrics = sorted(raw_averages.items(), key=lambda x: x[1], reverse=True)
        top_3 = sorted_metrics[:3]
        bottom_3 = sorted_metrics[-3:]
        
        strengths_text = " • ".join([f"<b>{metric_names.get(k, k)}</b> ({v:.1f})" for k, v in top_3])
        gaps_text = " • ".join([f"{metric_names.get(k, k)} ({v:.1f})" for k, v in bottom_3])
        
        insight_style = ParagraphStyle(
            'Insight',
            fontName=FONT_REGULAR,
            fontSize=9,
            textColor=Colors.TEXT_SECONDARY,
            alignment=TA_CENTER,
            leading=13,
        )
        
        elements.append(Paragraph(f"[+] <b>Сильные:</b> {strengths_text}", insight_style))
        elements.append(Spacer(1, 2*mm))
        elements.append(Paragraph(f"[-] <b>К развитию:</b> {gaps_text}", insight_style))
        elements.append(Spacer(1, 5*mm))
    
    # Разделитель
    elements.append(SectionDivider(width=180*mm, style="dots"))
    elements.append(Spacer(1, 3*mm))
    
    # Бенчмарк (если есть)
    if benchmark_data:
        avg_score = benchmark_data.get("avg_score", 50)
        # Центрируем BenchmarkBar в таблице — большой размер
        benchmark_table = Table(
            [[BenchmarkBar(total, avg_score, "Ваш результат vs средний", width=320, height=45)]],
            colWidths=[180*mm]
        )
        benchmark_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        elements.append(benchmark_table)
        elements.append(Spacer(1, 8*mm))
    
    # ========================================
    # СЕКЦИЯ: RADAR CHART КОМПЕТЕНЦИЙ (новая страница)
    # ========================================
    
    if raw_averages:
        elements.append(PageBreak())
        elements.append(Paragraph("КАРТА КОМПЕТЕНЦИЙ", heading_style))
        elements.append(Spacer(1, 5*mm))
        
        # Метрики по категориям для легенды
        metrics_groups = [
            ("Hard Skills", Colors.HARD_SKILLS, [
                ("Экспертиза", raw_averages.get("expertise", 5)),
                ("Методология", raw_averages.get("methodology", 5)),
                ("Инструменты", raw_averages.get("tools_proficiency", 5)),
            ]),
            ("Soft Skills", Colors.SOFT_SKILLS, [
                ("Коммуникация", raw_averages.get("articulation", 5)),
                ("Самосознание", raw_averages.get("self_awareness", 5)),
                ("Конфликты", raw_averages.get("conflict_handling", 5)),
            ]),
            ("Thinking", Colors.THINKING, [
                ("Глубина", raw_averages.get("depth", 5)),
                ("Структура", raw_averages.get("structure", 5)),
                ("Системность", raw_averages.get("systems_thinking", 5)),
                ("Креативность", raw_averages.get("creativity", 5)),
            ]),
            ("Mindset", Colors.MINDSET, [
                ("Честность", raw_averages.get("honesty", 5)),
                ("Рост", raw_averages.get("growth_orientation", 5)),
            ]),
        ]
        
        # Создаем легенду с группировкой
        legend_rows = []
        for group_name, group_color, metrics in metrics_groups:
            for i, (name, value) in enumerate(metrics):
                # Цвет точки по значению
                if value >= 7:
                    dot_color = Colors.EXCELLENT
                elif value >= 5:
                    dot_color = Colors.AVERAGE
                else:
                    dot_color = Colors.LOW
                
                metric_style = ParagraphStyle(
                    f'Metric_{name}',
                    fontName=FONT_NAME,
                    fontSize=9,
                    textColor=Colors.TEXT_PRIMARY,
                )
                value_style = ParagraphStyle(
                    f'Value_{name}',
                    fontName=FONT_BOLD,
                    fontSize=10,
                    textColor=dot_color,
                    alignment=TA_RIGHT,
                )
                legend_rows.append([
                    Paragraph(name, metric_style),
                    Paragraph(f"<b>{value:.1f}</b>", value_style),
                ])
            # Разделитель между группами
            if group_name != "Mindset":
                legend_rows.append([Spacer(1, 4), Spacer(1, 4)])
        
        legend_table = Table(legend_rows, colWidths=[55*mm, 15*mm])
        legend_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        
        # Radar chart + легенда в одной таблице, центрировано
        radar_section = Table(
            [[RadarChart(raw_averages, width=180, height=180), legend_table]],
            colWidths=[95*mm, 75*mm]
        )
        radar_section.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        
        # Центрируем всю секцию
        centered_radar = Table([[radar_section]], colWidths=[180*mm])
        centered_radar.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        elements.append(centered_radar)
        elements.append(Spacer(1, 10*mm))
    
    # ========================================
    # СЕКЦИЯ: ПРОФИЛЬ КОМПЕТЕНЦИЙ
    # ========================================
    
    if profile_data:
        elements.append(Paragraph("ПРОФИЛЬ КОМПЕТЕНЦИЙ", heading_style))
        elements.append(Spacer(1, 8*mm))
        
        # Две колонки: сильные стороны + зоны роста
        strengths = profile_data.get("strengths", [])
        growth = profile_data.get("growth_areas", [])
        
        col1_content = []
        col2_content = []
        
        col1_content.append(Paragraph("<b>[+] Сильные стороны</b>", subheading_style))
        for s in strengths[:3]:
            col1_content.append(Paragraph(f"• {s}", body_style))
        
        col2_content.append(Paragraph("<b>[-] Зоны развития</b>", subheading_style))
        for g in growth[:3]:
            col2_content.append(Paragraph(f"• {g}", body_style))
        
        profile_cols = Table(
            [[col1_content, col2_content]],
            colWidths=[80*mm, 80*mm]
        )
        profile_cols.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        # Центрируем колонки в контейнере
        centered_profile = Table([[profile_cols]], colWidths=[180*mm])
        centered_profile.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(centered_profile)
        elements.append(Spacer(1, 8*mm))
        
        # Разделитель
        elements.append(SectionDivider(width=180*mm, style="line"))
        elements.append(Spacer(1, 5*mm))
        
        # Стили мышления
        thinking_style = profile_data.get("thinking_style", "")
        comm_style = profile_data.get("communication_style", "")
        
        if thinking_style or comm_style:
            styles_data = []
            if thinking_style:
                styles_data.append(["Стиль мышления:", thinking_style[:80]])
            if comm_style:
                styles_data.append(["Коммуникация:", comm_style[:80]])
            
            styles_table = Table(styles_data, colWidths=[40*mm, 110*mm])
            styles_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), FONT_BOLD),
                ('FONTNAME', (1, 0), (1, -1), FONT_NAME),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('TEXTCOLOR', (0, 0), (-1, -1), Colors.TEXT_PRIMARY),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            
            # Центрируем таблицу стилей
            centered_styles = Table([[styles_table]], colWidths=[180*mm])
            centered_styles.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            elements.append(centered_styles)
    
    # ========================================
    # СТРАНИЦЫ 2-3: ДЕТАЛЬНЫЙ АНАЛИЗ ПО КАТЕГОРИЯМ
    # ========================================
    
    if raw_averages:
        elements.append(PageBreak())
        elements.append(Paragraph("АНАЛИЗ ПО КАТЕГОРИЯМ", heading_style))
        
        # Определяем метрики для каждой категории
        category_metrics = {
            "hard_skills": {
                "title": "Hard Skills",
                "subtitle": "Профессиональные навыки",
                "color": Colors.HARD_SKILLS,
                "icon": "[HS]",
                "max_score": 30,
                "metrics": ["expertise", "methodology", "tools_proficiency"],
                "descriptions": {
                    "expertise": "Глубина знаний в своей области, экспертиза",
                    "methodology": "Владение фреймворками и процессами",
                    "tools_proficiency": "Практическое владение инструментарием",
                },
                "insights": "Показывает уровень технической подготовки и практического опыта в профессии."
            },
            "soft_skills": {
                "title": "Soft Skills", 
                "subtitle": "Коммуникация и взаимодействие",
                "color": Colors.SOFT_SKILLS,
                "icon": "[SS]",
                "max_score": 25,
                "metrics": ["articulation", "self_awareness", "conflict_handling"],
                "descriptions": {
                    "articulation": "Ясность и структурность изложения мыслей",
                    "self_awareness": "Понимание своих сильных и слабых сторон",
                    "conflict_handling": "Умение находить компромиссы и решать конфликты",
                },
                "insights": "Отражает способность эффективно взаимодействовать с командой и стейкхолдерами."
            },
            "thinking": {
                "title": "Thinking",
                "subtitle": "Мышление и анализ",
                "color": Colors.THINKING,
                "icon": "[TH]",
                "max_score": 25,
                "metrics": ["depth", "structure", "systems_thinking", "creativity"],
                "descriptions": {
                    "depth": "Способность к глубокому анализу проблем",
                    "structure": "Логичность и последовательность рассуждений",
                    "systems_thinking": "Видение связей и закономерностей",
                    "creativity": "Нестандартные подходы к решению задач",
                },
                "insights": "Демонстрирует качество принятия решений и способность к стратегическому мышлению."
            },
            "mindset": {
                "title": "Mindset",
                "subtitle": "Установки и ценности",
                "color": Colors.MINDSET,
                "icon": "[MS]",
                "max_score": 20,
                "metrics": ["honesty", "growth_orientation"],
                "descriptions": {
                    "honesty": "Искренность и аутентичность в ответах",
                    "growth_orientation": "Стремление к развитию и обучению",
                },
                "insights": "Характеризует профессиональную зрелость и потенциал роста."
            },
        }
        
        metric_names = {
            "expertise": "Экспертиза",
            "methodology": "Методология", 
            "tools_proficiency": "Инструменты",
            "articulation": "Коммуникация",
            "self_awareness": "Самосознание",
            "conflict_handling": "Конфликты",
            "depth": "Глубина",
            "structure": "Структура",
            "systems_thinking": "Системность",
            "creativity": "Креативность",
            "honesty": "Честность",
            "growth_orientation": "Рост",
        }
        
        # Генерируем карточки для каждой категории
        for cat_key, cat_info in category_metrics.items():
            cat_score = scores.get(cat_key, 0)
            
            # Заголовок категории — по центру
            cat_header_style = ParagraphStyle(
                f'CatHeader_{cat_key}',
                fontName=FONT_BOLD,
                fontSize=12,
                textColor=cat_info["color"],
                spaceBefore=8,
                spaceAfter=2,
                alignment=TA_CENTER,
            )
            
            elements.append(Paragraph(
                f'{cat_info["icon"]} {cat_info["title"]} — {cat_info["subtitle"]}',
                cat_header_style
            ))
            
            # Балл категории — по центру
            cat_score_style = ParagraphStyle(
                f'CatScore_{cat_key}',
                fontName=FONT_SEMIBOLD,
                fontSize=10,
                textColor=Colors.TEXT_PRIMARY,
                spaceAfter=4,
                alignment=TA_CENTER,
            )
            elements.append(Paragraph(
                f'<b>{cat_score}</b> из {cat_info["max_score"]} баллов',
                cat_score_style
            ))
            
            # Метрики категории — с явными отступами слева и справа
            metrics_rows = []
            for m_key in cat_info["metrics"]:
                m_value = raw_averages.get(m_key, 5.0)
                m_name = metric_names.get(m_key, m_key)
                
                name_style = ParagraphStyle(
                    f'MetricName_{m_key}',
                    fontName=FONT_BOLD,
                    fontSize=10,
                    textColor=Colors.TEXT_PRIMARY,
                )
                # 3 колонки: [пустая] [название] [прогресс]
                metrics_rows.append([
                    '',  # Пустая колонка слева
                    Paragraph(m_name, name_style),
                    ProgressBar(m_value, 10, width=90, height=14, color=cat_info["color"], show_value=True),
                ])
            
            metrics_table = Table(
                metrics_rows,
                colWidths=[30*mm, 45*mm, 105*mm],
            )
            metrics_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(metrics_table)
            
            # Инсайт — по центру
            insight_style = ParagraphStyle(
                f'Insight_{cat_key}',
                fontName=FONT_NAME,
                fontSize=8,
                textColor=Colors.TEXT_SECONDARY,
                spaceAfter=6,
                alignment=TA_CENTER,
            )
            elements.append(Paragraph(f'> {cat_info["insights"]}', insight_style))
            
            # Разделитель (кроме последней категории)
            if cat_key != "mindset":
                elements.append(Spacer(1, 3*mm))
                elements.append(SectionDivider(width=180*mm, style="line"))
                elements.append(Spacer(1, 3*mm))
    
    # ========================================
    # СТРАНИЦА: СИЛЬНЫЕ СТОРОНЫ (S5)
    # ========================================
    
    if raw_averages:
        elements.append(PageBreak())
        elements.append(Paragraph("СИЛЬНЫЕ СТОРОНЫ", heading_style))
        
        intro_style = ParagraphStyle(
            'StrengthsIntro',
            fontName=FONT_NAME,
            fontSize=9,
            textColor=Colors.TEXT_SECONDARY,
            spaceAfter=10,
        )
        elements.append(Paragraph(
            "Ваши топ-5 компетенций, которые можно использовать как конкурентное преимущество.",
            intro_style
        ))
        
        # Расширенные описания метрик
        metric_details = {
            "expertise": {
                "name": "Экспертиза",
                "desc": "Глубокие знания в профессиональной области",
                "how_to_use": "Станьте go-to person в команде по сложным вопросам. Делитесь знаниями через менторинг или внутренние митапы.",
            },
            "methodology": {
                "name": "Методология",
                "desc": "Владение фреймворками, процессами и best practices",
                "how_to_use": "Внедряйте стандарты в команде, участвуйте в ревью процессов, предлагайте улучшения.",
            },
            "tools_proficiency": {
                "name": "Инструменты",
                "desc": "Практическое владение профессиональным инструментарием",
                "how_to_use": "Автоматизируйте рутину, обучайте коллег эффективным workflows, экспериментируйте с новыми тулами.",
            },
            "articulation": {
                "name": "Коммуникация",
                "desc": "Ясность и структурность изложения мыслей",
                "how_to_use": "Берите на себя презентации и защиту идей перед стейкхолдерами. Пишите документацию.",
            },
            "self_awareness": {
                "name": "Самосознание",
                "desc": "Понимание своих сильных и слабых сторон",
                "how_to_use": "Используйте рефлексию для роста. Запрашивайте фидбек и адаптируйте подход.",
            },
            "conflict_handling": {
                "name": "Решение конфликтов",
                "desc": "Умение находить компромиссы и сглаживать разногласия",
                "how_to_use": "Выступайте медиатором в спорах. Помогайте команде находить win-win решения.",
            },
            "depth": {
                "name": "Глубина мышления",
                "desc": "Способность к детальному анализу проблем",
                "how_to_use": "Беритесь за сложные задачи, где нужен глубокий анализ. Проводите root cause analysis.",
            },
            "structure": {
                "name": "Структурность",
                "desc": "Логичность и последовательность рассуждений",
                "how_to_use": "Структурируйте хаос: создавайте планы, декомпозируйте задачи, организуйте информацию.",
            },
            "systems_thinking": {
                "name": "Системное мышление",
                "desc": "Видение связей и закономерностей в сложных системах",
                "how_to_use": "Участвуйте в архитектурных решениях. Анализируйте последствия изменений на всю систему.",
            },
            "creativity": {
                "name": "Креативность",
                "desc": "Нестандартные подходы к решению задач",
                "how_to_use": "Предлагайте инновационные решения. Участвуйте в брейнштормах, генерируйте гипотезы.",
            },
            "honesty": {
                "name": "Честность",
                "desc": "Искренность и аутентичность в коммуникации",
                "how_to_use": "Давайте честный фидбек. Признавайте ошибки первым — это строит доверие.",
            },
            "growth_orientation": {
                "name": "Ориентация на рост",
                "desc": "Стремление к развитию и обучению",
                "how_to_use": "Ставьте stretch goals. Ищите возможности выйти из зоны комфорта.",
            },
        }
        
        # Топ-5 сильных метрик
        sorted_metrics = sorted(raw_averages.items(), key=lambda x: x[1], reverse=True)
        top_5 = sorted_metrics[:5]
        
        for i, (m_key, m_value) in enumerate(top_5, 1):
            details = metric_details.get(m_key, {})
            m_name = details.get("name", m_key)
            m_desc = details.get("desc", "")
            m_how = details.get("how_to_use", "")
            
            # Цвет по значению
            if m_value >= 8:
                badge_color = Colors.EXCELLENT
                level_text = "Отлично"
            elif m_value >= 6:
                badge_color = Colors.GOOD
                level_text = "Хорошо"
            else:
                badge_color = Colors.AVERAGE
                level_text = "Средне"
            
            # Заголовок с номером и баллом
            strength_header = ParagraphStyle(
                f'StrengthHeader_{i}',
                fontName=FONT_BOLD,
                fontSize=11,
                textColor=Colors.TEXT_PRIMARY,
                spaceBefore=8,
                spaceAfter=2,
            )
            elements.append(Paragraph(
                f'{i}. {m_name} — <font color="{badge_color.hexval()}">{m_value:.1f}/10</font>',
                strength_header
            ))
            
            # Описание
            if m_desc:
                desc_style = ParagraphStyle(
                    f'StrengthDesc_{i}',
                    fontName=FONT_NAME,
                    fontSize=9,
                    textColor=Colors.TEXT_SECONDARY,
                    leftIndent=15,
                    spaceAfter=2,
                )
                elements.append(Paragraph(m_desc, desc_style))
            
            # Как использовать
            if m_how:
                how_style = ParagraphStyle(
                    f'StrengthHow_{i}',
                    fontName=FONT_NAME,
                    fontSize=8,
                    textColor=Colors.SECONDARY,
                    leftIndent=15,
                    spaceAfter=5,
                    backColor=Colors.LIGHT_BG,
                    borderPadding=(3, 5, 3, 5),
                )
                elements.append(Paragraph(f'&gt; <b>Как использовать:</b> {m_how}', how_style))
        
        elements.append(Spacer(1, 5*mm))
    
    # ========================================
    # СТРАНИЦА: ЗОНЫ РАЗВИТИЯ (S6)
    # ========================================
    
    if raw_averages:
        elements.append(SectionDivider(width=180*mm, style="gradient"))
        elements.append(Paragraph("ЗОНЫ РАЗВИТИЯ", heading_style))
        
        elements.append(Paragraph(
            "Топ-3 области для приоритетного развития с конкретными первыми шагами.",
            intro_style
        ))
        
        # Нижние 3 метрики
        bottom_3 = sorted_metrics[-3:][::-1]  # Reverse для worst first
        
        priority_labels = ["[!] Критично", "[*] Важно", "[-] Желательно"]
        
        for i, (m_key, m_value) in enumerate(bottom_3):
            details = metric_details.get(m_key, {})
            m_name = details.get("name", m_key)
            priority = priority_labels[i] if i < len(priority_labels) else ""
            
            # Определяем первый шаг
            first_steps = {
                "expertise": "Выделите 2 часа в неделю на изучение новых материалов в своей области.",
                "methodology": "Изучите один новый фреймворк и примените его на реальном проекте.",
                "tools_proficiency": "Пройдите короткий курс по инструменту, который используете чаще всего.",
                "articulation": "Практикуйте объяснение сложных идей простым языком — записывайте себя.",
                "self_awareness": "Запросите фидбек у 3 коллег и составьте список паттернов.",
                "conflict_handling": "Изучите технику 'интересы vs позиции' и примените на следующем споре.",
                "depth": "При следующей задаче задайте себе 5 'почему' до корневой причины.",
                "structure": "Начните использовать шаблоны для документов и декомпозиции задач.",
                "systems_thinking": "Нарисуйте карту зависимостей вашего текущего проекта.",
                "creativity": "Попробуйте технику 'crazy 8s' — 8 идей за 8 минут.",
                "honesty": "На следующем ретро поделитесь одной своей ошибкой и уроком.",
                "growth_orientation": "Поставьте одну stretch goal на месяц и отслеживайте прогресс.",
            }
            
            first_step = first_steps.get(m_key, "Определите конкретное действие на эту неделю.")
            
            # Заголовок
            gap_header = ParagraphStyle(
                f'GapHeader_{i}',
                fontName=FONT_BOLD,
                fontSize=10,
                textColor=Colors.LOW if i == 0 else (Colors.AVERAGE if i == 1 else Colors.TEXT_PRIMARY),
                spaceBefore=8,
                spaceAfter=2,
            )
            elements.append(Paragraph(
                f'{priority} {m_name} — {m_value:.1f}/10',
                gap_header
            ))
            
            # Первый шаг
            step_style = ParagraphStyle(
                f'GapStep_{i}',
                fontName=FONT_NAME,
                fontSize=8,
                textColor=Colors.TEXT_PRIMARY,
                leftIndent=15,
                spaceAfter=5,
            )
            elements.append(Paragraph(f'&gt; <b>Первый шаг:</b> {first_step}', step_style))
        
        elements.append(Spacer(1, 5*mm))
    
    # ========================================
    # СТРАНИЦА: PDP (Personal Development Plan) — 30 дней
    # ========================================
    
    if pdp_data:
        elements.append(PageBreak())
        
        # Заголовок с акцентом
        pdp_title_style = ParagraphStyle(
            'PDPTitle',
            fontName=FONT_BOLD,
            fontSize=18,
            textColor=Colors.PRIMARY,
            spaceAfter=3,
        )
        elements.append(Paragraph("🎯 ПЛАН РАЗВИТИЯ", pdp_title_style))
        
        # Подзаголовок с временем
        pdp_subtitle_style = ParagraphStyle(
            'PDPSubtitle',
            fontName=FONT_BOLD,
            fontSize=12,
            textColor=Colors.ACCENT,
            spaceAfter=8,
        )
        elements.append(Paragraph("30 ДНЕЙ • 4 НЕДЕЛИ • КОНКРЕТНЫЕ ДЕЙСТВИЯ", pdp_subtitle_style))
        
        # Подзаголовок
        pdp_intro_style = ParagraphStyle(
            'PDPIntro',
            fontName=FONT_NAME,
            fontSize=9,
            textColor=Colors.TEXT_SECONDARY,
            spaceAfter=12,
        )
        elements.append(Paragraph(
            "Персональный план действий на основе результатов диагностики",
            pdp_intro_style
        ))
        
        # Главный фокус (карточка с рамкой)
        main_focus = pdp_data.get("main_focus", "")
        if main_focus:
            # Создаём таблицу-карточку для фокуса
            focus_content = Paragraph(
                f'<b>ГЛАВНЫЙ ФОКУС:</b> {main_focus}',
                ParagraphStyle(
                    'FocusText',
                    fontName=FONT_SEMIBOLD,
                    fontSize=11,
                    textColor=Colors.PRIMARY,
                )
            )
            focus_table = Table(
                [[focus_content]],
                colWidths=[175*mm],
            )
            focus_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), Colors.LIGHT_BG),
                ('BOX', (0, 0), (-1, -1), 1.5, Colors.ACCENT),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ]))
            elements.append(focus_table)
            elements.append(Spacer(1, 8*mm))
        
        elements.append(SectionDivider(width=180*mm, style="line"))
        
        # Приоритетные цели с прогресс-барами
        primary_goals = pdp_data.get("primary_goals", [])
        if primary_goals:
            elements.append(Paragraph("ЦЕЛИ НА 30 ДНЕЙ", subheading_style))
            
            for i, goal in enumerate(primary_goals[:3], 1):
                metric_name = goal.get("metric_name", "")
                current = goal.get("current_score", 0)
                target = goal.get("target_score", 0)
                priority_reason = goal.get("priority_reason", "")
                
                # Цветовая кодировка по номеру
                goal_colors = [Colors.HARD_SKILLS, Colors.SOFT_SKILLS, Colors.THINKING]
                goal_color = goal_colors[i-1] if i <= len(goal_colors) else Colors.PRIMARY
                
                # Заголовок цели
                goal_header_style = ParagraphStyle(
                    f'GoalHeader_{i}',
                    fontName=FONT_BOLD,
                    fontSize=11,
                    textColor=goal_color,
                    spaceBefore=8,
                    spaceAfter=3,
                )
                elements.append(Paragraph(f'{i}. {metric_name}', goal_header_style))
                
                # Прогресс-бар: [текущий] [бар] [→ цель]
                target_style = ParagraphStyle(
                    f'Target_{i}',
                    fontName=FONT_BOLD,
                    fontSize=9,
                    textColor=goal_color,
                )
                progress_row = Table(
                    [[
                        Paragraph(f'{current:.1f}', small_style),
                        ProgressBar(current, 10, width=80, height=10, color=goal_color, show_value=False),
                        Paragraph(f'→ {target:.1f}', target_style),
                    ]],
                    colWidths=[12*mm, 85*mm, 18*mm],
                    hAlign='LEFT',
                )
                progress_row.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 2),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ]))
                elements.append(progress_row)
                
                # Причина
                if priority_reason:
                    reason_style = ParagraphStyle(
                        f'GoalReason_{i}',
                        fontName=FONT_NAME,
                        fontSize=8,
                        textColor=Colors.TEXT_SECONDARY,
                        leftIndent=5,
                        spaceAfter=3,
                    )
                    elements.append(Paragraph(f'&gt; {priority_reason[:120]}', reason_style))
                
                # Действия (чек-лист)
                actions = goal.get("actions", [])
                if actions:
                    action_style = ParagraphStyle(
                        f'GoalAction_{i}',
                        fontName=FONT_NAME,
                        fontSize=9,
                        textColor=Colors.TEXT_PRIMARY,
                        leftIndent=5,
                        spaceAfter=2,
                        bulletIndent=0,
                    )
                    for action in actions[:3]:
                        action_text = action.get("action", "") if isinstance(action, dict) else str(action)
                        if action_text:
                            elements.append(Paragraph(f'<font color="{goal_color.hexval()}">•</font> {action_text[:80]}', action_style))
                
                # Ресурсы
                resources = goal.get("resources", [])
                if resources:
                    res_style = ParagraphStyle(
                        f'GoalRes_{i}',
                        fontName=FONT_NAME,
                        fontSize=8,
                        textColor=Colors.TEXT_SECONDARY,
                        leftIndent=5,
                        spaceBefore=2,
                    )
                    for res in resources[:2]:
                        res_title = res.get("title", "") if isinstance(res, dict) else str(res)
                        res_type = res.get("type", "") if isinstance(res, dict) else ""
                        type_labels = {"book": "Книга:", "course": "Курс:", "practice": "Практика:", "tool": "Инструмент:"}
                        label = type_labels.get(res_type, "")
                        elements.append(Paragraph(f'<i>{label}</i> {res_title[:70]}', res_style))
                
                elements.append(Spacer(1, 3*mm))
            
        elements.append(SectionDivider(width=180*mm, style="dots"))
        
        # План на 30 дней — по неделям
        plan_30 = pdp_data.get("plan_30_days", [])
        if plan_30:
            elements.append(Paragraph("ПЛАН ПО НЕДЕЛЯМ", subheading_style))
            
            week_colors = [Colors.HARD_SKILLS, Colors.SOFT_SKILLS, Colors.THINKING, Colors.MINDSET]
            items_per_week = max(1, len(plan_30) // 4) if len(plan_30) >= 4 else 1
            
            for week_num in range(4):
                start_idx = week_num * items_per_week
                end_idx = start_idx + items_per_week
                week_items = plan_30[start_idx:end_idx] if start_idx < len(plan_30) else []
                
                if week_items or week_num == 0:
                    week_color = week_colors[week_num]
                    week_header = ParagraphStyle(
                        f'WeekHeader_{week_num}',
                        fontName=FONT_BOLD,
                        fontSize=10,
                        textColor=week_color,
                        spaceBefore=6,
                        spaceAfter=3,
                    )
                    elements.append(Paragraph(f'Неделя {week_num + 1}', week_header))
                    
                    week_item_style = ParagraphStyle(
                        f'WeekItem_{week_num}',
                        fontName=FONT_NAME,
                        fontSize=9,
                        textColor=Colors.TEXT_PRIMARY,
                        leftIndent=5,
                        spaceAfter=2,
                    )
                    for item in week_items:
                        clean_item = item.lstrip("[]▸• 0123456789.")
                        elements.append(Paragraph(f'<font color="{week_color.hexval()}">•</font> {clean_item[:90]}', week_item_style))
        
        elements.append(Spacer(1, 5*mm))
        
        # Метрики успеха
        success_metrics = pdp_data.get("success_metrics", [])
        if success_metrics:
            elements.append(Paragraph("КАК ИЗМЕРИТЬ УСПЕХ", subheading_style))
            
            metric_style = ParagraphStyle(
                'SuccessMetric',
                fontName=FONT_NAME,
                fontSize=9,
                textColor=Colors.EXCELLENT,
                leftIndent=5,
                spaceAfter=3,
            )
            for item in success_metrics[:4]:
                clean_item = item.lstrip("[]▸• ")
                elements.append(Paragraph(f'✓ {clean_item}', metric_style))
        
        elements.append(Spacer(1, 8*mm))
        
        # Мотивационный блок в конце
        motivation_msg = pdp_data.get("motivation_message", "")
        if motivation_msg:
            # Очищаем от эмодзи в начале
            clean_motivation = motivation_msg.lstrip("🚀💪🎯👑 ")
            
            motivation_content = Paragraph(
                f'<i>"{clean_motivation}"</i>',
                ParagraphStyle(
                    'MotivationText',
                    fontName=FONT_NAME,
                    fontSize=10,
                    textColor=Colors.TEXT_PRIMARY,
                    alignment=TA_CENTER,
                )
            )
            motivation_table = Table(
                [[motivation_content]],
                colWidths=[160*mm],
            )
            motivation_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), Colors.LIGHT_BG),
                ('BOX', (0, 0), (-1, -1), 0.5, Colors.BORDER),
                ('LEFTPADDING', (0, 0), (-1, -1), 15),
                ('RIGHTPADDING', (0, 0), (-1, -1), 15),
                ('TOPPADDING', (0, 0), (-1, -1), 12),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            elements.append(motivation_table)
        
        # Призыв к действию
        elements.append(Spacer(1, 5*mm))
        cta_style = ParagraphStyle(
            'PDPCallToAction',
            fontName=FONT_SEMIBOLD,
            fontSize=9,
            textColor=Colors.ACCENT,
            alignment=TA_CENTER,
        )
        elements.append(Paragraph("Начни с первого действия сегодня! Пройди повторную диагностику через 30 дней.", cta_style))
    
    # ========================================
    # СТРАНИЦА: BENCHMARK — Сравнение с рынком (S8)
    # ========================================
    
    if benchmark_data or raw_averages:
        elements.append(PageBreak())
        
        # Заголовок
        bench_title_style = ParagraphStyle(
            'BenchTitle',
            fontName=FONT_BOLD,
            fontSize=16,
            textColor=Colors.PRIMARY,
            spaceAfter=5,
        )
        elements.append(Paragraph("СРАВНЕНИЕ С РЫНКОМ", bench_title_style))
        
        bench_intro_style = ParagraphStyle(
            'BenchIntro',
            fontName=FONT_NAME,
            fontSize=9,
            textColor=Colors.TEXT_SECONDARY,
            spaceAfter=15,
        )
        elements.append(Paragraph(
            f"Как ваш результат соотносится со средними показателями {role_name} с опытом {experience}",
            bench_intro_style
        ))
        
        # Общий результат vs средний
        avg_score = 50  # Базовый бенчмарк
        if benchmark_data:
            avg_score = benchmark_data.get("avg_score", 50)
        
        # Определяем перцентиль
        if total >= 80:
            percentile = "топ 5%"
            percentile_color = Colors.EXCELLENT
        elif total >= 70:
            percentile = "топ 15%"
            percentile_color = Colors.EXCELLENT
        elif total >= 60:
            percentile = "топ 30%"
            percentile_color = Colors.GOOD
        elif total >= 50:
            percentile = "топ 50%"
            percentile_color = Colors.GOOD
        elif total >= 40:
            percentile = "60-й перцентиль"
            percentile_color = Colors.AVERAGE
        else:
            percentile = "ниже среднего"
            percentile_color = Colors.LOW
        
        # Карточка с перцентилем
        percentile_card_style = ParagraphStyle(
            'PercentileCard',
            fontName=FONT_BOLD,
            fontSize=14,
            textColor=percentile_color,
            alignment=TA_CENTER,
            spaceBefore=10,
            spaceAfter=5,
        )
        elements.append(Paragraph(f'Вы в {percentile} специалистов', percentile_card_style))
        
        # Визуальная гистограмма распределения
        elements.append(Spacer(1, 5*mm))
        
        # Рисуем распределение (симуляция нормального распределения)
        distribution_data = []
        ranges = [
            ("0-20", 5, Colors.LOW),
            ("21-40", 15, Colors.AVERAGE),
            ("41-60", 35, Colors.AVERAGE),
            ("61-80", 30, Colors.GOOD),
            ("81-100", 15, Colors.EXCELLENT),
        ]
        
        # Определяем в каком диапазоне пользователь
        user_range_idx = 0
        if total <= 20:
            user_range_idx = 0
        elif total <= 40:
            user_range_idx = 1
        elif total <= 60:
            user_range_idx = 2
        elif total <= 80:
            user_range_idx = 3
        else:
            user_range_idx = 4
        
        # Создаём гистограмму как таблицу с барами
        hist_rows = []
        for i, (label, pct, color) in enumerate(ranges):
            bar_width = pct * 1.5  # Масштаб
            is_user = (i == user_range_idx)
            
            bar_color = percentile_color if is_user else Colors.BORDER
            label_style = ParagraphStyle(
                f'HistLabel_{i}',
                fontName=FONT_BOLD if is_user else FONT_NAME,
                fontSize=8,
                textColor=Colors.TEXT_PRIMARY if is_user else Colors.TEXT_SECONDARY,
            )
            
            # Создаём визуальный бар
            bar_cell = Table(
                [['']], 
                colWidths=[bar_width*mm], 
                rowHeights=[12]
            )
            bar_cell.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), bar_color),
                ('ROUNDEDCORNERS', [3, 3, 3, 3]),
            ]))
            
            marker = " ◀ ВЫ" if is_user else ""
            hist_rows.append([
                Paragraph(label, label_style),
                bar_cell,
                Paragraph(f'{pct}%{marker}', label_style),
            ])
        
        hist_table = Table(
            hist_rows,
            colWidths=[25*mm, 100*mm, 40*mm],
        )
        hist_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        
        elements.append(Paragraph("<b>Распределение оценок</b>", subheading_style))
        elements.append(hist_table)
        elements.append(Spacer(1, 8*mm))
        
        # Сравнение по категориям
        elements.append(Paragraph("<b>Сравнение по категориям</b>", subheading_style))
        
        category_benchmarks = {
            "hard_skills": {"name": "Hard Skills", "avg": 15, "max": 30, "color": Colors.HARD_SKILLS},
            "soft_skills": {"name": "Soft Skills", "avg": 12, "max": 25, "color": Colors.SOFT_SKILLS},
            "thinking": {"name": "Thinking", "avg": 12, "max": 25, "color": Colors.THINKING},
            "mindset": {"name": "Mindset", "avg": 10, "max": 20, "color": Colors.MINDSET},
        }
        
        comparison_rows = []
        for cat_key, cat_info in category_benchmarks.items():
            user_score = scores.get(cat_key, 0)
            avg_cat = cat_info["avg"]
            max_cat = cat_info["max"]
            diff = user_score - avg_cat
            
            if diff > 0:
                diff_text = f'+{diff}'
                diff_color = Colors.EXCELLENT
            elif diff < 0:
                diff_text = str(diff)
                diff_color = Colors.LOW
            else:
                diff_text = '±0'
                diff_color = Colors.TEXT_MUTED
            
            comparison_rows.append([
                Paragraph(cat_info["name"], body_style),
                Paragraph(f'{user_score}/{max_cat}', body_style),
                ProgressBar(user_score, max_cat, width=60, height=8, color=cat_info["color"], show_value=False),
                Paragraph(f'Ср: {avg_cat}', small_style),
                Paragraph(f'<font color="{diff_color.hexval()}">{diff_text}</font>', body_style),
            ])
        
        comparison_table = Table(
            comparison_rows,
            colWidths=[35*mm, 20*mm, 65*mm, 25*mm, 20*mm],
        )
        comparison_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LINEBELOW', (0, 0), (-1, -2), 0.5, Colors.BORDER),
        ]))
        elements.append(comparison_table)
        elements.append(Spacer(1, 8*mm))
        
        # Рекомендация "чтобы войти в топ-10%"
        if total < 80:
            gap_to_top = 80 - total
            top10_style = ParagraphStyle(
                'Top10Advice',
                fontName=FONT_SEMIBOLD,
                fontSize=9,
                textColor=Colors.SECONDARY,
                backColor=Colors.LIGHT_BG,
                borderPadding=(8, 10, 8, 10),
                spaceAfter=10,
            )
            elements.append(Paragraph(
                f'<b>Чтобы войти в топ-10%:</b> нужно набрать ещё +{gap_to_top} баллов. '
                f'Сфокусируйтесь на самых слабых метриках из раздела "Зоны развития".',
                top10_style
            ))
    
    # ========================================
    # СТРАНИЦА: ДЕТАЛЬНЫЙ АНАЛИЗ
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
    
    # ========================================
    # СТРАНИЦА: ДИАЛОГ ДИАГНОСТИКИ (S9)
    # ========================================
    
    if conversation_history and len(conversation_history) > 0:
        elements.append(PageBreak())
        
        # Заголовок
        dialog_title_style = ParagraphStyle(
            'DialogTitle',
            fontName=FONT_BOLD,
            fontSize=16,
            textColor=Colors.PRIMARY,
            spaceAfter=5,
        )
        elements.append(Paragraph("ДИАЛОГ ДИАГНОСТИКИ", dialog_title_style))
        
        dialog_intro_style = ParagraphStyle(
            'DialogIntro',
            fontName=FONT_NAME,
            fontSize=9,
            textColor=Colors.TEXT_SECONDARY,
            spaceAfter=10,
        )
        elements.append(Paragraph(
            f"Полная запись {len(conversation_history)} вопросов и ответов диагностики",
            dialog_intro_style
        ))
        
        elements.append(SectionDivider(width=180*mm, style="line"))
        elements.append(Spacer(1, 3*mm))
        
        for i, item in enumerate(conversation_history, 1):
            question = item.get('question', '')[:250]
            answer = item.get('answer', '')
            
            # Получаем оценку ответа если есть
            answer_score = item.get('score', None)
            
            # Номер вопроса (badge)
            q_num_style = ParagraphStyle(
                f'QNum_{i}',
                fontName=FONT_BOLD,
                fontSize=10,
                textColor=Colors.TEXT_WHITE,
                backColor=Colors.PRIMARY,
                borderPadding=(3, 8, 3, 8),
            )
            
            # Заголовок вопроса
            q_header_style = ParagraphStyle(
                f'QHeader_{i}',
                fontName=FONT_SEMIBOLD,
                fontSize=9,
                textColor=Colors.PRIMARY,
                spaceBefore=8,
                spaceAfter=3,
            )
            
            # Мини-бар оценки если есть
            score_indicator = ""
            if answer_score is not None:
                if answer_score >= 8:
                    score_indicator = f' <font color="{Colors.EXCELLENT.hexval()}">[***]</font>'
                elif answer_score >= 6:
                    score_indicator = f' <font color="{Colors.GOOD.hexval()}">[**-]</font>'
                elif answer_score >= 4:
                    score_indicator = f' <font color="{Colors.AVERAGE.hexval()}">[*--]</font>'
                else:
                    score_indicator = f' <font color="{Colors.LOW.hexval()}">[---]</font>'
            
            elements.append(Paragraph(f"<b>Q{i}.</b> {question}{score_indicator}", q_header_style))
            
            # Ответ (карточка с фоном)
            answer_truncated = answer[:500] if len(answer) > 500 else answer
            if len(answer) > 500:
                answer_truncated += "..."
            
            a_style = ParagraphStyle(
                f'Answer_{i}',
                fontName=FONT_NAME,
                fontSize=8,
                textColor=Colors.TEXT_PRIMARY,
                leftIndent=15,
                backColor=Colors.LIGHT_BG,
                borderPadding=(5, 8, 5, 8),
                spaceAfter=3,
                leading=11,
            )
            
            # Очищаем ответ от спецсимволов
            clean_answer = answer_truncated.replace('<', '&lt;').replace('>', '&gt;')
            elements.append(Paragraph(clean_answer, a_style))
            
            # Мини-разделитель между Q&A
            if i < len(conversation_history):
                elements.append(Spacer(1, 2*mm))
    
    # ========================================
    # СТРАНИЦА: ABOUT & CONTACT (S10)
    # ========================================
    
    elements.append(PageBreak())
    
    # Заголовок
    about_title_style = ParagraphStyle(
        'AboutTitle',
        fontName=FONT_BOLD,
        fontSize=16,
        textColor=Colors.PRIMARY,
        spaceAfter=10,
    )
    elements.append(Paragraph("О МЕТОДОЛОГИИ", about_title_style))
    
    # Описание методологии
    methodology_intro = ParagraphStyle(
        'MethodologyIntro',
        fontName=FONT_NAME,
        fontSize=9,
        textColor=Colors.TEXT_PRIMARY,
        spaceAfter=10,
        leading=13,
    )
    elements.append(Paragraph(
        "<b>Deep Diagnostic</b> — это AI-powered система оценки профессиональных компетенций, "
        "разработанная на основе лучших практик HR-аналитики и поведенческих интервью. "
        "Система анализирует 12 ключевых метрик, сгруппированных в 4 категории.",
        methodology_intro
    ))
    
    elements.append(SectionDivider(width=180*mm, style="line"))
    
    # Категории метрик (компактно)
    elements.append(Paragraph("<b>Структура оценки:</b>", subheading_style))
    
    metrics_summary = [
        ("Hard Skills (30 баллов)", "Экспертиза, Методология, Инструменты"),
        ("Soft Skills (25 баллов)", "Коммуникация, Самосознание, Конфликты"),
        ("Thinking (25 баллов)", "Глубина, Структура, Системность, Креатив"),
        ("Mindset (20 баллов)", "Честность, Ориентация на рост"),
    ]
    
    metrics_style = ParagraphStyle(
        'MetricsSummary',
        fontName=FONT_NAME,
        fontSize=8,
        textColor=Colors.TEXT_SECONDARY,
        leftIndent=10,
        spaceAfter=3,
    )
    
    for cat, metrics_list in metrics_summary:
        elements.append(Paragraph(f"<b>{cat}</b>", body_style))
        elements.append(Paragraph(metrics_list, metrics_style))
    
    elements.append(Spacer(1, 8*mm))
    elements.append(SectionDivider(width=180*mm, style="dots"))
    elements.append(Spacer(1, 12*mm))
    
    # Disclaimer
    important_style = ParagraphStyle(
        'Important',
        fontName=FONT_BOLD,
        fontSize=10,
        textColor=Colors.SECONDARY,
        spaceBefore=0,
        spaceAfter=5,
    )
    elements.append(Paragraph("ВАЖНО:", important_style))
    
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        fontName=FONT_NAME,
        fontSize=8,
        textColor=Colors.TEXT_MUTED,
        spaceAfter=8,
        backColor=Colors.LIGHT_BG,
        borderPadding=(8, 10, 8, 10),
        leading=11,
    )
    elements.append(Paragraph(
        "• Это <b>не психологический тест</b> — результаты основаны на анализе текстовых ответов<br/>"
        "• Диагностика носит <b>рекомендательный характер</b> и не заменяет профессиональную оценку<br/>"
        "• Для комплексной оценки рекомендуется использовать дополнительные методы<br/>"
        "• Результаты могут меняться со временем по мере развития компетенций",
        disclaimer_style
    ))
    
    elements.append(Spacer(1, 5*mm))
    elements.append(SectionDivider(width=180*mm, style="gradient"))
    
    # Контакты и повторная диагностика
    elements.append(Paragraph("<b>Повторная диагностика</b>", subheading_style))
    
    repeat_style = ParagraphStyle(
        'RepeatInfo',
        fontName=FONT_NAME,
        fontSize=9,
        textColor=Colors.TEXT_PRIMARY,
        spaceAfter=8,
    )
    elements.append(Paragraph(
        "Рекомендуется проходить диагностику каждые 3-6 месяцев для отслеживания прогресса. "
        "Сравнивайте результаты и отмечайте рост по ключевым метрикам.",
        repeat_style
    ))
    
    # Telegram бот
    elements.append(Paragraph("<b>Пройти диагностику снова:</b>", subheading_style))
    
    bot_link_style = ParagraphStyle(
        'BotLink',
        fontName=FONT_SEMIBOLD,
        fontSize=11,
        textColor=Colors.SECONDARY,
        alignment=TA_CENTER,
        spaceBefore=5,
        spaceAfter=10,
    )
    elements.append(Paragraph("@VISUALMAXAGENCY_BOT", bot_link_style))
    
    elements.append(Spacer(1, 10*mm))
    
    # Информация об отчёте
    report_id = f"DD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    report_info_style = ParagraphStyle(
        'ReportInfo',
        fontName=FONT_NAME,
        fontSize=7,
        textColor=Colors.TEXT_MUTED,
        alignment=TA_CENTER,
    )
    
    elements.append(Paragraph(
        f"----------------------------------------",
        report_info_style
    ))
    elements.append(Spacer(1, 3*mm))
    
    elements.append(Paragraph(
        f"<b>Отчёт ID:</b> {report_id}",
        report_info_style
    ))
    elements.append(Paragraph(
        f"<b>Дата генерации:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        report_info_style
    ))
    elements.append(Paragraph(
        f"<b>Кандидат:</b> {user_name} | {role_name} | {experience}",
        report_info_style
    ))
    elements.append(Spacer(1, 5*mm))
    
    # Финальный footer
    final_footer_style = ParagraphStyle(
        'FinalFooter',
        fontName=FONT_SEMIBOLD,
        fontSize=9,
        textColor=Colors.PRIMARY,
        alignment=TA_CENTER,
    )
    elements.append(Paragraph(
        "Deep Diagnostic — AI-powered career assessment",
        final_footer_style
    ))
    
    powered_style = ParagraphStyle(
        'Powered',
        fontName=FONT_NAME,
        fontSize=7,
        textColor=Colors.TEXT_MUTED,
        alignment=TA_CENTER,
    )
    elements.append(Paragraph(
        "Powered by MAX AGENCY",
        powered_style
    ))
    
    # Генерируем PDF с кастомными header/footer
    doc.build(
        elements,
        onFirstPage=_add_first_page,
        onLaterPages=_add_later_pages,
    )
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes
