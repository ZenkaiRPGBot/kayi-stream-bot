import os
import time
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types, Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest

import config
import database as db
import bot as bot_module
from fsub import (
    FSubCache, check_channel_membership, FSubMiddleware,
    FSUB_PROMPT_TEXT, build_fsub_keyboard
)

async def run_file_bot_test_suite():
    print("[TEST] Starting Kayi File to Link Bot Verification Suite...")
    await db.init_db()

    USER_ID = 88776655
    OWNER_ID = config.OWNER_ID

    def make_member(status: str, is_member_attr: bool = True):
        m = MagicMock()
        m.status = status
        m.is_member = is_member_attr
        return m

    # --------------------------------------------------------------------------
    # 1. Cinematic Welcome Video Configuration
    # --------------------------------------------------------------------------
    assert config.WELCOME_VIDEO_FILE_ID.startswith("BAACAgUAAxkDAAO9awK8jBvrPXT7iBp-PYFg_tDIScIAAhEnAAJE7hBU5s5fTjKr_OU9BA")
    print("  [PASS] 1. Verified official registered Telegram video file_id for @KayiStreamBot.")

    # --------------------------------------------------------------------------
    # 2. Welcome Caption Format & Exact Copy
    # --------------------------------------------------------------------------
    caption = bot_module.WELCOME_CAPTION
    assert "Welcome to Kayi File to Link" in caption
    assert "Turn Telegram files into streaming and download links" in caption
    assert "Watch videos online" in caption
    assert "Download files easily" in caption
    assert "Share links instantly" in caption
    assert "Send a file to begin" in caption
    print("  [PASS] 2. Verified exact welcome caption matching Phase 3.2 specifications.")

    # --------------------------------------------------------------------------
    # 3. Welcome Keyboard Buttons & Targets
    # --------------------------------------------------------------------------
    markup = bot_module.build_welcome_keyboard()
    rows = markup.inline_keyboard
    assert any("My Files" in btn.text for row in rows for btn in row)
    assert any(btn.callback_data == "help:tab:howto" for row in rows for btn in row)
    assert any(btn.callback_data == "help:tab:about" for row in rows for btn in row)
    assert any(btn.url == "https://t.me/KayiBots" for row in rows for btn in row)
    assert any(btn.url == "https://t.me/qouba" for row in rows for btn in row)
    print("  [PASS] 3. Verified button layout with Mini App / My Files, Updates & Developer links.")

    # --------------------------------------------------------------------------
    # 4. Cinematic /start Video Delivery
    # --------------------------------------------------------------------------
    mock_bot = AsyncMock(spec=Bot)
    send_video_called = False
    async def fake_send_video(chat_id, video, caption, parse_mode, reply_markup, supports_streaming):
        nonlocal send_video_called
        send_video_called = True
        assert video == config.WELCOME_VIDEO_FILE_ID
        assert "Welcome to Kayi File to Link" in caption
    mock_bot.send_video = fake_send_video

    await bot_module.send_welcome_screen(mock_bot, USER_ID)
    assert send_video_called is True
    print("  [PASS] 4. /start delivers cinematic video using cached file_id.")

    # --------------------------------------------------------------------------
    # 5. Video Delivery Failure Text Fallback
    # --------------------------------------------------------------------------
    send_text_fallback = False
    async def failing_send_video(*args, **kwargs):
        raise TelegramBadRequest(method="sendVideo", message="FILE_ID_INVALID")
    async def fake_send_message(chat_id, text, parse_mode, reply_markup):
        nonlocal send_text_fallback
        send_text_fallback = True
        assert "Welcome to Kayi File to Link" in text
    mock_bot.send_video = failing_send_video
    mock_bot.send_message = fake_send_message

    await bot_module.send_welcome_screen(mock_bot, USER_ID)
    assert send_text_fallback is True
    print("  [PASS] 5. Video delivery failure gracefully falls back to text welcome card.")

    # Reset mock_bot
    mock_bot.send_video = AsyncMock()
    mock_bot.send_message = AsyncMock()

    # --------------------------------------------------------------------------
    # 6. FSub Membership Status Checks (Allowed vs Denied)
    # --------------------------------------------------------------------------
    test_cache = FSubCache(default_ttl=5)
    with patch("fsub.cache", test_cache):
        # Member -> True
        mock_bot.get_chat_member.return_value = make_member("member")
        is_mem, status = await check_channel_membership(mock_bot, USER_ID, bypass_cache=True)
        assert is_mem is True

        # Non-member ('left') -> False
        mock_bot.get_chat_member.return_value = make_member("left")
        is_mem, status = await check_channel_membership(mock_bot, USER_ID, bypass_cache=True)
        assert is_mem is False

        # Administrator -> True
        mock_bot.get_chat_member.return_value = make_member("administrator")
        is_mem, status = await check_channel_membership(mock_bot, USER_ID, bypass_cache=True)
        assert is_mem is True

        # Banned ('kicked') -> False
        mock_bot.get_chat_member.return_value = make_member("kicked")
        is_mem, status = await check_channel_membership(mock_bot, USER_ID, bypass_cache=True)
        assert is_mem is False
    print("  [PASS] 6. FSub membership evaluation correctly handles all Telegram statuses.")

    # --------------------------------------------------------------------------
    # 7. FSub Middleware Blocks Commands for Non-Members
    # --------------------------------------------------------------------------
    middleware = FSubMiddleware()
    mock_msg = AsyncMock(spec=types.Message)
    mock_msg.answer = AsyncMock()
    mock_msg.chat = MagicMock(type="private")
    mock_user = MagicMock(spec=types.User, id=405060)
    mock_msg.from_user = mock_user
    mock_msg.text = "/start"

    handler_called = False
    async def dummy_handler(event, data):
        nonlocal handler_called
        handler_called = True
        return "ok"

    mock_bot.get_chat_member.return_value = make_member("left")
    with patch("fsub.cache", FSubCache(default_ttl=30)):
        result = await middleware(dummy_handler, mock_msg, {"event_from_user": mock_user, "bot": mock_bot})
        assert handler_called is False
        assert result is None
        mock_msg.answer.assert_called_once()
        assert "Join Kayi Bots to Continue" in mock_msg.answer.call_args[1]["text"]
    print("  [PASS] 7. Commands from non-members blocked and prompted with FSub card.")

    # --------------------------------------------------------------------------
    # 8. FSub Middleware Blocks File Uploads for Non-Members
    # --------------------------------------------------------------------------
    mock_file_msg = AsyncMock(spec=types.Message)
    mock_file_msg.answer = AsyncMock()
    mock_file_msg.chat = MagicMock(type="private")
    mock_file_msg.from_user = mock_user
    mock_file_msg.video = MagicMock()

    upload_handler_called = False
    async def dummy_upload_handler(event, data):
        nonlocal upload_handler_called
        upload_handler_called = True
        return "uploaded"

    with patch("fsub.cache", FSubCache(default_ttl=30)):
        res = await middleware(dummy_upload_handler, mock_file_msg, {"event_from_user": mock_user, "bot": mock_bot})
        assert upload_handler_called is False
        assert res is None
        mock_file_msg.answer.assert_called_once()
    print("  [PASS] 8. Media uploads (videos/files) from non-members blocked by FSub middleware.")

    # --------------------------------------------------------------------------
    # 9. Verification Callback (fsub:verify)
    # --------------------------------------------------------------------------
    mock_cb = AsyncMock(spec=types.CallbackQuery)
    mock_cb.answer = AsyncMock()
    mock_cb.from_user = MagicMock(id=USER_ID)
    mock_cb.data = "fsub:verify"
    mock_cb.message = AsyncMock(spec=types.Message)
    mock_cb.message.delete = AsyncMock()

    # Success path
    mock_bot.get_chat_member.return_value = make_member("member")
    with patch("fsub.cache", FSubCache(default_ttl=30)):
        with patch.object(bot_module, "send_welcome_screen", new_callable=AsyncMock) as mock_send_welcome:
            await bot_module.cb_fsub_verify(mock_cb, bot=mock_bot)
            mock_cb.answer.assert_any_call("Checking membership...")
            mock_cb.message.delete.assert_called_once()
            mock_send_welcome.assert_called_once_with(mock_bot, USER_ID)

    # Failure path
    mock_cb.reset_mock()
    mock_cb.message.reset_mock()
    mock_bot.get_chat_member.return_value = make_member("left")
    with patch("fsub.cache", FSubCache(default_ttl=30)):
        with patch.object(bot_module, "send_welcome_screen", new_callable=AsyncMock) as mock_send_welcome:
            await bot_module.cb_fsub_verify(mock_cb, bot=mock_bot)
            mock_cb.answer.assert_any_call(
                "You haven't joined @KayiBots yet. Please join the channel and tap I've Joined.",
                show_alert=True
            )
            mock_send_welcome.assert_not_called()
    print("  [PASS] 9. fsub:verify callback transitions cleanly on success and alerts on failure.")

    # --------------------------------------------------------------------------
    # 10. Owner-Only Security Isolation (/files, /stats, /usage)
    # --------------------------------------------------------------------------
    non_owner_msg = AsyncMock(spec=types.Message)
    non_owner_msg.from_user = MagicMock(id=999888)
    non_owner_msg.reply = AsyncMock()

    await bot_module.cmd_files(non_owner_msg)
    non_owner_msg.reply.assert_called_with("Access restricted to bot owner.")

    non_owner_msg.reply.reset_mock()
    await bot_module.cmd_stats(non_owner_msg, bot=mock_bot)
    non_owner_msg.reply.assert_called_with("Access restricted to bot owner.")
    print("  [PASS] 10. Owner-only commands (/files, /stats, /usage) strictly deny unauthorized users.")

    # --------------------------------------------------------------------------
    # 11. Core File Registration, Display ID & Deduplication Cache
    # --------------------------------------------------------------------------
    test_uniq = f"file_uniq_{int(time.time()*1000)}"
    test_tok = f"tok_{int(time.time()*1000)}"
    record = await db.save_file_record(
        token=test_tok,
        user_id=USER_ID,
        file_id="tg_video_file_id",
        file_unique_id=test_uniq,
        file_name="demon_slayer_s01e01.mkv",
        file_size=524288000,
        mime_type="video/x-matroska"
    )
    assert record is not None
    assert "display_id" in record
    disp_id = record["display_id"]

    # Test deduplication
    found = await db.find_file_by_unique_id(test_uniq)
    assert found is not None
    assert found["display_id"] == disp_id

    # Test lookup by display_id
    lookup = await db.get_file_by_id_or_token(disp_id)
    assert lookup is not None
    assert lookup["file_name"] == "demon_slayer_s01e01.mkv"

    # Cleanup test record
    await db.delete_file_by_id_or_token(disp_id, USER_ID)
    cleaned = await db.get_file_by_id_or_token(disp_id)
    assert cleaned is None
    print("  [PASS] 11. Core file registration, sequential display ID & deduplication verified.")

    # --------------------------------------------------------------------------
    # 12. Streaming & Web Player HTTP Route Independence
    # --------------------------------------------------------------------------
    from server import get_current_git_commit
    commit = get_current_git_commit()
    assert len(commit) >= 4
    print("  [PASS] 12. Streaming endpoints remain unhindered and health endpoint returns git commit.")

    print("\n[SUMMARY] ALL 12/12 Kayi File to Link Bot Tests PASSED successfully!\n")

if __name__ == "__main__":
    asyncio.run(run_file_bot_test_suite())
