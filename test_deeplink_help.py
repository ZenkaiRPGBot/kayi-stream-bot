"""Comprehensive test suite for /start help deep-link in Kayi File to Link Bot."""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import types
from aiogram.filters import CommandObject

# Add repo to sys.path
sys.path.insert(0, os.path.dirname(__file__))

import bot
import fsub


@pytest.mark.asyncio
async def test_cmd_start_with_command_args_help():
    """Verify /start help with CommandObject(args='help') routes to cmd_help."""
    message = AsyncMock(spec=types.Message)
    message.from_user = MagicMock(id=12345)
    message.text = "/start help"
    message.bot = AsyncMock()
    command = CommandObject(prefix="/", command="start", args="help")

    with patch("bot.send_welcome_screen", new=AsyncMock()) as mock_welcome, \
         patch("bot.cmd_help", new=AsyncMock()) as mock_help:
        await bot.cmd_start(message, bot=message.bot, command=command)
        mock_help.assert_awaited_once_with(message)
        mock_welcome.assert_not_called()


@pytest.mark.asyncio
async def test_cmd_start_with_text_fallback_help():
    """Verify /start help with command=None routes to cmd_help via message.text."""
    message = AsyncMock(spec=types.Message)
    message.from_user = MagicMock(id=12345)
    message.text = "/start help"
    message.bot = AsyncMock()

    with patch("bot.send_welcome_screen", new=AsyncMock()) as mock_welcome, \
         patch("bot.cmd_help", new=AsyncMock()) as mock_help:
        await bot.cmd_start(message, bot=message.bot, command=None)
        mock_help.assert_awaited_once_with(message)
        mock_welcome.assert_not_called()


@pytest.mark.asyncio
async def test_cmd_start_normal_cinematic():
    """Verify normal /start delivers the welcome screen."""
    message = AsyncMock(spec=types.Message)
    message.from_user = MagicMock(id=12345)
    message.text = "/start"
    message.bot = AsyncMock()
    command = CommandObject(prefix="/", command="start", args=None)

    with patch("bot.send_welcome_screen", new=AsyncMock()) as mock_welcome, \
         patch("bot.cmd_help", new=AsyncMock()) as mock_help:
        await bot.cmd_start(message, bot=message.bot, command=command)
        mock_welcome.assert_awaited_once_with(message.bot, 12345)
        mock_help.assert_not_called()


@pytest.mark.asyncio
async def test_fsub_middleware_stores_pending_help_param():
    """Verify non-member sending /start help triggers pending param storage."""
    middleware = fsub.FSubMiddleware()
    event = AsyncMock(spec=types.Message)
    event.from_user = MagicMock(id=777888)
    event.chat = MagicMock(type="private")
    event.text = "/start help"
    event.bot = AsyncMock()
    event.answer = AsyncMock()
    handler = AsyncMock()

    with patch("fsub.check_channel_membership", new=AsyncMock(return_value=(False, "left"))):
        await middleware(handler, event, {"event_from_user": event.from_user, "bot": event.bot})
        handler.assert_not_called()
        event.answer.assert_awaited_once()
        # Verify pending param was set
        assert fsub.get_and_clear_pending_start_param(777888) == "help"


@pytest.mark.asyncio
async def test_cb_fsub_verify_routes_to_help_when_pending():
    """Verify clicking verify after /start help routes directly to Help Center."""
    fsub.set_pending_start_param(999000, "help")

    cb = AsyncMock(spec=types.CallbackQuery)
    cb.from_user = MagicMock(id=999000)
    cb.message = AsyncMock(spec=types.Message)
    cb.message.delete = AsyncMock()
    cb.message.answer = AsyncMock()
    cb.answer = AsyncMock()
    cb.bot = AsyncMock()

    with patch("bot.check_channel_membership", new=AsyncMock(return_value=(True, "member"))), \
         patch("bot.send_welcome_screen", new=AsyncMock()) as mock_welcome:
        await bot.cb_fsub_verify(cb, bot=cb.bot)
        cb.message.delete.assert_awaited_once()
        cb.message.answer.assert_awaited_once()
        sent_text = cb.message.answer.call_args[0][0]
        assert bot.HELP_MAIN_TEXT == sent_text
        mock_welcome.assert_not_called()


@pytest.mark.asyncio
async def test_cb_fsub_verify_routes_to_welcome_when_no_pending():
    """Verify clicking verify without pending param opens welcome screen."""
    cb = AsyncMock(spec=types.CallbackQuery)
    cb.from_user = MagicMock(id=111222)
    cb.message = AsyncMock(spec=types.Message)
    cb.message.delete = AsyncMock()
    cb.answer = AsyncMock()
    cb.bot = AsyncMock()

    with patch("bot.check_channel_membership", new=AsyncMock(return_value=(True, "member"))), \
         patch("bot.send_welcome_screen", new=AsyncMock()) as mock_welcome:
        await bot.cb_fsub_verify(cb, bot=cb.bot)
        cb.message.delete.assert_awaited_once()
        mock_welcome.assert_awaited_once_with(cb.bot, 111222)


if __name__ == "__main__":
    asyncio.run(test_cmd_start_with_command_args_help())
    asyncio.run(test_cmd_start_with_text_fallback_help())
    asyncio.run(test_cmd_start_normal_cinematic())
    asyncio.run(test_fsub_middleware_stores_pending_help_param())
    asyncio.run(test_cb_fsub_verify_routes_to_help_when_pending())
    asyncio.run(test_cb_fsub_verify_routes_to_welcome_when_no_pending())
    print("ALL 6 /start help deep-link tests PASSED successfully for Kayi File to Link Bot!")
