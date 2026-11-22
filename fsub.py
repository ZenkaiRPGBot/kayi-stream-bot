import time
import asyncio
import logging
from typing import Callable, Any, Awaitable
from aiogram import BaseMiddleware, Bot, types
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, TelegramObject
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from config import FSUB_CHANNEL, FSUB_CHANNEL_URL, FSUB_CACHE_TTL, FSUB_TIMEOUT

logger = logging.getLogger("fsub")

# ==============================================================================
# UI COPY & KEYBOARD
# ==============================================================================

# Pending deep-link start parameter tracking across FSub prompts
_PENDING_PARAMS: dict[int, tuple[str, float]] = {}
PENDING_PARAM_TTL = 300.0  # 5 minutes

def set_pending_start_param(user_id: int, param: str) -> None:
    _PENDING_PARAMS[user_id] = (param, time.time() + PENDING_PARAM_TTL)

def get_and_clear_pending_start_param(user_id: int) -> str | None:
    val = _PENDING_PARAMS.pop(user_id, None)
    if not val:
        return None
    param, expiry = val
    if time.time() > expiry:
        return None
    return param

FSUB_PROMPT_TEXT = (
    "<b>Join Kayi Bots to Continue</b>\n\n"
    "To use Kayi File to Link, please join our official channel.\n\n"
    "Get announcements, new features, and important service updates.\n\n"
    "Once you've joined, tap <b>I've Joined</b> to verify your membership."
)

def build_fsub_keyboard(channel_url: str = FSUB_CHANNEL_URL) -> InlineKeyboardMarkup:
    """Builds native Telegram inline keyboard with Join URL and I've Joined callback."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📢 Join @KayiBots",
                url=channel_url
            )
        ],
        [
            InlineKeyboardButton(
                text="✅ I've Joined",
                callback_data="fsub:verify",
                style="success"
            )
        ]
    ])

# ==============================================================================
# IN-MEMORY TTL CACHE
# ==============================================================================

class FSubCache:
    """
    In-memory per-user membership cache with configurable time-to-live (TTL).
    Reduces latency and prevents excessive Telegram getChatMember calls.
    """
    def __init__(self, default_ttl: int = FSUB_CACHE_TTL):
        self.default_ttl = default_ttl
        self._store: dict[int, tuple[bool, float]] = {}

    def get(self, user_id: int) -> bool | None:
        entry = self._store.get(user_id)
        if entry is None:
            return None
        is_member, expires_at = entry
        if time.monotonic() < expires_at:
            return is_member
        self._store.pop(user_id, None)
        return None

    def set(self, user_id: int, is_member: bool, ttl: int | None = None) -> None:
        effective_ttl = ttl if ttl is not None else self.default_ttl
        self._store[user_id] = (is_member, time.monotonic() + effective_ttl)

    def invalidate(self, user_id: int) -> None:
        self._store.pop(user_id, None)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)

cache = FSubCache()

# ==============================================================================
# MEMBERSHIP CHECKER
# ==============================================================================

async def check_channel_membership(
    bot: Bot,
    user_id: int,
    channel: str = FSUB_CHANNEL,
    bypass_cache: bool = False
) -> tuple[bool, str]:
    """
    Queries Telegram getChatMember to determine whether a user belongs to the channel.

    Allowed statuses:
      - 'creator'
      - 'administrator'
      - 'member'
      - 'restricted' with is_member == True

    Disallowed statuses:
      - 'left'
      - 'kicked'
      - 'restricted' with is_member == False
    """
    if not bypass_cache:
        cached = cache.get(user_id)
        if cached is not None:
            return cached, "cached"

    try:
        member = await asyncio.wait_for(
            bot.get_chat_member(chat_id=channel, user_id=user_id),
            timeout=FSUB_TIMEOUT
        )
        status = member.status

        if status in ("creator", "administrator", "member"):
            is_member = True
        elif status == "restricted":
            is_member = getattr(member, "is_member", False)
        else:
            is_member = False

        cache.set(user_id, is_member)

        if is_member:
            logger.info("FSUB_ALLOW user_id=%s status=%s channel=%s", user_id, status, channel)
        else:
            logger.info("FSUB_DENY user_id=%s status=%s channel=%s", user_id, status, channel)

        return is_member, status

    except asyncio.TimeoutError:
        logger.warning("FSUB_TIMEOUT user_id=%s channel=%s timeout=%ss", user_id, channel, FSUB_TIMEOUT)
        return False, "timeout"
    except (TelegramBadRequest, TelegramForbiddenError) as tg_err:
        logger.warning("FSUB_TG_ERROR user_id=%s channel=%s error=%s: %s", user_id, channel, type(tg_err).__name__, tg_err)
        return False, f"error:{type(tg_err).__name__}"
    except Exception as exc:
        logger.error("FSUB_UNEXPECTED_ERROR user_id=%s channel=%s error=%s: %s", user_id, channel, type(exc).__name__, exc)
        return False, f"error:{type(exc).__name__}"

# ==============================================================================
# ENFORCEMENT MIDDLEWARE
# ==============================================================================

class FSubMiddleware(BaseMiddleware):
    """
    Aiogram 3 outer middleware that enforces mandatory channel membership
    across all user-facing commands, messages (including video/document uploads),
    and callback queries.
    """
    def __init__(self, channel: str = FSUB_CHANNEL):
        self.channel = channel

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:
        user: types.User | None = data.get("event_from_user")
        bot: Bot | None = data.get("bot")

        if not user or not bot:
            return await handler(event, data)

        # Narrow whitelist: 'fsub:verify' must reach verification handler
        if isinstance(event, types.CallbackQuery) and event.data == "fsub:verify":
            return await handler(event, data)

        # Check membership using short TTL cache
        is_member, _ = await check_channel_membership(
            bot=bot,
            user_id=user.id,
            channel=self.channel,
            bypass_cache=False
        )

        if is_member:
            return await handler(event, data)

        # Non-member enforcement
        if isinstance(event, types.Message):
            if event.chat and event.chat.type != "private":
                return None

            msg_text = getattr(event, "text", None)
            if msg_text:
                parts = str(msg_text).strip().split(maxsplit=1)
                if len(parts) > 1 and parts[0].lower().startswith("/start") and parts[1].strip().lower() == "help":
                    set_pending_start_param(user.id, "help")

            await event.answer(
                text=FSUB_PROMPT_TEXT,
                parse_mode=ParseMode.HTML,
                reply_markup=build_fsub_keyboard(),
                disable_web_page_preview=True
            )
            return None

        elif isinstance(event, types.CallbackQuery):
            try:
                await event.answer(
                    "Please join @KayiBots to use Kayi File to Link.",
                    show_alert=True
                )
            except Exception:
                pass

            if event.message:
                try:
                    await event.message.edit_text(
                        text=FSUB_PROMPT_TEXT,
                        parse_mode=ParseMode.HTML,
                        reply_markup=build_fsub_keyboard(),
                        disable_web_page_preview=True
                    )
                except Exception:
                    pass
            return None

        return None
