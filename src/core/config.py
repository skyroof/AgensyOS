from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Конфигурация приложения."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # Telegram
    bot_token: str = Field(..., description="Telegram Bot Token")
    
    # AI (RouterAI - единый API для всех моделей)
    routerai_api_key: str = Field(..., description="RouterAI API Key")
    routerai_base_url: str = Field(
        default="https://routerai.ru/api/v1",
        description="RouterAI API Base URL"
    )
    
    # Модель для диагностики (можно менять на лету)
    # Доступные: anthropic/claude-sonnet-4.5, openai/gpt-4-turbo, google/gemini-2.0-flash, deepseek/deepseek-chat
    ai_model: str = Field(
        default="anthropic/claude-sonnet-4.5",
        description="AI model identifier for RouterAI"
    )
    
    # Database (для MVP не нужно)
    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/diagnostic_bot",
        description="PostgreSQL connection string"
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string"
    )
    
    # Monitoring
    sentry_dsn: str | None = Field(
        default=None,
        description="Sentry DSN for error tracking"
    )

    # App
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="text", description="Logging format: text or json")
    
    # Payments (Telegram Payments API)
    payment_provider_token: str = Field(
        default="",
        description="Payment provider token from @BotFather"
    )
    
    # Pricing (in kopecks/cents)
    price_single: int = Field(default=29900, description="Price for 1 diagnostic in kopecks")
    price_pack3: int = Field(default=69900, description="Price for 3 diagnostics in kopecks")
    price_pack10: int = Field(default=199000, description="Price for 10 diagnostics in kopecks")
    
    # Admin
    admin_telegram_id: int = Field(
        default=0,
        description="Admin Telegram user ID for notifications"
    )


@lru_cache
def get_settings() -> Settings:
    """Singleton для настроек."""
    return Settings()

