"""
SQLAlchemy модели для хранения данных диагностики.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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
