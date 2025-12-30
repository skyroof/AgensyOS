"""
SQLAlchemy модели для хранения данных диагностики.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import quoted_name


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


class User(Base):
    """Пользователь Telegram."""
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Связь с сессиями диагностики
    sessions: Mapped[list["DiagnosticSession"]] = relationship(back_populates="user")
    
    def __repr__(self) -> str:
        return f"<User {self.telegram_id} @{self.username}>"


class DiagnosticSession(Base):
    """Сессия диагностики (одно прохождение)."""
    
    __tablename__ = "diagnostic_sessions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    
    # Параметры диагностики
    role: Mapped[str] = mapped_column(String(50))  # designer / product
    role_name: Mapped[str] = mapped_column(String(100))
    experience: Mapped[str] = mapped_column(String(50))  # junior / middle / senior / lead
    experience_name: Mapped[str] = mapped_column(String(100))
    
    # Статус
    status: Mapped[str] = mapped_column(String(20), default="in_progress")  # in_progress / completed / abandoned
    current_question: Mapped[int] = mapped_column(Integer, default=1)
    
    # Режим диагностики (монетизация)
    # "mode" - зарезервированное слово в PostgreSQL, используем quoted_name
    diagnostic_mode: Mapped[str] = mapped_column(quoted_name("mode", quote=True), String(10), default="full")  # demo / full
    
    # Итоговые баллы
    total_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hard_skills_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    soft_skills_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    thinking_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mindset_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Детальные данные (JSON)
    conversation_history: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    analysis_history: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Итоговый отчёт
    report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Временные метки
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Связи
    user: Mapped["User"] = relationship(back_populates="sessions")
    answers: Mapped[list["Answer"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<DiagnosticSession {self.id} user={self.user_id} role={self.role}>"


class Answer(Base):
    """Ответ на вопрос."""
    
    __tablename__ = "answers"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("diagnostic_sessions.id"), index=True)
    
    question_number: Mapped[int] = mapped_column(Integer)
    question_text: Mapped[str] = mapped_column(Text)
    answer_text: Mapped[str] = mapped_column(Text)
    
    # Оценки от AI
    depth_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    self_awareness_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    structure_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    honesty_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expertise_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Анализ от AI (JSON)
    analysis: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Связь
    session: Mapped["DiagnosticSession"] = relationship(back_populates="answers")
    
    def __repr__(self) -> str:
        return f"<Answer {self.id} session={self.session_id} q={self.question_number}>"


class Feedback(Base):
    """Обратная связь от пользователя о качестве диагностики."""
    
    __tablename__ = "feedbacks"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("diagnostic_sessions.id"), unique=True, index=True)
    
    # Оценка от 1 до 10
    rating: Mapped[int] = mapped_column(Integer)
    
    # Опциональный комментарий
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Связь
    session: Mapped["DiagnosticSession"] = relationship()
    
    def __repr__(self) -> str:
        return f"<Feedback session={self.session_id} rating={self.rating}>"


# ==================== PDP 2.0 ====================

class PdpPlan(Base):
    """
    Персональный план развития 2.0.
    
    Привязан к сессии диагностики и содержит недельный план.
    """
    
    __tablename__ = "pdp_plans"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("diagnostic_sessions.id"), index=True)
    
    # Настройки плана
    focus_skills: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Топ-3 навыка для развития
    daily_time_minutes: Mapped[int] = mapped_column(Integer, default=30)  # 15/30/60 минут в день
    learning_style: Mapped[str] = mapped_column(String(20), default="mixed")  # read/watch/do/mixed
    
    # Статус
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/paused/completed
    current_week: Mapped[int] = mapped_column(Integer, default=1)  # 1-4
    current_day: Mapped[int] = mapped_column(Integer, default=1)  # 1-30
    
    # Прогресс
    total_tasks: Mapped[int] = mapped_column(Integer, default=0)
    completed_tasks: Mapped[int] = mapped_column(Integer, default=0)
    skipped_tasks: Mapped[int] = mapped_column(Integer, default=0)
    
    # Стрики и геймификация
    current_streak: Mapped[int] = mapped_column(Integer, default=0)  # Дней подряд
    best_streak: Mapped[int] = mapped_column(Integer, default=0)
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    badges: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Полученные бейджи
    
    # Временные метки
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Связи
    user: Mapped["User"] = relationship()
    session: Mapped["DiagnosticSession"] = relationship()
    tasks: Mapped[list["PdpTask"]] = relationship(back_populates="plan", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<PdpPlan {self.id} user={self.user_id} week={self.current_week}>"


class PdpTask(Base):
    """
    Задача в плане развития.
    
    Микро-шаг на 15-30 минут с конкретным действием.
    """
    
    __tablename__ = "pdp_tasks"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("pdp_plans.id"), index=True)
    
    # Позиция в плане
    week: Mapped[int] = mapped_column(Integer)  # 1-4
    day: Mapped[int] = mapped_column(Integer)  # 1-7 (Пн-Вс)
    order: Mapped[int] = mapped_column(Integer, default=1)  # Порядок в дне (если несколько задач)
    
    # Контент задачи
    skill: Mapped[str] = mapped_column(String(50))  # Какой навык развивает
    skill_name: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(255))  # Краткое название
    description: Mapped[str] = mapped_column(Text)  # Полное описание что делать
    duration_minutes: Mapped[int] = mapped_column(Integer)  # Сколько минут
    
    # Тип задачи
    task_type: Mapped[str] = mapped_column(String(20))  # read/watch/practice/reflect/discuss
    
    # Ресурс (опционально)
    resource_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # book/course/article/video
    resource_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    resource_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Статус выполнения
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/completed/skipped
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    user_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Заметка пользователя
    
    # Связь
    plan: Mapped["PdpPlan"] = relationship(back_populates="tasks")
    
    def __repr__(self) -> str:
        return f"<PdpTask {self.id} W{self.week}D{self.day} '{self.title[:20]}'>"


class PdpReminder(Base):
    """Настройки напоминаний для PDP."""
    
    __tablename__ = "pdp_reminders"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    
    # Настройки
    enabled: Mapped[bool] = mapped_column(default=True)
    reminder_time: Mapped[str] = mapped_column(String(5), default="10:00")  # HH:MM
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow")
    
    # Последнее напоминание
    last_reminder_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    def __repr__(self) -> str:
        return f"<PdpReminder user={self.user_id} time={self.reminder_time}>"


class DiagnosticReminder(Base):
    """
    Напоминание о повторной диагностике.
    
    Планируется после завершения диагностики (через 30 дней).
    """
    
    __tablename__ = "diagnostic_reminders"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("diagnostic_sessions.id"), index=True)
    
    # Когда отправить
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    
    # Тип напоминания
    reminder_type: Mapped[str] = mapped_column(String(20), default="30_days")  # 30_days / 7_days / custom
    
    # Статус
    sent: Mapped[bool] = mapped_column(default=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Отменено пользователем
    cancelled: Mapped[bool] = mapped_column(default=False)
    
    # Для персонализации
    last_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    focus_skill: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Главная зона роста
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Связи
    user: Mapped["User"] = relationship()
    session: Mapped["DiagnosticSession"] = relationship()
    
    def __repr__(self) -> str:
        return f"<DiagnosticReminder user={self.user_id} scheduled={self.scheduled_at} sent={self.sent}>"


class UserSettings(Base):
    """Настройки пользователя."""
    
    __tablename__ = "user_settings"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    
    # Напоминания о диагностике
    diagnostic_reminders_enabled: Mapped[bool] = mapped_column(default=True)
    
    # Напоминания PDP
    pdp_reminders_enabled: Mapped[bool] = mapped_column(default=True)
    
    # Часовой пояс
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    def __repr__(self) -> str:
        return f"<UserSettings user={self.user_id}>"


# ==================== МОНЕТИЗАЦИЯ ====================

class UserBalance(Base):
    """
    Баланс диагностик пользователя.
    
    Модель Pay-per-Diagnostic: демо бесплатно, остальное платно.
    """
    
    __tablename__ = "user_balances"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    
    # Демо использовано?
    demo_used: Mapped[bool] = mapped_column(default=False)
    
    # Баланс оплаченных диагностик
    diagnostics_balance: Mapped[int] = mapped_column(Integer, default=0)
    
    # Статистика
    total_purchased: Mapped[int] = mapped_column(Integer, default=0)  # Всего куплено
    total_used: Mapped[int] = mapped_column(Integer, default=0)  # Всего использовано (включая демо)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Связь
    user: Mapped["User"] = relationship()
    
    def __repr__(self) -> str:
        return f"<UserBalance user={self.user_id} balance={self.diagnostics_balance} demo_used={self.demo_used}>"


class Payment(Base):
    """
    Платёж за диагностику.
    
    Хранит информацию о всех платежах через Telegram Payments.
    """
    
    __tablename__ = "payments"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    
    # Что куплено
    pack_type: Mapped[str] = mapped_column(String(20))  # single / pack3 / pack10
    diagnostics_count: Mapped[int] = mapped_column(Integer)  # 1 / 3 / 10
    
    # Сумма
    amount: Mapped[int] = mapped_column(Integer)  # В копейках (29900 = 299₽)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    
    # Промокод (если применён)
    promocode_id: Mapped[Optional[int]] = mapped_column(ForeignKey("promocodes.id"), nullable=True)
    discount_amount: Mapped[int] = mapped_column(Integer, default=0)  # Скидка в копейках
    final_amount: Mapped[int] = mapped_column(Integer)  # Итоговая сумма
    
    # Telegram Payments данные
    telegram_payment_charge_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider_payment_charge_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    invoice_payload: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Статус
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending / success / failed / refunded
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Связи
    user: Mapped["User"] = relationship()
    promocode: Mapped[Optional["Promocode"]] = relationship()
    
    def __repr__(self) -> str:
        return f"<Payment {self.id} user={self.user_id} {self.pack_type} {self.final_amount/100}₽ {self.status}>"


class Promocode(Base):
    """
    Промокод для скидки.
    
    MAXVISUAL100 = 100% скидка.
    """
    
    __tablename__ = "promocodes"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Код (уникальный, uppercase)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    
    # Скидка
    discount_percent: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    discount_amount: Mapped[int] = mapped_column(Integer, default=0)  # Фиксированная сумма в копейках
    
    # Ограничения
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    max_uses: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # None = безлимит
    current_uses: Mapped[int] = mapped_column(Integer, default=0)
    
    # К каким пакетам применим (JSON: ["single", "pack3", "pack10"])
    applicable_packs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Метаданные
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # admin username
    is_active: Mapped[bool] = mapped_column(default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<Promocode {self.code} -{self.discount_percent}% uses={self.current_uses}/{self.max_uses}>"


class PromocodeUse(Base):
    """История использования промокодов."""
    
    __tablename__ = "promocode_uses"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    promocode_id: Mapped[int] = mapped_column(ForeignKey("promocodes.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), index=True)
    
    discount_applied: Mapped[int] = mapped_column(Integer)  # Сколько сэкономил в копейках
    
    used_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Связи
    promocode: Mapped["Promocode"] = relationship()
    user: Mapped["User"] = relationship()
    payment: Mapped["Payment"] = relationship()
    
    def __repr__(self) -> str:
        return f"<PromocodeUse promo={self.promocode_id} user={self.user_id}>"
