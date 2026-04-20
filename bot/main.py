from __future__ import annotations

from collections import defaultdict
from typing import Any

from bot.data import deals_within_budget, format_deal_message, ranked_deals, search_deals
from config import get_settings
from models.persona import PersonaType

USER_MODES: defaultdict[int, PersonaType] = defaultdict(lambda: PersonaType.WORKER)


async def start(update: Any, context: Any) -> None:
    message = _message(update)
    if message is None:
        return
    await message.reply_text(
        "Welcome to BudgetWings.\n"
        "I read local deal data and help you browse cheap trips.\n\n"
        "Commands:\n"
        "/mode worker or /mode student\n"
        "/deals\n"
        "/deals 清迈\n"
        "/budget 2000"
    )


async def mode(update: Any, context: Any) -> None:
    message = _message(update)
    if message is None:
        return
    args = _args(context)
    if not args or args[0] not in {PersonaType.WORKER.value, PersonaType.STUDENT.value}:
        await message.reply_text("Usage: /mode worker or /mode student")
        return
    chat_id = _chat_id(update)
    if chat_id is not None:
        USER_MODES[chat_id] = PersonaType(args[0])
    await message.reply_text(f"Mode switched to {args[0]}")


async def deals(update: Any, context: Any) -> None:
    message = _message(update)
    if message is None:
        return
    persona = _persona(update)
    args = _args(context)
    selected = search_deals(" ".join(args), persona) if args else ranked_deals(persona)
    if not selected:
        await message.reply_text(
            "No local deals found. Run the agent pipeline or add sample data first."
        )
        return
    for deal in selected[:10]:
        await message.reply_text(format_deal_message(deal), disable_web_page_preview=True)


async def budget(update: Any, context: Any) -> None:
    message = _message(update)
    if message is None:
        return
    args = _args(context)
    if not args or not args[0].isdigit():
        await message.reply_text("Usage: /budget 2000")
        return
    selected = deals_within_budget(int(args[0]), _persona(update))
    if not selected:
        await message.reply_text("No local deals fit this budget yet.")
        return
    for deal in selected[:10]:
        await message.reply_text(format_deal_message(deal), disable_web_page_preview=True)


def run_bot() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        msg = "TELEGRAM_BOT_TOKEN is required"
        raise RuntimeError(msg)

    from telegram.ext import Application, CommandHandler

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mode", mode))
    app.add_handler(CommandHandler("deals", deals))
    app.add_handler(CommandHandler("budget", budget))
    app.run_polling()


def _message(update: Any) -> Any | None:
    return getattr(update, "effective_message", None)


def _chat_id(update: Any) -> int | None:
    chat = getattr(update, "effective_chat", None)
    chat_id = getattr(chat, "id", None)
    return int(chat_id) if chat_id is not None else None


def _persona(update: Any) -> PersonaType:
    chat_id = _chat_id(update)
    return USER_MODES[chat_id] if chat_id is not None else PersonaType.WORKER


def _args(context: Any) -> list[str]:
    args = getattr(context, "args", [])
    return [str(arg) for arg in args]


if __name__ == "__main__":
    run_bot()
