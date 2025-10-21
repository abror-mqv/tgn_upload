API_URL = "http://176.126.164.86:8000/ads/create/"  # твой backend endpoint
API_TOKEN = "8175494936:AAFcEje1JiBgrs7--KumK1IhnqtT0HP4gI8"
DJANGO_TOKEN = "c4ebc8326980a71f9d642ef1c14a050317b2eca0"

import re
import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import asyncio
import logging
import os
import mimetypes
import time


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Категории
CATEGORIES = [
    {"id": 7, "ru_name": "Попутка"},
    {"id": 8, "ru_name": "Недвижимость"},
    {"id": 9, "ru_name": "Авто"},
    {"id": 10, "ru_name": "Скот"},
    {"id": 11, "ru_name": "Купить/Продать"},
    {"id": 12, "ru_name": "Работа"},
    {"id": 13, "ru_name": "Новости района"},
]

class AdState(StatesGroup):
    waiting_for_category = State()

def extract_phone(text: str) -> str | None:
    patterns = [
        r"(?:\+?996)(?:[\s\-]*\d){9}",
        r"0(?:[\s\-]*\d){9}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            phone = re.sub(r"\D", "", match.group(0))
            if phone.startswith("996"):
                return phone
            if phone.startswith("0") and len(phone) == 10:
                return "996" + phone[1:]
            if len(phone) == 9:
                return "996" + phone
    return None

async def extract_image_urls(message: Message) -> list[str]:
    image_urls: list[str] = []
    if message.photo:
        largest = message.photo[-1]
        file = await bot.get_file(largest.file_id)
        image_urls.append(f"https://api.telegram.org/file/bot{API_TOKEN}/{file.file_path}")
    doc = getattr(message, "document", None)
    if doc and getattr(doc, "mime_type", "").startswith("image/"):
        file = await bot.get_file(doc.file_id)
        image_urls.append(f"https://api.telegram.org/file/bot{API_TOKEN}/{file.file_path}")
    return image_urls

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("Привет! Перешли мне объявление — я попробую его опубликовать 😊")

async def process_incoming(message: Message, state: FSMContext):
    text = message.text or message.caption
    phone = extract_phone(text or "")
    images = await extract_image_urls(message)

    now = time.time()
    data = await state.get_data()
    last_activity = data.get("last_activity_at") if data else None
    SESSION_WINDOW_SECONDS = 30
    media_group_id = getattr(message, "media_group_id", None)

    can_merge = bool(data) and last_activity is not None and (now - float(last_activity) <= SESSION_WINDOW_SECONDS)
    if media_group_id:
        can_merge = True

    if not can_merge:
        merged_images = images
        merged_text = text
        merged_phone = phone
    else:
        prev_images = data.get("images", [])
        seen = set()
        merged_images = []
        for u in prev_images + images:
            if u and u not in seen:
                seen.add(u)
                merged_images.append(u)
        merged_text = data.get("text") or text
        merged_phone = data.get("phone") or phone

    logging.info("Incoming message: phone_found=%s, has_text=%s, new_images=%s, merged_images_count=%d", bool(phone), bool(text), images, len(merged_images))
    if media_group_id:
        mg_until = now + 2.0
        await state.update_data(media_group_active_until=mg_until)
        logging.info("Media group detected id=%s; delaying category prompt until %.2f", media_group_id, mg_until)

    if not merged_phone:
        if merged_images:
            await state.update_data(text=merged_text, phone=merged_phone, images=merged_images, last_activity_at=now)
            await message.answer("🖼️ Принял фото. Теперь отправь текст объявления с номером телефона.")
            return
        else:
            await message.answer("⚠️ Не удалось найти номер телефона. Отправь текст объявления с номером телефона.")
            return

    await state.update_data(text=merged_text, phone=merged_phone, images=merged_images, last_activity_at=now)

    st = await state.get_data()
    mg_until = st.get("media_group_active_until")
    if mg_until is not None and now < float(mg_until):
        await asyncio.sleep(float(mg_until) - now)
        st2 = await state.get_data()
        merged_images = st2.get("images", merged_images)
        await state.update_data(media_group_active_until=None)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=cat["ru_name"], callback_data=f"cat_{cat['id']}")]
            for cat in CATEGORIES
        ]
    )
    await message.answer(f"📱 Найден номер: +{merged_phone}\n\nВыбери категорию:", reply_markup=kb)
    await state.set_state(AdState.waiting_for_category)

@dp.message(F.text | F.caption)
async def handle_text_or_caption(message: Message, state: FSMContext):
    await process_incoming(message, state)

@dp.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    await process_incoming(message, state)

@dp.message(F.document)
async def handle_document(message: Message, state: FSMContext):
    doc = getattr(message, "document", None)
    if not doc or not getattr(doc, "mime_type", "").startswith("image/"):
        return
    await process_incoming(message, state)

@dp.callback_query(F.data.startswith("cat_"))
async def handle_category(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[1])
    data = await state.get_data()
    now = time.time()
    mg_until = data.get("media_group_active_until")
    if mg_until is not None and now < float(mg_until):
        await asyncio.sleep(float(mg_until) - now)
        data = await state.get_data()

    text = data.get("text")
    phone = data.get("phone")
    images = data.get("images", [])
    if images:
        seen = set()
        dedup = []
        for u in images:
            if u and u not in seen:
                seen.add(u)
                dedup.append(u)
        def _file_index(u: str) -> int:
            try:
                base = u.rsplit("/", 1)[-1]
                if base.startswith("file_"):
                    num = base.split("_", 1)[1].split(".")[0]
                    return int(num)
            except Exception:
                pass
            return 10_000_000
        images = sorted(list(dedup))
        images = sorted(images, key=_file_index)[:10]

    if not text or not phone:
        await callback.answer("❌ Ошибка: данные не найдены.")
        return

    payload = {
        "description": text,
        "contact_phone": phone,
        "category": str(cat_id),
        "cities": "1",
    }

    async with httpx.AsyncClient() as client:
        if images:
            files = []
            for url in images:
                name = os.path.basename(url.split("?")[0]) or "image"
                mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    content = resp.content
                    files.append(("images", (name, content, mime)))
                    logging.info("Prepared image file: name=%s, size=%d, mime=%s", name, len(content), mime)
                except Exception as e:
                    logging.warning("Failed to download image %s: %s", url, e)

            logging.info("Uploading multipart to %s: fields=%s, images_count=%d", API_URL, payload, len(files))
            response = await client.post(
                API_URL,
                data=payload,
                files=files if files else None,
                headers={"Authorization": f"Token {DJANGO_TOKEN}"},
                timeout=60,
            )
        else:
            logging.info("Uploading JSON to %s: %s", API_URL, payload)
            response = await client.post(
                API_URL,
                json=payload,
                headers={"Authorization": f"Token {DJANGO_TOKEN}"},
                timeout=60,
            )

    logging.info("API response: status=%s, body=%s", response.status_code, response.text)

    if response.status_code in (200, 201):
        await callback.message.answer("✅ Объявление опубликовано успешно!")
    else:
        await callback.message.answer(f"❌ Ошибка при публикации ({response.status_code})")

    await state.clear()
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
