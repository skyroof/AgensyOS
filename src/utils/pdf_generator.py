"""
Генератор PDF-отчётов.
"""
import io
import logging
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

# Регистрируем шрифт с поддержкой кириллицы
# Используем встроенный Helvetica для ASCII, для кириллицы нужен DejaVu или другой
try:
    # Попробуем найти системный шрифт
    import os
    
    # Windows fonts
    font_paths = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
    ]
    
    font_registered = False
    for font_path in font_paths:
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('CustomFont', font_path))
            font_registered = True
            break
    
    if not font_registered:
        # Fallback - используем стандартный шрифт
        logger.warning("No Cyrillic font found, PDF may have issues with Russian text")
        FONT_NAME = 'Helvetica'
    else:
        FONT_NAME = 'CustomFont'
        
except Exception as e:
    logger.warning(f"Failed to register font: {e}")
    FONT_NAME = 'Helvetica'


def generate_pdf_report(
    role_name: str,
    experience: str,
    scores: dict,
    report_text: str,
    conversation_history: list[dict],
    user_name: str = "Кандидат",
) -> bytes:
    """
    Сгенерировать PDF-отчёт.
    
    Args:
        role_name: Название роли
        experience: Опыт
        scores: Баллы по категориям
        report_text: Текст отчёта (HTML)
        conversation_history: История диалога
        user_name: Имя пользователя
        
    Returns:
        PDF как bytes
    """
    buffer = io.BytesIO()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm,
    )
    
    # Стили
    styles = getSampleStyleSheet()
    
    # Кастомные стили
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName=FONT_NAME,
        fontSize=24,
        spaceAfter=12,
        textColor=colors.HexColor('#1a1a2e'),
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontName=FONT_NAME,
        fontSize=14,
        spaceBefore=12,
        spaceAfter=6,
        textColor=colors.HexColor('#16213e'),
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=10,
        leading=14,
        spaceAfter=6,
    )
    
    small_style = ParagraphStyle(
        'SmallText',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=8,
        textColor=colors.grey,
    )
    
    # Элементы документа
    elements = []
    
    # Заголовок
    elements.append(Paragraph("DEEP DIAGNOSTIC", title_style))
    elements.append(Paragraph(
        f"Отчёт о диагностике специалиста",
        body_style
    ))
    elements.append(Spacer(1, 10*mm))
    
    # Информация о кандидате
    elements.append(Paragraph("ПРОФИЛЬ", heading_style))
    
    profile_data = [
        ["Имя:", user_name],
        ["Роль:", role_name],
        ["Опыт:", experience],
        ["Дата:", datetime.now().strftime("%d.%m.%Y %H:%M")],
    ]
    
    profile_table = Table(profile_data, colWidths=[40*mm, 100*mm])
    profile_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(profile_table)
    elements.append(Spacer(1, 8*mm))
    
    # Баллы
    elements.append(Paragraph("РЕЗУЛЬТАТЫ", heading_style))
    
    total = scores.get('total', 0)
    
    # Определяем уровень
    if total >= 80:
        level = "Senior / Lead"
        level_color = colors.HexColor('#27ae60')
    elif total >= 60:
        level = "Middle+"
        level_color = colors.HexColor('#2980b9')
    elif total >= 40:
        level = "Middle"
        level_color = colors.HexColor('#f39c12')
    else:
        level = "Junior / Junior+"
        level_color = colors.HexColor('#e74c3c')
    
    scores_data = [
        ["Категория", "Баллы", "Максимум"],
        ["Hard Skills", str(scores.get('hard_skills', 0)), "30"],
        ["Soft Skills", str(scores.get('soft_skills', 0)), "25"],
        ["Thinking", str(scores.get('thinking', 0)), "25"],
        ["Mindset", str(scores.get('mindset', 0)), "20"],
        ["ИТОГО", str(total), "100"],
    ]
    
    scores_table = Table(scores_data, colWidths=[60*mm, 30*mm, 30*mm])
    scores_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f0f0')),
        ('FONTNAME', (0, -1), (-1, -1), FONT_NAME),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(scores_table)
    elements.append(Spacer(1, 4*mm))
    
    # Уровень
    level_style = ParagraphStyle(
        'LevelStyle',
        parent=body_style,
        fontSize=12,
        textColor=level_color,
    )
    elements.append(Paragraph(f"<b>Уровень: {level}</b>", level_style))
    elements.append(Spacer(1, 8*mm))
    
    # Детальный отчёт
    elements.append(Paragraph("ДЕТАЛЬНЫЙ АНАЛИЗ", heading_style))
    
    # Очищаем HTML теги и конвертируем
    clean_report = report_text
    # Заменяем HTML теги на reportlab-совместимые
    clean_report = clean_report.replace('<b>', '<b>').replace('</b>', '</b>')
    clean_report = clean_report.replace('<i>', '<i>').replace('</i>', '</i>')
    clean_report = clean_report.replace('━', '-')
    clean_report = clean_report.replace('•', '  *')
    
    # Разбиваем на параграфы
    paragraphs = clean_report.split('\n\n')
    for para in paragraphs:
        if para.strip():
            # Убираем лишние переносы
            para = para.replace('\n', ' ').strip()
            if para:
                try:
                    elements.append(Paragraph(para, body_style))
                except Exception:
                    # Если не удалось распарсить HTML — добавляем как текст
                    elements.append(Paragraph(para.replace('<', '&lt;').replace('>', '&gt;'), body_style))
    
    elements.append(Spacer(1, 10*mm))
    
    # История диалога
    if conversation_history:
        elements.append(Paragraph("ИСТОРИЯ ДИАЛОГА", heading_style))
        
        for i, item in enumerate(conversation_history, 1):
            elements.append(Paragraph(f"<b>Вопрос {i}:</b>", body_style))
            elements.append(Paragraph(item.get('question', ''), body_style))
            elements.append(Paragraph(f"<b>Ответ:</b>", body_style))
            answer = item.get('answer', '')[:500]
            if len(item.get('answer', '')) > 500:
                answer += "..."
            elements.append(Paragraph(answer, body_style))
            elements.append(Spacer(1, 4*mm))
    
    # Футер
    elements.append(Spacer(1, 10*mm))
    elements.append(Paragraph(
        f"Сгенерировано Deep Diagnostic Bot • {datetime.now().strftime('%d.%m.%Y')}",
        small_style
    ))
    
    # Генерируем PDF
    doc.build(elements)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes

