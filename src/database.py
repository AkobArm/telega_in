from datetime import datetime
from typing import Any, Dict, Optional

import psycopg2
from loguru import logger
from psycopg2.extensions import connection
from psycopg2.extras import DictCursor
from psycopg2.pool import SimpleConnectionPool

from config import settings


class Database:
    """
    Класс для работы с базой данных PostgreSQL.

    Attributes:
        conn_params: Параметры подключения к базе данных
    """

    def __init__(self) -> None:
        """Инициализация параметров подключения к базе данных."""
        self.conn_params: Dict[str, Any] = {
            'host': settings.DB_HOST,
            'port': settings.DB_PORT,
            'user': settings.DB_USER,
            'password': settings.DB_PASSWORD,
            'cursor_factory': DictCursor
        }
        self.pool: Optional[SimpleConnectionPool] = None

    def _init_pool(self) -> None:
        """Инициализация пула соединений."""
        if self.pool is None:
            conn_params = self.conn_params.copy()
            conn_params['database'] = settings.DB_NAME
            self.pool = SimpleConnectionPool(
                minconn=5,
                maxconn=20,
                **conn_params
            )

    def get_connection(self) -> connection:
        """Получение соединения из пула."""
        if self.pool is None:
            self._init_pool()
        return self.pool.getconn()

    def return_connection(self, conn: connection) -> None:
        """Возврат соединения в пул."""
        if self.pool is not None:
            self.pool.putconn(conn)

    def create_database(self) -> None:
        """Создает базу данных, если она не существует."""
        conn_params = self.conn_params.copy()
        conn_params['database'] = settings.DB_NAME

        try:
            with psycopg2.connect(**conn_params) as conn:
                conn.autocommit = True

                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT 1 FROM pg_database WHERE datname = %s",
                        (settings.DB_NAME,)
                    )
                    exists = cur.fetchone()

                    if not exists:
                        cur.execute(f'CREATE DATABASE {settings.DB_NAME}')
                        logger.info(f"База данных {settings.DB_NAME} создана")
        except Exception as e:
            logger.error(f"Ошибка создания базы данных: {e}")
            raise

    def init_db(self) -> None:
        """Инициализация схемы базы данных."""
        self.create_database()

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                                        CREATE TABLE IF NOT EXISTS telegram_posts (
                                            id SERIAL PRIMARY KEY,
                                            channel_id TEXT NOT NULL,
                                            message_id BIGINT NOT NULL,
                                            published_at TIMESTAMP NOT NULL,
                                            text TEXT,
                                            views INTEGER,
                                            collected_at TIMESTAMP DEFAULT NOW()
                                        )
                                    """)

                cur.execute(
                    """
                                        CREATE UNIQUE INDEX IF NOT EXISTS 
                                        telegram_posts_channel_message_idx ON 
                                        telegram_posts(channel_id, message_id)
                                    """)

                cur.execute(
                    """
                                        CREATE INDEX IF NOT EXISTS 
                                        telegram_posts_published_at_idx ON 
                                        telegram_posts(published_at)
                                    """)
            conn.commit()
            logger.info("Схема базы данных успешно инициализирована")

    def save_message(
            self,
            channel_id: str,
            message_id: int,
            published_at: datetime,
            text: Optional[str],
            views: Optional[int]
    ) -> bool:
        """
        Сохранение сообщения в базу данных.

        Args:
            channel_id: ID канала
            message_id: ID сообщения
            published_at: Дата публикации
            text: Текст сообщения
            views: Количество просмотров

        Returns:
            bool: True если сообщение успешно сохранено, False в случае ошибки

        Note:
            Метод использует ON CONFLICT DO NOTHING для предотвращения дублирования
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO telegram_posts 
                    (channel_id, message_id, published_at, text, views)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (channel_id, message_id) DO NOTHING
                    RETURNING id
                    """, (channel_id, message_id, published_at, text, views))
                
                result = cur.fetchone()
                conn.commit()
                
                if result:
                    logger.debug(
                        f"Сохранено новое сообщение {message_id} "
                        f"из канала {channel_id}"
                    )
                return True
        except Exception as e:
            logger.error(f"Ошибка сохранения сообщения: {e}")
            conn.rollback()
            return False
        finally:
            self.return_connection(conn)
