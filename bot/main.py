from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any, cast

from bot.data import deals_within_budget, format_deal_message, ranked_deals, search_deals
from config import get_settings
from models.deal import Deal
from models.persona import PersonaType

logger = logging.getLogger(__name__)
USER_MODES: defaultdict[int, PersonaType] = defaultdict(lambda: PersonaType.WORKER)
Handler = Callable[[Any, Any], Coroutine[Any, Any, None]]


def with_error_handling(handler: Handler) -> Handler:
    async def wrapped(update: Any, context: Any) -> None:
        try:
            await handler(update, context)
        except Exception:
            logger.exception("Telegram command failed")
            message = _message(update)
            if message is not None:
                await message.reply_text(
                    "出错了，我没有调用 LLM，只读取本地 data/ 数据。请稍后再试。"
                )

    return wrapped


@with_error_handling
async def start(update: Any, context: Any) -> None:
    message = _message(update)
    if message is None:
        return
    await message.reply_text(
        "欢迎使用 BudgetWings。\n"
        "我会读取本地 data/deals 里的低价出行数据，帮你按打工人或学生党模式筛选目的地。\n\n"
        "命令：\n"
        "/mode worker 切换打工人模式\n"
        "/mode student 切换学生党模式\n"
        "/deals 查看最新 TOP 10\n"
        "/deals 清迈 搜索目的地\n"
        "/budget 2000 查看预算内推荐"
    )


@with_error_handling
async def mode(update: Any, context: Any) -> None:
    message = _message(update)
    if message is None:
        return
    args = _args(context)
    if not args or args[0] not in {PersonaType.WORKER.value, PersonaType.STUDENT.value}:
        await message.reply_text("用法：/mode worker 或 /mode student")
        return
    user_id = _user_id(update)
    if user_id is not None:
        USER_MODES[user_id] = PersonaType(args[0])
    await message.reply_text(f"已切换到 {args[0]} 模式。")


@with_error_handling
async def deals(update: Any, context: Any) -> None:
    message = _message(update)
    if message is None:
        return
    persona = _persona(update)
    args = _args(context)
    selected = search_deals(" ".join(args), persona) if args else ranked_deals(persona)
    await _reply_deals(message, selected[:10], "没有找到本地 deal。请先运行采集或检查 data/deals。")


@with_error_handling
async def budget(update: Any, context: Any) -> None:
    message = _message(update)
    if message is None:
        return
    args = _args(context)
    if not args:
        await message.reply_text("用法：/budget 2000")
        return
    try:
        total_budget = int(args[0])
    except ValueError:
        await message.reply_text("预算请输入整数，例如：/budget 2000")
        return
    selected = deals_within_budget(total_budget, _persona(update))
    await _reply_deals(message, selected[:10], "当前本地数据里没有符合预算的推荐。")


def run_bot() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    if not settings.telegram_bot_token:
        msg = "TELEGRAM_BOT_TOKEN is required"
        raise RuntimeError(msg)

    from telegram.ext import Application, CommandHandler

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", cast(Any, start)))
    app.add_handler(CommandHandler("mode", cast(Any, mode)))
    app.add_handler(CommandHandler("deals", cast(Any, deals)))
    app.add_handler(CommandHandler("budget", cast(Any, budget)))
    app.run_polling()


async def _reply_deals(message: Any, selected: list[Deal], empty_text: str) -> None:
    if not selected:
        await message.reply_text(empty_text)
        return
    for deal in selected:
        await message.reply_text(format_deal_message(deal), disable_web_page_preview=True)


def _message(update: Any) -> Any | None:
    return getattr(update, "effective_message", None)


def _user_id(update: Any) -> int | None:
    user = getattr(update, "effective_user", None)
    user_id = getattr(user, "id", None)
    return int(user_id) if user_id is not None else None


def _persona(update: Any) -> PersonaType:
    user_id = _user_id(update)
    return USER_MODES[user_id] if user_id is not None else PersonaType.WORKER


def _args(context: Any) -> list[str]:
    args = getattr(context, "args", [])
    return [str(arg) for arg in args]


if __name__ == "__main__":
    run_bot()
