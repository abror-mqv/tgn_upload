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

client = TelegramClient(session_name, api_id, api_hash)

@client.on(events.NewMessage(chats=groups))
async def handler(event):
    message = event.message
    ad = parse_message(message)

    if ad:
        print("🟢 Найдено объявление:", ad)
        images = []
        gid = getattr(message, "grouped_id", None)
        if gid:
            msgs = await client.get_messages(event.chat_id, limit=20)
            same = [m for m in msgs if getattr(m, "grouped_id", None) == gid]
            same.sort(key=lambda m: m.id)
            for m in same:
                is_img = bool(getattr(m, "photo", None)) or (getattr(m, "document", None) and getattr(m.document, "mime_type", "").startswith("image/"))
                if is_img:
                    b = await m.download_media(file=bytes)
                    if b:
                        images.append(b)
        else:
            is_img = bool(getattr(message, "photo", None)) or (getattr(message, "document", None) and getattr(message.document, "mime_type", "").startswith("image/"))
            if is_img:
                b = await message.download_media(file=bytes)
                if b:
                    images.append(b)
        if images:
            ad["images"] = images
        # Получаем предсказание категории
        category, confidence = await get_prediction(ad["description"])
        ad["category"] = category
        ad["confidence"] = confidence
        await send_to_backend(ad)

async def main():
    print("🚀 Watcher запущен. Мониторим группы...")
    await client.start()
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
