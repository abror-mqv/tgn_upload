from telethon.tl.functions.channels import GetFullChannelRequest
from dotenv import load_dotenv
import os
from telethon import TelegramClient
load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
session_name = os.getenv("SESSION_NAME")
groups = [x.strip() for x in os.getenv("GROUPS").split(",")]
client = TelegramClient(session_name, api_id, api_hash)
async def get_chat_id(link):
    channel = await client(GetFullChannelRequest(link))
    return channel.full_chat.id

async def main():
    await client.start()
    group_ids = []
    for link in groups:
        chat_id = await get_chat_id(link)
        print(f"🔹 {link} -> {chat_id}")
        group_ids.append(chat_id)
    print(group_ids)

