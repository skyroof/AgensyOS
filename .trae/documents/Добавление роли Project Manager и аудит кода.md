## Добавление роли Project Manager и аудит кода

### 1. Обновление UI и логики выбора ролей
*   **[inline.py](file:///c:/Users/ilayt/OneDrive/Desktop/TG-BOT/src/bot/keyboards/inline.py)**: Добавление кнопки "⚙️ Проджект" в `get_role_keyboard`.
*   **[reply.py](file:///c:/Users/ilayt/OneDrive/Desktop/TG-BOT/src/bot/keyboards/reply.py)**: Добавление кнопки "⚙️ Проджект" в `get_role_reply_keyboard`.
*   **[start.py](file:///c:/Users/ilayt/OneDrive/Desktop/TG-BOT/src/bot/handlers/start.py)**: Рефакторинг `process_role` — использование маппинга вместо `if/else`.

### 2. Подготовка AI-контента для проджектов
*   **[questions.py](file:///c:/Users/ilayt/OneDrive/Desktop/TG-BOT/src/core/prompts/questions.py)**: Создание базы вопросов (Delivery, Agile, Waterfall, Stakeholders, Risks).
*   **[cached_questions.py](file:///c:/Users/ilayt/OneDrive/Desktop/TG-BOT/src/ai/cached_questions.py)**: Добавление стартовых вопросов для всех уровней опыта (Junior-Lead).
*   **[system.py](file:///c:/Users/ilayt/OneDrive/Desktop/TG-BOT/src/core/prompts/system.py)**: Настройка контекста роли для анализатора.

### 3. Настройка аналитики и рекомендаций
*   **[competency_profile.py](file:///c:/Users/ilayt/OneDrive/Desktop/TG-BOT/src/analytics/competency_profile.py)**: Добавление книг и курсов (PMBOK, Deadlines, Critical Path).
*   **[pdp.py](file:///c:/Users/ilayt/OneDrive/Desktop/TG-BOT/src/analytics/pdp.py)**: Специфические задания для развития навыков управления проектами.

### 4. Аудит и исправление ошибок
*   Устранение жесткой привязки к двум ролям в `questions.py` и `pdp.py`.
*   Проверка всех циклов и условий на предмет исключений.
*   Обновление PRD в [ABOUTTG.md](file:///c:/Users/ilayt/OneDrive/Desktop/TG-BOT/ABOUTTG.md).

Жду подтверждения для начала реализации.