import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional, TypedDict

from apscheduler.schedulers.blocking import BlockingScheduler
from loguru import logger
from telethon import TelegramClient
from telethon.errors import (
    ChannelPrivateError,
    ChatAdminRequiredError,
    FloodWaitError
)
from telethon.tl.types import Channel, Message

from config import settings
from database import Database


STAT_PROCESSED = 'processed'
STAT_SAVED = 'saved'
STAT_ERRORS = 'errors'


class CollectionStats(TypedDict):
    processed: int
    saved: int
    errors: int


class TelegramCollector:
    """
    Коллектор сообщений из Telegram каналов.

    Attributes:
        db: Интерфейс базы данных
        scheduler: Планировщик заданий
        collection_stats: Статистика сбора сообщений
    """

    def __init__(self) -> None:
        """Инициализация коллектора."""
        self.db = Database()
        self.scheduler = BlockingScheduler()
        self.collection_stats: Dict[str, CollectionStats] = {}

    def _create_client(self) -> TelegramClient:
        """Создание нового клиента Telegram."""
        return TelegramClient(
            settings.SESSION_NAME,
            settings.API_ID,
            settings.API_HASH
        )

    async def collect_channel_messages(self, client: TelegramClient, channel: str) -> bool:
        """
        Сбор сообщений из одного канала.

        Args:
            client: Клиент Telegram API
            channel: Идентификатор канала (username, ссылка или ID)

        Returns:
            bool: True если сбор прошел успешно, False в случае ошибки

        Raises:
            ChannelPrivateError: Если канал приватный
            ChatAdminRequiredError: Если требуются права администратора
            FloodWaitError: Если превышен лимит запросов
        """
        start_time = time.time()
        try:
            logger.info(f"Начало сбора сообщений из канала: {channel}")
            entity: Channel = await client.get_entity(channel)
            messages: List[Message] = await client.get_messages(
                entity,
                limit=settings.MESSAGES_LIMIT
            )

            self.collection_stats[channel] = {
                STAT_PROCESSED: len(messages),
                STAT_SAVED: 0,
                STAT_ERRORS: 0
            }

            for message in messages:
                views: Optional[int] = getattr(message, 'views', None)

                if self.db.save_message(
                        channel_id=str(entity.id),
                        message_id=message.id,
                        published_at=message.date,
                        text=message.text,
                        views=views
                ):
                    self.collection_stats[channel][STAT_SAVED] += 1
                else:
                    self.collection_stats[channel][STAT_ERRORS] += 1

            logger.info(
                f"Статистика канала {channel}: "
                f"обработано={self.collection_stats[channel][STAT_PROCESSED]}, "
                f"сохранено={self.collection_stats[channel][STAT_SAVED]}, "
                f"ошибок={self.collection_stats[channel][STAT_ERRORS]}"
            )
            return True

        except FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"Превышен лимит запросов, ожидание {wait_time} секунд")
            await asyncio.sleep(wait_time)
            return False
        except ChannelPrivateError:
            logger.error(f"Нет доступа к приватному каналу: {channel}")
            return False
        except ChatAdminRequiredError:
            logger.error(f"Требуются права администратора для канала: {channel}")
            return False
        except Exception as e:
            logger.exception(f"Ошибка сбора сообщений из канала {channel}: {e}")
            return False
        finally:
            duration = time.time() - start_time
            logger.info(f"Время сбора для канала {channel}: {duration:.2f} секунд")

    async def validate_channel(self, client: TelegramClient, channel: str) -> bool:
        """
        Проверка доступности и валидности канала.

        Args:
            client: Клиент Telegram API
            channel: Идентификатор канала для проверки

        Returns:
            bool: True если канал доступен и валиден
        """
        try:
            await client.get_entity(channel)
            logger.info(f"Канал {channel} успешно проверен")
            return True
        except ValueError as e:
            logger.error(f"Неверный формат канала {channel}: {e}")
            return False
        except Exception as e:
            logger.error(f"Нет доступа к каналу {channel}: {e}")
            return False

    async def collect_all_channels(self) -> None:
        """
        Сбор сообщений из всех настроенных каналов.
        """
        success = False
        self.collection_stats = {}

        client = self._create_client()
        async with client:
            tasks = []
            for channel in settings.TELEGRAM_CHANNELS:
                if channel := channel.strip():
                    if await self.validate_channel(client, channel):
                        tasks.append(self.collect_channel_messages(client, channel))
            
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                success = any(result is True for result in results)

        if not success:
            logger.critical("Не удалось собрать сообщения из какого-либо канала!")

        self._log_collection_summary()

    def _log_collection_summary(self) -> None:
        """Логирование общей статистики сбора."""
        total_processed = sum(
            stats[STAT_PROCESSED] for stats in self.collection_stats.values()
        )
        total_saved = sum(
            stats[STAT_SAVED] for stats in self.collection_stats.values()
        )
        total_errors = sum(
            stats[STAT_ERRORS] for stats in self.collection_stats.values()
        )

        logger.info(
            f"Итоги сбора: "
            f"каналов={len(self.collection_stats)}, "
            f"обработано={total_processed}, "
            f"сохранено={total_saved}, "
            f"ошибок={total_errors}"
        )

    def run_collection(self) -> None:
        """Wrapper для запуска асинхронной функции сбора."""
        try:
            asyncio.run(self.collect_all_channels())
        except Exception as e:
            logger.exception(f"Критическая ошибка в процессе сбора данных: {e}")

    def start_collection(self) -> None:
        """
        Запуск процесса сбора сообщений.
        """
        self.db.init_db()

        logger.remove()
        logger.add(
            lambda msg: print(msg),
            level=settings.LOG_LEVEL
        )

        self.scheduler.add_job(
            self.run_collection,
            'interval',
            minutes=settings.COLLECTION_INTERVAL,
            next_run_time=datetime.now(),
            id='telegram_collector',
            name='Telegram Channel Collection',
            max_instances=1,
            coalesce=True,
            misfire_grace_time=None
        )

        try:
            logger.info(
                f"Запуск коллектора. "
                f"Интервал: {settings.COLLECTION_INTERVAL} минут. "
                f"Каналов: {len(settings.TELEGRAM_CHANNELS)}"
            )
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Коллектор остановлен пользователем")
        except Exception as e:
            logger.exception(f"Коллектор остановлен из-за ошибки: {e}")


if __name__ == "__main__":
    collector = TelegramCollector()
    collector.start_collection()
