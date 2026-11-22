import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()
from aiogram import Bot
from config import BOT_TOKEN, OWNER_ID, FSUB_CHANNEL

async def verify():
    if not BOT_TOKEN:
        print("[ERROR] BOT_TOKEN missing in .env")
        sys.exit(1)

    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()
    print(f"Checking bot @{me.username} (ID: {me.id}) access to channel '{FSUB_CHANNEL}'...")

    try:
        chat = await bot.get_chat(FSUB_CHANNEL)
        print(f"[OK] Channel resolved: {chat.title} (ID: {chat.id}, Type: {chat.type})")
    except Exception as e:
        print(f"[ERROR] Could not resolve channel {FSUB_CHANNEL}: {type(e).__name__} - {e}")
        await bot.session.close()
        sys.exit(1)

    try:
        bot_member = await bot.get_chat_member(FSUB_CHANNEL, me.id)
        print(f"[OK] Bot status in {FSUB_CHANNEL}: {bot_member.status}")
        if bot_member.status != "administrator":
            print(f"[WARNING] Bot is {bot_member.status}, not administrator. Telegram channel getChatMember requires administrator status.")
    except Exception as e:
        print(f"[BLOCKED] Bot cannot inspect members in {FSUB_CHANNEL}: {type(e).__name__} - {e}")
        print("-> Required Action: Add @KayiStreamBot as an administrator to @KayiBots.")
        await bot.session.close()
        return False

    try:
        owner_member = await bot.get_chat_member(FSUB_CHANNEL, OWNER_ID)
        print(f"[OK] Owner status in {FSUB_CHANNEL}: {owner_member.status}")
        print("\n[READY] Administrator access verified! Safe to deploy FSub.")
        await bot.session.close()
        return True
    except Exception as e:
        print(f"[BLOCKED] Failed checking owner status: {type(e).__name__} - {e}")
        await bot.session.close()
        return False

if __name__ == "__main__":
    success = asyncio.run(verify())
    sys.exit(0 if success else 1)
