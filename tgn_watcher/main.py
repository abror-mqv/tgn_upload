import asyncio
import os
from telethon import TelegramClient, events
from dotenv import load_dotenv
from parser import parse_message
from sender import send_to_backend, get_prediction

load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
session_name = os.getenv("SESSION_NAME")
groups = [x.strip() for x in os.getenv("GROUPS").split(",")]

print(f"🔹 API_ID: {api_id}, SESSION_NAME: {session_name}")
print(f"🔹 Мониторим группы: {groups}")

client = TelegramClient(session_name, api_id, api_hash)


@client.on(events.NewMessage(chats=groups))
async def handler(event):
    message = event.message
    print(f"\n📩 Новое сообщение в {event.chat_id} от {message.sender_id}")
    
    ad = parse_message(message)
    if not ad:
        print("⚪ Сообщение не является объявлением, пропускаем")
        return

    print("🟢 Найдено объявление:", ad)
    images = []
    gid = getattr(message, "grouped_id", None)
    if gid:
        print(f"🖼 Сообщение входит в группу медиаконтента {gid}")
        msgs = await client.get_messages(event.chat_id, limit=20)
        same = [m for m in msgs if getattr(m, "grouped_id", None) == gid]
        same.sort(key=lambda m: m.id)
        for m in same:
            is_img = bool(getattr(m, "photo", None)) or (
                getattr(m, "document", None) and getattr(m.document, "mime_type", "").startswith("image/")
            )
            if is_img:
                print(f"🔹 Загружаем изображение из сообщения {m.id}...")
                b = await m.download_media(file=bytes)
                if b:
                    images.append(b)
    else:
        is_img = bool(getattr(message, "photo", None)) or (
            getattr(message, "document", None) and getattr(message.document, "mime_type", "").startswith("image/")
        )
        if is_img:
            print("🔹 Загружаем изображение из одиночного сообщения...")
            b = await message.download_media(file=bytes)
            if b:
                images.append(b)
    
    if images:
        print(f"🖼 Загружено {len(images)} изображений")
        ad["images"] = images
    else:
        print("⚪ Изображений нет")

    # Получаем предсказание категории
    print("🔹 Запрос предсказания категории...")
    try:
        category, confidence = await get_prediction(ad["description"])
        ad["category"] = category
        ad["confidence"] = confidence
        print(f"🧠 Предсказание: {category} ({confidence:.2f})")
    except Exception as e:
        print("❌ Ошибка при получении предсказания:", e)
        ad["category"] = None
        ad["confidence"] = None

    # Отправляем на бэкенд
    try:
        await send_to_backend(ad)
        print("✅ Отправлено на бэкенд")
    except Exception as e:
        print("❌ Ошибка при отправке на бэкенд:", e)


async def main():
    print("🚀 Watcher запущен. Подключаемся к Telegram...")
    await client.start()
    print("✅ Успешно подключено к Telegram")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
