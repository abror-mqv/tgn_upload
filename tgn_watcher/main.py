import asyncio
import os
from telethon import TelegramClient, events, errors
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
    try:
        ad = parse_message(message)
        if ad:
            print(f"🟢 Новое объявление: {ad}")

            images = []
            gid = getattr(message, "grouped_id", None)
            if gid:
                msgs = await client.get_messages(event.chat_id, limit=20)
                same = [m for m in msgs if getattr(m, "grouped_id", None) == gid]
                same.sort(key=lambda m: m.id)
                for m in same:
                    is_img = bool(getattr(m, "photo", None)) or (
                        getattr(m, "document", None) and getattr(m.document, "mime_type", "").startswith("image/")
                    )
                    if is_img:
                        b = await m.download_media(file=bytes)
                        if b:
                            images.append(b)
            else:
                is_img = bool(getattr(message, "photo", None)) or (
                    getattr(message, "document", None) and getattr(m.document, "mime_type", "").startswith("image/")
                )
                if is_img:
                    b = await message.download_media(file=bytes)
                    if b:
                        images.append(b)

            if images:
                ad["images"] = images

            category, confidence = await get_prediction(ad["description"])
            ad["category"] = category
            ad["confidence"] = confidence

            await send_to_backend(ad)
            print(f"✅ Отправлено объявление на бэкенд: {ad['category']} | {ad['confidence']:.2f}")

    except Exception as e:
        print(f"❌ Ошибка при обработке сообщения: {e}")


async def main():
    print("🚀 Watcher запущен. Подключаемся к Telegram...")
    try:
        await client.start()
        me = await client.get_me()
        print(f"🔹 Успешно подключились! Аккаунт: {me.first_name} ({me.username})")
        print(f"🔹 Слежение за группами: {groups}")
        await client.run_until_disconnected()
    except errors.RPCError as rpc_e:
        print(f"❌ RPCError при подключении к Telegram: {rpc_e}")
    except Exception as e:
        print(f"❌ Общая ошибка при подключении к Telegram: {e}")


if __name__ == "__main__":
    asyncio.run(main())
