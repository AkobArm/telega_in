from pathlib import Path
from typing import List

from loguru import logger
from pydantic import (Field, field_validator, model_validator, PostgresDsn, ValidationError)
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / '.env'


class Settings(BaseSettings):
    """
    Настройки приложения.
    """

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore'
    )

    API_ID: str = Field(
        ...,
        description="Telegram API ID",
        examples=["12345678"]
    )
    API_HASH: str = Field(
        ...,
        description="Telegram API Hash",
        examples=["0123456789abcdef0123456789abcdef"]
    )
    SESSION_NAME: str = Field(
        default="collector",
        description="Telegram session name"
    )

    DB_HOST: str = Field(default="localhost", description="Database host")
    DB_PORT: int = Field(default=5432, description="Database port")
    DB_NAME: str = Field(default="telegram_collector", description="Database name")
    DB_USER: str = Field(default="postgres", description="Database user")
    DB_PASSWORD: str = Field(default="postgres", description="Database password")

    DATABASE_URL: PostgresDsn | None = Field(
        default=None,
        description="Optional database URL. If not set, will be built from individual settings"
    )

    TELEGRAM_CHANNELS: str = Field(
        default="@telegram",
        description="Comma-separated list of Telegram channels to monitor",
        examples=["@channel1,@channel2,t.me/channel3"]
    )
    MESSAGES_LIMIT: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Number of messages to collect from each channel"
    )
    COLLECTION_INTERVAL: int = Field(
        default=60,
        ge=1,
        description="Collection interval in minutes"
    )

    LOG_LEVEL: str = Field(
        default="INFO",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        description="Logging level"
    )

    @field_validator("TELEGRAM_CHANNELS", mode='after')
    def split_channels(cls, v: str) -> List[str]:
        """Разделяет строку каналов на список и валидирует форматы."""
        channels = [c.strip() for c in v.split(',') if c.strip()]
        if not channels:
            raise ValueError("Необходимо указать хотя бы один канал")
        
        for channel in channels:
            if not (
                channel.startswith('@') or
                channel.startswith('https://t.me/') or
                channel.startswith('-100') or
                'joinchat' in channel
            ):
                raise ValueError(
                    f"Неверный формат канала: {channel}. "
                    "Поддерживаемые форматы: @username, https://t.me/channel, "
                    "-100<id>, https://t.me/joinchat/..."
                )
        return channels

    @model_validator(mode='after')
    def assemble_db_url(self) -> 'Settings':
        """Собирает URL базы данных из отдельных компонентов."""
        if not self.DATABASE_URL:
            self.DATABASE_URL = PostgresDsn.build(
                scheme="postgresql",
                username=self.DB_USER,
                password=self.DB_PASSWORD,
                host=self.DB_HOST,
                port=self.DB_PORT,
                path=self.DB_NAME
            )
        return self


try:
    settings = Settings()
except ValidationError as e:
    logger.error(f"Ошибка конфигурации: {e}")
    print("Ошибка загрузки настроек:")
    print("\nУбедитесь, что файл .env создан и содержит необходимые настройки:")
    print("Обязательные параметры:")
    print("- API_ID (получить на https://my.telegram.org/apps)")
    print("- API_HASH (получить на https://my.telegram.org/apps)")
    print("- TELEGRAM_CHANNELS (список каналов через запятую)")
    raise SystemExit(1)

API_ID = settings.API_ID
API_HASH = settings.API_HASH
SESSION_NAME = settings.SESSION_NAME
DB_HOST = settings.DB_HOST
DB_PORT = settings.DB_PORT
DB_NAME = settings.DB_NAME
DB_USER = settings.DB_USER
DB_PASSWORD = settings.DB_PASSWORD
DATABASE_URL = settings.DATABASE_URL
TELEGRAM_CHANNELS = settings.TELEGRAM_CHANNELS
MESSAGES_LIMIT = settings.MESSAGES_LIMIT
COLLECTION_INTERVAL = settings.COLLECTION_INTERVAL
LOG_LEVEL = settings.LOG_LEVEL
