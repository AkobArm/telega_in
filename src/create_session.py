import os

from telethon import TelegramClient

from config import settings

os.makedirs(os.path.dirname(settings.SESSION_NAME), exist_ok=True)

client = TelegramClient(
    settings.SESSION_NAME,
    settings.API_ID,
    settings.API_HASH
)


async def main():
    print("Создание сессии Telegram...")
    await client.start()
    print(f"Сессия успешно создана и сохранена в файл {settings.SESSION_NAME}.session")
    await client.disconnect()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
