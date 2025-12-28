# 🚀 ROADMAP v2: План развития Deep Diagnostic Bot

> Анализ текущего состояния + стратегия улучшений

---

## 📊 Аудит текущей системы

### Что работает хорошо ✅

| Компонент | Статус | Комментарий |
|-----------|--------|-------------|
| Базовый flow | ✅ | 10 вопросов → анализ → отчёт |
| AI-генерация вопросов | ✅ | Адаптивные вопросы через Claude |
| Анализ ответов | ⚠️ | Работает, но JSON parsing нестабилен |
| Скоринг | ✅ | 4 категории, взвешенный расчёт |
| PDF экспорт | ✅ | Полноценный отчёт |
| Голосовые сообщения | ✅ | Whisper через RouterAI |
| Persistence | ✅ | SQLite + SQLAlchemy |
| Логирование | ✅ | Middleware + структурированные логи |

### Критические проблемы 🔴

#### 1. JSON Parsing Failures (7 из 10 ответов)
```
ERROR - Failed to parse AI response as JSON: Extra data: line 21 column 1 (char 1598)
```

**Текущий код** (`src/ai/answer_analyzer.py:51-57`):
```python
clean_response = response.strip()
if clean_response.startswith("```"):
    lines = clean_response.split("\n")
    clean_response = "\n".join(lines[1:-1])

analysis = json.loads(clean_response)  # ← ПАДАЕТ
```

**Проблема**: AI возвращает JSON + комментарии/объяснения после него.

**Решение**:
```python
import re

def extract_json(text: str) -> dict:
    """Извлечь JSON из текста с мусором."""
    # Способ 1: JSONDecoder.raw_decode
    try:
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(text.strip())
        return obj
    except json.JSONDecodeError:
        pass
    
    # Способ 2: Regex для извлечения JSON объекта
    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group())
    
    raise ValueError("No valid JSON found")
```

#### 2. Медленные ответы (25-90 секунд)

**Причины**:
- Последовательные запросы: анализ → генерация вопроса
- Большой контекст передаётся каждый раз
- Нет streaming

**Текущий тайминг по логам**:
| Операция | Среднее время |
|----------|---------------|
| Анализ ответа | 18-26 сек |
| Генерация вопроса | 6-12 сек |
| Генерация отчёта | 60-90 сек |
| **Итого на вопрос** | **25-35 сек** |

**Решения**:
1. Параллельные запросы (анализ + генерация)
2. Streaming для UX
3. Сокращение контекста

#### 3. Fallback на дефолтные оценки

При ошибке парсинга все метрики = 5. Это **искажает 70% результатов**.

```python
DEFAULT_ANALYSIS = {
    "scores": {
        "depth": 5,
        "self_awareness": 5,  # ← Середина шкалы
        ...
    },
}
```

---

## 🎯 ФАЗА 1: Стабилизация (3-5 дней)

### 1.1 Исправить JSON parsing

```python
# src/ai/answer_analyzer.py

import re
import json
from json import JSONDecoder

def robust_json_parse(text: str) -> dict:
    """
    Робастный парсинг JSON из ответа AI.
    Обрабатывает:
    - JSON в markdown блоках
    - JSON с trailing text
    - JSON с комментариями
    """
    text = text.strip()
    
    # 1. Убираем markdown code blocks
    if text.startswith("```"):
        # Ищем конец блока
        end_idx = text.rfind("```")
        if end_idx > 3:
            text = text[text.find("\n")+1:end_idx]
    
    # 2. Пробуем raw_decode (игнорирует trailing data)
    try:
        decoder = JSONDecoder()
        obj, idx = decoder.raw_decode(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    
    # 3. Regex: извлекаем первый валидный JSON объект
    # Ищем { ... } с учётом вложенности
    brace_count = 0
    start_idx = None
    
    for i, char in enumerate(text):
        if char == '{':
            if brace_count == 0:
                start_idx = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_idx is not None:
                try:
                    return json.loads(text[start_idx:i+1])
                except json.JSONDecodeError:
                    start_idx = None
    
    raise ValueError(f"No valid JSON found in: {text[:200]}...")


async def analyze_answer(question: str, answer: str, role: str) -> dict:
    """Улучшенный анализ с робастным парсингом."""
    try:
        messages = get_analysis_prompt(question, answer, role)
        response = await chat_completion(messages=messages, temperature=0.3, max_tokens=1000)
        
        analysis = robust_json_parse(response)
        
        # Валидация структуры
        if "scores" not in analysis:
            raise ValueError("Missing 'scores' in analysis")
        
        # Валидация значений (0-10)
        for key, value in analysis["scores"].items():
            if not isinstance(value, (int, float)) or not 0 <= value <= 10:
                analysis["scores"][key] = 5  # Корректируем невалидные
        
        return analysis
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}, response: {response[:500] if 'response' in dir() else 'N/A'}")
        # Логируем сырой ответ для отладки
        return DEFAULT_ANALYSIS
```

### 1.2 Параллельные AI-запросы

```python
# src/bot/handlers/diagnostic.py

import asyncio

async def process_answer(message: Message, state: FSMContext, bot: Bot):
    """Оптимизированная обработка с параллельными запросами."""
    
    # ... валидация ...
    
    thinking_msg = await message.answer("🧠 Анализирую ответ...")
    
    # ПАРАЛЛЕЛЬНО: анализ + генерация следующего вопроса
    analysis_task = asyncio.create_task(
        analyze_answer(current_question, message.text, data["role"])
    )
    
    next_question_num = data["current_question"] + 1
    question_task = None
    
    if next_question_num <= TOTAL_QUESTIONS:
        # Начинаем генерацию следующего вопроса сразу
        # (используем текущую историю, анализ добавим потом)
        question_task = asyncio.create_task(
            generate_question(
                role=data["role"],
                role_name=data["role_name"],
                experience=data["experience_name"],
                question_number=next_question_num,
                conversation_history=conversation_history,
                analysis_history=analysis_history,  # Без текущего анализа
            )
        )
    
    # Ждём анализ
    analysis = await analysis_task
    analysis_history.append(analysis)
    
    # Если есть задача на вопрос — ждём её тоже
    if question_task:
        next_question = await question_task
    
    # Время ответа: ~18-26 сек вместо 25-35 сек (-30%)
```

### 1.3 Streaming для UX

```python
# src/ai/client.py

async def chat_completion_stream(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> AsyncGenerator[str, None]:
    """Streaming версия для улучшения UX."""
    settings = get_settings()
    client = get_ai_client()
    
    stream = await client.chat.completions.create(
        model=settings.ai_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


# Использование для отчёта:
async def generate_report_with_progress(callback, ...):
    """Генерация отчёта с live-обновлением."""
    full_text = ""
    last_update = 0
    
    async for chunk in chat_completion_stream(messages, ...):
        full_text += chunk
        
        # Обновляем сообщение каждые 500 символов
        if len(full_text) - last_update > 500:
            await callback.message.edit_text(
                f"📊 Генерирую отчёт...\n\n{full_text[:1000]}..."
            )
            last_update = len(full_text)
    
    return full_text
```

### 1.4 Логирование сырых ответов AI

```python
# Добавить в analyze_answer и другие AI-функции

import os
from datetime import datetime

DEBUG_LOG_DIR = "debug_logs"

def log_ai_response(prompt_type: str, response: str, success: bool):
    """Сохранять сырые ответы AI для отладки."""
    os.makedirs(DEBUG_LOG_DIR, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    status = "ok" if success else "fail"
    filename = f"{DEBUG_LOG_DIR}/{timestamp}_{prompt_type}_{status}.txt"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(response)
```

---

## 🎯 ФАЗА 2: Улучшение качества диагностики (1-2 недели)

### 2.1 Расширенные метрики

**Текущие (5)**: depth, self_awareness, structure, honesty, expertise

**Новые (12)**:
```python
METRICS_V2 = {
    # Когнитивные (Thinking 25%)
    "analytical_depth": "Глубина анализа проблем",
    "systems_thinking": "Системное видение",
    "creativity": "Нестандартные решения",
    
    # Профессиональные (Hard Skills 30%)
    "domain_expertise": "Экспертиза в предметной области",
    "methodology": "Владение методологиями",
    "tools_proficiency": "Владение инструментами",
    
    # Коммуникативные (Soft Skills 25%)
    "articulation": "Ясность изложения",
    "empathy": "Понимание стейкхолдеров",
    "conflict_handling": "Работа с конфликтами",
    
    # Личностные (Mindset 20%)
    "self_reflection": "Рефлексия и самокритика",
    "growth_orientation": "Ориентация на рост",
    "integrity": "Честность и этика",
}
```

### 2.2 Калибровка оценок по опыту

```python
def calibrate_scores(scores: dict, experience: str, role: str) -> dict:
    """
    Калибровка оценок относительно заявленного опыта.
    
    Junior с оценкой 7 за expertise — это хорошо.
    Lead с оценкой 7 за expertise — это посредственно.
    """
    experience_multipliers = {
        "junior": {"baseline": 4, "excellent_threshold": 6},
        "middle": {"baseline": 5, "excellent_threshold": 7},
        "senior": {"baseline": 6, "excellent_threshold": 8},
        "lead": {"baseline": 7, "excellent_threshold": 9},
    }
    
    calibrated = {}
    config = experience_multipliers.get(experience, experience_multipliers["middle"])
    
    for metric, value in scores.items():
        # Нормализуем относительно ожиданий для уровня
        baseline = config["baseline"]
        if value >= config["excellent_threshold"]:
            calibrated[metric] = {"value": value, "assessment": "exceeds_expectations"}
        elif value >= baseline:
            calibrated[metric] = {"value": value, "assessment": "meets_expectations"}
        else:
            calibrated[metric] = {"value": value, "assessment": "below_expectations"}
    
    return calibrated
```

### 2.3 Адаптивная сложность вопросов

```python
# src/ai/question_gen.py

def get_question_difficulty(analysis_history: list[dict]) -> str:
    """Определить сложность следующего вопроса."""
    if not analysis_history:
        return "standard"
    
    # Средняя оценка за последние 3 ответа
    recent = analysis_history[-3:]
    avg_scores = []
    
    for analysis in recent:
        scores = analysis.get("scores", {})
        avg = sum(scores.values()) / len(scores) if scores else 5
        avg_scores.append(avg)
    
    overall_avg = sum(avg_scores) / len(avg_scores)
    
    if overall_avg >= 8:
        return "challenging"  # Провокационные, глубинные
    elif overall_avg >= 6:
        return "standard"     # Обычные вопросы
    else:
        return "supportive"   # Упрощённые, поддерживающие


async def generate_question(...) -> str:
    """Генерация с адаптивной сложностью."""
    difficulty = get_question_difficulty(analysis_history)
    
    difficulty_instructions = {
        "challenging": """
            Задай ПРОВОКАЦИОННЫЙ вопрос:
            - Намеренно создай дискомфорт
            - Попроси привести пример ПРОВАЛА
            - Спроси о противоречиях в предыдущих ответах
            - Поставь перед сложным выбором
        """,
        "standard": """
            Задай вопрос средней сложности:
            - Попроси конкретный пример
            - Углубись в выявленные темы
        """,
        "supportive": """
            Задай ПОДДЕРЖИВАЮЩИЙ вопрос:
            - Помоги кандидату раскрыться
            - Спроси о том, что получается хорошо
            - Избегай давления
        """,
    }
    
    # Добавляем инструкцию в промпт
    messages = get_question_prompt(...)
    messages[0]["content"] += difficulty_instructions[difficulty]
    
    return await chat_completion(messages, ...)
```

### 2.4 Детекция паттернов

```python
# src/ai/pattern_detector.py

SUSPICIOUS_PATTERNS = {
    "rehearsed_answers": [
        r"как я уже говорил",
        r"обычно в таких случаях",
        r"по методологии \w+",
        r"согласно best practices",
    ],
    "evasive": [
        r"сложно сказать",
        r"это зависит",
        r"по-разному",
        r"не помню точно",
    ],
    "overconfident": [
        r"я всегда",
        r"у меня никогда не было проблем",
        r"я лучший в",
        r"все говорят что я",
    ],
}

def detect_patterns(answer: str) -> list[str]:
    """Выявить подозрительные паттерны в ответе."""
    detected = []
    
    for pattern_type, patterns in SUSPICIOUS_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, answer, re.IGNORECASE):
                detected.append(pattern_type)
                break
    
    return detected
```

---

## 🎯 ФАЗА 3: Продвинутая аналитика (2-3 недели)

### 3.1 Профиль компетенций

```python
# src/analytics/competency_profile.py

from dataclasses import dataclass
from typing import Optional

@dataclass
class CompetencyProfile:
    """Полный профиль компетенций на основе диагностики."""
    
    # Базовые данные
    role: str
    experience: str
    total_score: int
    
    # Детальные оценки по категориям
    hard_skills: dict[str, float]  # methodology, tools, domain
    soft_skills: dict[str, float]  # communication, empathy, conflict
    thinking: dict[str, float]     # analytical, systems, creative
    mindset: dict[str, float]      # growth, integrity, reflection
    
    # Топ-3 сильные стороны
    strengths: list[str]
    
    # Топ-3 зоны роста
    growth_areas: list[str]
    
    # Психологический профиль
    thinking_style: str  # analytical / creative / strategic / tactical
    communication_style: str  # direct / diplomatic / avoiding
    risk_tolerance: str  # conservative / moderate / aggressive
    motivation_driver: str  # growth / recognition / stability / impact
    
    # Сравнение с бенчмарком
    percentile: int  # 0-100, позиция среди аналогичных
    
    # Рекомендации
    development_plan: list[str]
    recommended_resources: list[dict]  # books, courses, etc.


def build_profile(session: DiagnosticSession) -> CompetencyProfile:
    """Построить профиль на основе сессии."""
    
    # Извлекаем все оценки из analysis_history
    all_scores = aggregate_scores(session.analysis_history)
    
    # Определяем психологические характеристики
    thinking_style = detect_thinking_style(session.conversation_history)
    communication_style = detect_communication_style(session.conversation_history)
    
    # Находим сильные стороны и зоны роста
    sorted_scores = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
    strengths = [s[0] for s in sorted_scores[:3]]
    growth_areas = [s[0] for s in sorted_scores[-3:]]
    
    # Генерируем рекомендации
    development_plan = generate_development_plan(growth_areas, session.role)
    resources = find_recommended_resources(growth_areas, session.role)
    
    return CompetencyProfile(
        role=session.role,
        experience=session.experience,
        total_score=session.total_score,
        hard_skills=extract_category_scores(all_scores, "hard"),
        soft_skills=extract_category_scores(all_scores, "soft"),
        thinking=extract_category_scores(all_scores, "thinking"),
        mindset=extract_category_scores(all_scores, "mindset"),
        strengths=strengths,
        growth_areas=growth_areas,
        thinking_style=thinking_style,
        communication_style=communication_style,
        risk_tolerance=detect_risk_tolerance(session.conversation_history),
        motivation_driver=detect_motivation(session.conversation_history),
        percentile=calculate_percentile(session),
        development_plan=development_plan,
        recommended_resources=resources,
    )
```

### 3.2 Бенчмаркинг

```python
# src/analytics/benchmark.py

async def calculate_percentile(session: DiagnosticSession) -> int:
    """
    Вычислить перцентиль пользователя среди аналогичных.
    
    Сравнение по:
    - Той же роли (designer / product)
    - Тому же уровню опыта (±1 уровень)
    """
    async with get_session() as db:
        # Находим похожие завершённые сессии
        similar_sessions = await db.execute(
            select(DiagnosticSession)
            .where(
                DiagnosticSession.role == session.role,
                DiagnosticSession.status == "completed",
                DiagnosticSession.total_score.isnot(None),
            )
        )
        
        all_scores = [s.total_score for s in similar_sessions.scalars()]
        
        if len(all_scores) < 10:
            return 50  # Недостаточно данных
        
        # Считаем перцентиль
        below_count = sum(1 for s in all_scores if s < session.total_score)
        percentile = int((below_count / len(all_scores)) * 100)
        
        return percentile


def get_benchmark_insights(session: DiagnosticSession, percentile: int) -> list[str]:
    """Генерация инсайтов на основе бенчмарка."""
    insights = []
    
    if percentile >= 90:
        insights.append(f"🏆 Ты в топ-10% {session.role_name}ов с опытом {session.experience_name}")
    elif percentile >= 75:
        insights.append(f"💪 Ты опережаешь 75% коллег по профессии")
    elif percentile >= 50:
        insights.append(f"📊 Ты в верхней половине специалистов твоего уровня")
    else:
        insights.append(f"📈 Есть потенциал для роста — ты можешь подняться выше")
    
    return insights
```

### 3.3 Трекинг прогресса

```python
# src/analytics/progress.py

@dataclass
class ProgressReport:
    """Отчёт о прогрессе между диагностиками."""
    
    sessions_count: int
    first_date: datetime
    last_date: datetime
    
    # Динамика общего скора
    first_score: int
    current_score: int
    score_change: int
    score_trend: str  # "growing" / "stable" / "declining"
    
    # Детальная динамика по категориям
    category_changes: dict[str, int]  # {"hard_skills": +5, ...}
    
    # Улучшившиеся области
    improved_areas: list[str]
    
    # Ухудшившиеся области
    declined_areas: list[str]
    
    # Рекомендация
    recommendation: str


async def get_progress_report(user_id: int) -> Optional[ProgressReport]:
    """Получить отчёт о прогрессе пользователя."""
    async with get_session() as db:
        sessions = await db.execute(
            select(DiagnosticSession)
            .where(
                DiagnosticSession.user_id == user_id,
                DiagnosticSession.status == "completed",
            )
            .order_by(DiagnosticSession.completed_at)
        )
        
        sessions_list = list(sessions.scalars())
        
        if len(sessions_list) < 2:
            return None  # Нужно минимум 2 диагностики
        
        first = sessions_list[0]
        last = sessions_list[-1]
        
        score_change = last.total_score - first.total_score
        
        if score_change > 5:
            trend = "growing"
            recommendation = "Отличная динамика! Продолжай в том же духе."
        elif score_change < -5:
            trend = "declining"
            recommendation = "Заметно снижение. Рекомендую уделить внимание развитию."
        else:
            trend = "stable"
            recommendation = "Стабильный уровень. Попробуй выйти из зоны комфорта."
        
        return ProgressReport(
            sessions_count=len(sessions_list),
            first_date=first.started_at,
            last_date=last.completed_at,
            first_score=first.total_score,
            current_score=last.total_score,
            score_change=score_change,
            score_trend=trend,
            category_changes=calculate_category_changes(first, last),
            improved_areas=find_improved_areas(first, last),
            declined_areas=find_declined_areas(first, last),
            recommendation=recommendation,
        )
```

---

## 🎯 ФАЗА 4: Интеграции (3-4 недели)

### 4.1 Webhook для внешних систем

```python
# src/integrations/webhook.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class DiagnosticResult(BaseModel):
    session_id: int
    user_telegram_id: int
    user_name: str
    role: str
    experience: str
    total_score: int
    scores: dict
    report_summary: str
    completed_at: str


@app.post("/webhook/{webhook_id}")
async def send_to_webhook(webhook_id: str, result: DiagnosticResult):
    """Отправить результат во внешнюю систему."""
    
    # Получаем URL webhook из настроек
    webhook_url = await get_webhook_url(webhook_id)
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            webhook_url,
            json=result.dict(),
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        
        if response.status_code != 200:
            raise HTTPException(500, f"Webhook failed: {response.text}")
    
    return {"status": "sent"}
```

### 4.2 Notion интеграция

```python
# src/integrations/notion.py

from notion_client import AsyncClient

class NotionExporter:
    def __init__(self, token: str, database_id: str):
        self.client = AsyncClient(auth=token)
        self.database_id = database_id
    
    async def export_session(self, session: DiagnosticSession, profile: CompetencyProfile):
        """Экспортировать результат в Notion базу."""
        
        page = await self.client.pages.create(
            parent={"database_id": self.database_id},
            properties={
                "Name": {"title": [{"text": {"content": f"{session.user.first_name} - {session.role_name}"}}]},
                "Score": {"number": session.total_score},
                "Role": {"select": {"name": session.role_name}},
                "Experience": {"select": {"name": session.experience_name}},
                "Level": {"select": {"name": profile.get_level()}},
                "Strengths": {"multi_select": [{"name": s} for s in profile.strengths]},
                "Growth Areas": {"multi_select": [{"name": g} for g in profile.growth_areas]},
                "Date": {"date": {"start": session.completed_at.isoformat()}},
                "Telegram": {"url": f"https://t.me/{session.user.username}"},
            },
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"text": {"content": session.report[:2000]}}]
                    }
                }
            ]
        )
        
        return page["id"]
```

### 4.3 Telegram Mini App

```
tg-bot/
├── miniapp/
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── QuestionCard.tsx
│   │   │   ├── ProgressBar.tsx
│   │   │   ├── CompetencyRadar.tsx
│   │   │   └── ReportView.tsx
│   │   └── hooks/
│   │       └── useTelegram.ts
│   └── vite.config.ts
```

**Преимущества Mini App:**
- Богатый UI (анимации, графики)
- Radar chart для компетенций
- Интерактивный отчёт
- Sharing результатов

---

## 🎯 ФАЗА 5: DevOps & Масштабирование (2-3 недели)

### 5.1 Docker

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей системы
RUN apt-get update && apt-get install -y \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY src/ src/
COPY *.py .

# Переменные окружения
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "src.bot.main"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  bot:
    build: .
    env_file: .env
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    depends_on:
      - redis
  
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  redis_data:
```

### 5.2 Переход на PostgreSQL

```python
# src/core/config.py

class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///diagnostic_bot.db"
    
    # Для продакшена:
    # database_url: str = "postgresql+asyncpg://user:pass@host:5432/dbname"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
```

### 5.3 Redis для кэширования

```python
# src/cache/redis_cache.py

import redis.asyncio as redis
import json

class CacheManager:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
    
    async def cache_analysis(self, session_id: int, question_num: int, analysis: dict):
        """Кэшировать анализ ответа."""
        key = f"analysis:{session_id}:{question_num}"
        await self.redis.setex(key, 3600, json.dumps(analysis))
    
    async def get_cached_analysis(self, session_id: int, question_num: int) -> dict | None:
        """Получить кэшированный анализ."""
        key = f"analysis:{session_id}:{question_num}"
        data = await self.redis.get(key)
        return json.loads(data) if data else None
    
    async def cache_question(self, context_hash: str, question: str):
        """Кэшировать сгенерированный вопрос."""
        key = f"question:{context_hash}"
        await self.redis.setex(key, 1800, question)  # 30 минут
```

---

## 📅 Таймлайн

| Фаза | Длительность | Приоритет | Статус |
|------|-------------|-----------|--------|
| 1. Стабилизация | 3-5 дней | 🔴 Критический | Pending |
| 2. Качество диагностики | 1-2 недели | 🟡 Высокий | Pending |
| 3. Аналитика | 2-3 недели | 🟢 Средний | Pending |
| 4. Интеграции | 3-4 недели | 🔵 Низкий | Pending |
| 5. DevOps | 2-3 недели | 🟣 Низкий | Pending |

**Общий срок**: 8-12 недель

---

## 🎯 Quick Wins (можно сделать сегодня)

1. **✅ Исправить JSON parsing** → +30% точности оценок
2. **✅ Добавить логирование сырых ответов AI** → отладка промптов
3. **✅ Typing indicator при генерации** → лучший UX
4. **✅ Retry при ошибках AI** → надёжность
5. **✅ Ограничение длины ответа** → защита от спама

---

## 📊 Метрики успеха

| Метрика | Текущее | Цель | Как измерять |
|---------|---------|------|--------------|
| JSON Parse Success | ~30% | 100% | Логи ошибок |
| Avg Response Time | 25-35 сек | <15 сек | Timing middleware |
| Completion Rate | ? | >80% | БД: started vs completed |
| User Satisfaction | ? | NPS >50 | Опрос после отчёта |
| Repeat Usage | ? | >20% | БД: users с >1 session |

---

## 🔗 Связанные документы

- `Roadmap.md` — оригинальная концепция
- `README.md` — документация проекта
- `requirements.txt` — зависимости
