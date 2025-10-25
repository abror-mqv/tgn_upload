import re
from typing import Union

def extract_phone_number(text: str) -> Union[str, None]:
    if not text:
        return None
    cleaned = re.sub(r"[^\d\+\s]", " ", text)
    candidates = re.findall(r"(?:\+?\d[\d\s\-]{6,15}\d)", cleaned)
    for c in candidates:
        phone = re.sub(r"\D", "", c)
        if phone.startswith("0") and len(phone) == 10:
            phone = "+996" + phone[1:]
        elif phone.startswith("996") and len(phone) == 12:
            phone = "+" + phone
        elif not phone.startswith("+"):
            phone = "+" + phone
        if 12 <= len(phone) <= 13:
            return phone
    return None


def parse_message(message):
    text = (message.text or "").strip()
    if not text:
        return None

    phone = extract_phone_number(text)
    if not phone:
        return None  # игнорируем посты без телефонов

    ad = {
        "description": text,
        "contact_phone": phone,
        "cities": 1  # можно потом определять автоматически
    }
    return ad
