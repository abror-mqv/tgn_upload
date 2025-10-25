import httpx
import os
import mimetypes
from dotenv import load_dotenv

load_dotenv()
FASTAPI_URL = os.getenv("FASTAPI_URL")
DJANGO_URL = os.getenv("DJANGO_URL")
DJANGO_TOKEN = os.getenv("DJANGO_TOKEN")

async def get_prediction(description: str):
    async with httpx.AsyncClient() as client:
        r = await client.post(FASTAPI_URL, json={"text": description})
        if r.status_code == 200:
            data = r.json()
            print("🟢 Получено предсказание:", data.get("category_name"), data.get("confidence"))
            return data.get("category"), data.get("confidence", 0.0)
        return None, 0.0


async def send_to_backend(ad_data: dict):
    description = ad_data.get("description", "")
    raw_phone = ad_data.get("contact_phone", "")
    digits = "".join(ch for ch in str(raw_phone) if ch.isdigit())
    if digits.startswith("996"):
        contact_phone = digits
    elif digits.startswith("0") and len(digits) == 10:
        contact_phone = "996" + digits[1:]
    elif len(digits) == 9:
        contact_phone = "996" + digits
    else:
        contact_phone = digits
    category = ad_data.get("category")
    cities = ad_data.get("cities")
    images = ad_data.get("images", []) or []

    if isinstance(category, (int, float)):
        category = str(int(category))
    elif category is not None:
        category = str(category)

    if isinstance(cities, list):
        pass
    elif cities is None:
        cities = "1"
    else:
        cities = str(cities)

    payload = {
        "description": description,
        "contact_phone": contact_phone,
        "category": category if category is not None else "",
        "cities": cities,
    }

    headers = {"Authorization": f"Token {DJANGO_TOKEN}"}

    async with httpx.AsyncClient(timeout=60) as client:
        if images:
            files = []
            idx = 0
            for item in images:
                try:
                    if isinstance(item, str) and item.startswith("http"):
                        resp = await client.get(item)
                        resp.raise_for_status()
                        content = resp.content
                        name = os.path.basename(item.split("?")[0]) or f"image_{idx}.jpg"
                        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
                    elif isinstance(item, (bytes, bytearray)):
                        content = bytes(item)
                        name = f"image_{idx}.jpg"
                        mime = "application/octet-stream"
                    else:
                        continue
                    files.append(("images", (name, content, mime)))
                    print(f"🖼️ Prepared image file: name={name}, size={len(content)}, mime={mime}")
                    idx += 1
                except Exception as e:
                    print("⚠️ Failed to prepare image:", e)

            print("📤 Uploading multipart to", DJANGO_URL, ", fields=", payload, ", images_count=", len(files))
            r = await client.post(DJANGO_URL, data=payload, files=files if files else None, headers=headers)
        else:
            print("📤 Uploading JSON to", DJANGO_URL, ":", payload)
            r = await client.post(DJANGO_URL, json=payload, headers=headers)

    print("📥 Backend response:", r.status_code, r.text)
