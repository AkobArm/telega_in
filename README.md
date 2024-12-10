# Сборщик сообщений из Telegram каналов

Скрипт для автоматического сбора сообщений из Telegram каналов с сохранением в
PostgreSQL.

## Возможности

- Сбор последних 50 сообщений из указанных каналов
- Поддержка публичных и приватных каналов
- Параллельный сбор данных
- Автоматический запуск каждый час
- Сохранение в PostgreSQL с предотвращением дублирования
- Сбор метаданных (просмотры, дата публикации)
- Поддержка Docker

## Системные требования

- Python 3.10+
- PostgreSQL
- Docker и Docker Compose (опционально)

## Установка

### 1. Получение API-ключей Telegram

1. Зайдите на сайт [my.telegram.org/apps](https://my.telegram.org/apps)
2. Авторизуйтесь в своём аккаунте Telegram
3. Создайте новое приложение
4. Сохраните полученные `API_ID` и `API_HASH`

### 2. Локальная установка

1. Клонируйте репозиторий:

```bash
git clone url
cd telegram_collector
```

2. Создайте виртуальное окружение:

```bash
python -m venv venv
source venv/bin/activate # для Linux/Mac
venv\Scripts\activate # для Windows
```

3. Установите зависимости:

```bash
pip install -r requirements.txt
```

4. Создайте конфигурационный файл:

```bash
cp .env.example .env
```

5. Создайте сессию Telegram:

```bash
python src/create_session.py
```

При первом запуске потребуется:
- Ввести номер телефона
- Ввести код подтверждения из Telegram

После этого будет создан файл `collector.session`

### 3. Установка через Docker

1. Соберите Docker-образ:

```bash
docker-compose -f docker/docker-compose.yml build
```

2. Создайте и настройте файл .env:

```bash
cp .env.example .env
```

## Настройка

Отредактируйте файл `.env`:

```env
# Учётные данные Telegram API
API_ID=ваш_api_id
API_HASH=ваш_api_hash
SESSION_NAME=collector

# Настройки базы данных
DB_HOST=localhost
DB_PORT=5432
DB_NAME=telegram_collector
DB_USER=postgres
DB_PASSWORD=postgres

# Каналы для мониторинга
TELEGRAM_CHANNELS=@channel1,@channel2,t.me/channel3

# Настройки сбора данных
MESSAGES_LIMIT=50
COLLECTION_INTERVAL=60

# Настройки логирования
LOG_LEVEL=INFO
```

### Поддерживаемые форматы указания каналов

В параметре `TELEGRAM_CHANNELS` можно указывать каналы в следующих форматах:

- Имя пользователя: `@channel_name`
- Публичная ссылка: `t.me/channel_name`
- ID канала: `-1001234567890`
- Приватная ссылка: `t.me/joinchat/XXXXX`

**Важно**: Для доступа к приватным каналам ваш аккаунт Telegram должен быть их
участником.

## Запуск

### Локальный запуск

```bash
python src/collector.py
```

### Запуск через Docker

```bash
docker-compose -f docker/docker-compose.yml up -d
```

## Структура базы данных

```sql
CREATE TABLE telegram_posts
(
    id           SERIAL PRIMARY KEY,
    channel_id   TEXT      NOT NULL,
    message_id   BIGINT    NOT NULL,
    published_at TIMESTAMP NOT NULL,
    text         TEXT,
    views        INTEGER,
    collected_at TIMESTAMP DEFAULT NOW()
);

-- Индексы
CREATE UNIQUE INDEX telegram_posts_channel_message_idx
    ON telegram_posts (channel_id, message_id);
CREATE INDEX telegram_posts_published_at_idx
    ON telegram_posts (published_at);
```

## Мониторинг

Скрипт использует библиотеку `loguru` для логирования. События записываются с
разными уровнями важности:

- INFO: Основные события (запуск, остановка, успешный сбор)
- WARNING: Предупреждения (превышение лимитов API)
- ERROR: Ошибки (недоступность каналов, проблемы с БД)
- DEBUG: Детальная ин��ормация о собранных сообщениях

### Просмотр логов

При локальном запуске логи выводятся в консоль.

В Docker:

```bash
docker-compose -f docker/docker-compose.yml logs -f collector
```

## Особенности реализации

- Использование пула соединений для оптимизации работы с базой данных
- Параллельный сбор сообщений из нескольких каналов
- Автоматическое создание базы данных и необходимых таблиц
- Валидация форматов каналов
- Типизация данных через Pydantic
- Безопасное хранение конфигурации в файле .env

## Ограничения

- Для доступа к приватным каналам требуется членство в них
- Telegram API имеет ограничения на количество запросов
- При первом запуске потребуется подтверждение через Telegram

## Устранение неполадок

### Ошибка "connection pool exhausted"

Увеличьте размер пула соединений в файле `database.py`:

```python
self.pool = SimpleConnectionPool(
    minconn=5,  # Увеличьте при необходимости
    maxconn=20,  # Увеличьте при необходимости
    conn_params
)
```

### Ошибка доступа к каналу

Проверьте следующее:

1. Формат канала указан корректно
2. Ваш аккаунт имеет доступ к каналу
3. Канал существует и активен