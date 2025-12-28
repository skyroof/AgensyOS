# 🚀 IMPROVEMENTS: План развития Deep Diagnostic Bot

> Глубокий анализ текущего состояния + стратегия улучшений

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
        return DEFAULT_ANALYSIS
```

### 1.2 Параллельные AI-запросы

```python
# src/bot/handlers/diagnostic.py

import asyncio

async def process_answer(message: Message, state: FSMContext, bot: Bot):
    """Оптимизированная обработка с параллельными запросами."""
    
    thinking_msg = await message.answer("🧠 Анализирую ответ...")
    
    # ПАРАЛЛЕЛЬНО: анализ + генерация следующего вопроса
    analysis_task = asyncio.create_task(
        analyze_answer(current_question, message.text, data["role"])
    )
    
    next_question_num = data["current_question"] + 1
    question_task = None
    
    if next_question_num <= TOTAL_QUESTIONS:
        question_task = asyncio.create_task(
            generate_question(
                role=data["role"],
                role_name=data["role_name"],
                experience=data["experience_name"],
                question_number=next_question_num,
                conversation_history=conversation_history,
                analysis_history=analysis_history,
            )
        )
    
    # Ждём анализ
    analysis = await analysis_task
    analysis_history.append(analysis)
    
    # Ждём вопрос
    if question_task:
        next_question = await question_task
    
    # Экономия: ~18-26 сек вместо 25-35 сек (-30%)
```

### 1.3 Streaming для генерации отчёта

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
```

### 1.4 Логирование сырых ответов AI

```python
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
def calibrate_scores(scores: dict, experience: str) -> dict:
    """
    Калибровка оценок относительно заявленного опыта.
    
    Junior с оценкой 7 — это хорошо.
    Lead с оценкой 7 — это посредственно.
    """
    experience_baseline = {
        "junior": 4,
        "middle": 5,
        "senior": 6,
        "lead": 7,
    }
    
    baseline = experience_baseline.get(experience, 5)
    
    calibrated = {}
    for metric, value in scores.items():
        if value >= baseline + 2:
            calibrated[metric] = {"value": value, "assessment": "exceeds"}
        elif value >= baseline:
            calibrated[metric] = {"value": value, "assessment": "meets"}
        else:
            calibrated[metric] = {"value": value, "assessment": "below"}
    
    return calibrated
```

### 2.3 Адаптивная сложность вопросов

```python
def get_question_difficulty(analysis_history: list[dict]) -> str:
    """Определить сложность следующего вопроса."""
    if not analysis_history:
        return "standard"
    
    recent = analysis_history[-3:]
    avg_scores = []
    
    for analysis in recent:
        scores = analysis.get("scores", {})
        avg = sum(scores.values()) / len(scores) if scores else 5
        avg_scores.append(avg)
    
    overall_avg = sum(avg_scores) / len(avg_scores)
    
    if overall_avg >= 8:
        return "challenging"  # Провокационные вопросы
    elif overall_avg >= 6:
        return "standard"
    else:
        return "supportive"  # Поддерживающие вопросы
```

### 2.4 Детекция паттернов

```python
SUSPICIOUS_PATTERNS = {
    "rehearsed": [r"как я уже говорил", r"обычно в таких случаях"],
    "evasive": [r"сложно сказать", r"это зависит", r"не помню точно"],
    "overconfident": [r"я всегда", r"у меня никогда не было проблем"],
}

def detect_patterns(answer: str) -> list[str]:
    """Выявить подозрительные паттерны."""
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
@dataclass
class CompetencyProfile:
    role: str
    experience: str
    total_score: int
    
    # Детальные оценки
    hard_skills: dict[str, float]
    soft_skills: dict[str, float]
    thinking: dict[str, float]
    mindset: dict[str, float]
    
    # Топ-3
    strengths: list[str]
    growth_areas: list[str]
    
    # Психологический профиль
    thinking_style: str  # analytical / creative / strategic
    communication_style: str  # direct / diplomatic
    motivation_driver: str  # growth / recognition / stability
    
    # Бенчмарк
    percentile: int
    
    # Рекомендации
    development_plan: list[str]
```

### 3.2 Бенчмаркинг

```python
async def calculate_percentile(session: DiagnosticSession) -> int:
    """Перцентиль среди аналогичных специалистов."""
    async with get_session() as db:
        similar = await db.execute(
            select(DiagnosticSession)
            .where(
                DiagnosticSession.role == session.role,
                DiagnosticSession.status == "completed",
            )
        )
        
        all_scores = [s.total_score for s in similar.scalars()]
        
        if len(all_scores) < 10:
            return 50
        
        below = sum(1 for s in all_scores if s < session.total_score)
        return int((below / len(all_scores)) * 100)
```

### 3.3 Трекинг прогресса

```python
@dataclass
class ProgressReport:
    sessions_count: int
    first_score: int
    current_score: int
    score_change: int
    trend: str  # growing / stable / declining
    improved_areas: list[str]
    declined_areas: list[str]


async def get_progress(user_id: int) -> ProgressReport | None:
    """Прогресс между диагностиками."""
    sessions = await get_user_sessions(user_id)
    
    if len(sessions) < 2:
        return None
    
    first, last = sessions[0], sessions[-1]
    change = last.total_score - first.total_score
    
    return ProgressReport(
        sessions_count=len(sessions),
        first_score=first.total_score,
        current_score=last.total_score,
        score_change=change,
        trend="growing" if change > 5 else "declining" if change < -5 else "stable",
        improved_areas=find_improvements(first, last),
        declined_areas=find_declines(first, last),
    )
```

---

## 🎯 ФАЗА 4: Интеграции (3-4 недели)

### 4.1 Webhook API

```python
@app.post("/webhook/{webhook_id}")
async def send_result(webhook_id: str, result: DiagnosticResult):
    webhook_url = await get_webhook_url(webhook_id)
    async with httpx.AsyncClient() as client:
        await client.post(webhook_url, json=result.dict())
```

### 4.2 Notion интеграция

```python
class NotionExporter:
    async def export_session(self, session, profile):
        await self.client.pages.create(
            parent={"database_id": self.database_id},
            properties={
                "Name": {"title": [{"text": {"content": f"{session.user.first_name}"}}]},
                "Score": {"number": session.total_score},
                "Role": {"select": {"name": session.role_name}},
                "Strengths": {"multi_select": [{"name": s} for s in profile.strengths]},
            }
        )
```

### 4.3 Telegram Mini App

Преимущества:
- Radar chart для компетенций
- Интерактивный отчёт
- Красивая анимация прогресса
- Sharing результатов

---

## 🎯 ФАЗА 5: DevOps (2-3 недели)

### 5.1 Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y fonts-dejavu-core
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ src/
CMD ["python", "-m", "src.bot.main"]
```

### 5.2 PostgreSQL + Redis

```python
class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://user:pass@host:5432/db"
    redis_url: str = "redis://localhost:6379/0"
```

---

## 📅 Таймлайн

| Фаза | Срок | Приоритет |
|------|------|-----------|
| 1. Стабилизация | 3-5 дней | 🔴 Критический |
| 2. Качество | 1-2 недели | 🟡 Высокий |
| 3. Аналитика | 2-3 недели | 🟢 Средний |
| 4. Интеграции | 3-4 недели | 🔵 Низкий |
| 5. DevOps | 2-3 недели | 🟣 Низкий |

---

## 🎯 Quick Wins (сегодня)

1. ✅ **Исправить JSON parsing** → +30% точности
2. ✅ **Логировать сырые ответы AI** → отладка
3. ✅ **Typing indicator при генерации** → UX
4. ✅ **Retry при ошибках AI** → надёжность
5. ✅ **Параллельные запросы** → -30% время ответа

---

## 📊 Метрики успеха

| Метрика | Текущее | Цель |
|---------|---------|------|
| JSON Parse Success | ~30% | 100% |
| Avg Response Time | 25-35 сек | <15 сек |
| Completion Rate | ? | >80% |
| User Satisfaction | ? | NPS >50 |

