#!/usr/bin/env python3
"""инлайн-обработчик запросов для отправки карточек расписания в любые чаты."""
from __future__ import annotations

import hashlib
from datetime import timedelta
from aiogram import Router
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from bot.storage import get_user_settings
from bot.parser import (
    get_groups,
    fetch_schedule,
    format_day_schedule,
    format_week_schedule,
    get_current_moscow_date,
)

router = Router()


def make_id(seed: str) -> str:
    return hashlib.md5(seed.encode("utf-8")).hexdigest()


@router.inline_query()
async def inline_query_handler(query: InlineQuery) -> None:
    q = query.query.strip().lower()
    user_id = query.from_user.id
    user_data = await get_user_settings(user_id)
    profiles = user_data.get("profiles", [])

    today = get_current_moscow_date()
    today_num = today.weekday() + 1
    tomorrow = today + timedelta(days=1)
    tomorrow_num = tomorrow.weekday() + 1

    bot_info = await query.bot.get_me()
    bot_username = bot_info.username or "fz_arcotel_bot"

    open_btn = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть расписание в боте", url=f"https://t.me/{bot_username}?start=schedule")]
        ]
    )

    results: list[InlineQueryResultArticle] = []

    # Если у пользователя еще нет сохраненных профилей
    if not profiles:
        setup_btn = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Настроить свой профиль", url=f"https://t.me/{bot_username}?start=setup")]
            ]
        )
        results.append(
            InlineQueryResultArticle(
                id=make_id("onboarding_inline"),
                title="Настройте профиль в боте",
                description="Нажмите сюда, чтобы выбрать свою группу и подгруппу",
                input_message_content=InputTextMessageContent(
                    message_text=(
                        f"Привет! Для мгновенной отправки расписания настройте свой профиль в боте @{bot_username}."
                    ),
                    parse_mode="HTML",
                ),
                reply_markup=setup_btn,
            )
        )
        await query.answer(results, cache_time=5, is_personal=True)
        return

    # Карточки для сохраненных профилей пользователя
    matched_profiles = [p for p in profiles if not q or q in p["name"].lower() or q in p["group_name"].lower()]

    for p in matched_profiles[:6]:
        pid = p["id"]
        pname = p["name"]
        gid = p["group_id"]
        gname = p["group_name"]
        sg = p.get("subgroup", 0)

        try:
            sched = await fetch_schedule(gid)
            days = sched.get("days", {})
            week_info = sched.get("week_info", "")

            # 1. Сегодня
            if today_num <= 6 and today_num in days:
                txt_today = format_day_schedule(days[today_num], gname, sg, week_info=week_info, profile_label=pname)
            else:
                txt_today = f"<b>{pname}</b> | {gname}\nСегодня воскресенье — занятий нет!"

            results.append(
                InlineQueryResultArticle(
                    id=make_id(f"{pid}_today_{today}"),
                    title=f"{pname} — Сегодня ({gname})",
                    description=f"Расписание на сегодня" + (f", {sg} п/г" if sg else ""),
                    input_message_content=InputTextMessageContent(
                        message_text=txt_today,
                        parse_mode="HTML",
                    ),
                    reply_markup=open_btn,
                )
            )

            # 2. Завтра
            if tomorrow_num <= 6 and tomorrow_num in days:
                txt_tomorrow = format_day_schedule(days[tomorrow_num], gname, sg, week_info=week_info, profile_label=pname)
            else:
                txt_tomorrow = f"<b>{pname}</b> | {gname}\nЗавтра воскресенье — занятий нет!"

            results.append(
                InlineQueryResultArticle(
                    id=make_id(f"{pid}_tomorrow_{tomorrow}"),
                    title=f"{pname} — Завтра ({gname})",
                    description=f"Расписание на завтра" + (f", {sg} п/г" if sg else ""),
                    input_message_content=InputTextMessageContent(
                        message_text=txt_tomorrow,
                        parse_mode="HTML",
                    ),
                    reply_markup=open_btn,
                )
            )

            # 3. Вся неделя
            txt_week = format_week_schedule(sched, gname, sg, profile_label=pname)
            results.append(
                InlineQueryResultArticle(
                    id=make_id(f"{pid}_week_{today}"),
                    title=f"{pname} — Вся неделя ({gname})",
                    description=f"Полное расписание на текущую неделю",
                    input_message_content=InputTextMessageContent(
                        message_text=txt_week,
                        parse_mode="HTML",
                    ),
                    reply_markup=open_btn,
                )
            )
        except Exception:
            pass

    # Поиск по базе всех групп колледжа (если ввели поисковый запрос)
    if q and len(q) >= 2:
        all_groups = await get_groups()
        group_matches = [(gn, gid) for gn, gid in all_groups.items() if q in gn.lower() or q in gid]

        for gn, gid in group_matches[:3]:
            try:
                sched = await fetch_schedule(gid)
                days = sched.get("days", {})
                week_info = sched.get("week_info", "")

                if today_num <= 6 and today_num in days:
                    txt_grp_today = format_day_schedule(days[today_num], gn, subgroup=0, week_info=week_info)
                else:
                    txt_grp_today = f"Группа {gn}: сегодня воскресенье — занятий нет!"

                results.append(
                    InlineQueryResultArticle(
                        id=make_id(f"search_grp_{gid}_today_{today}"),
                        title=f"{gn} — Сегодня",
                        description=f"Расписание группы {gn} на сегодня",
                        input_message_content=InputTextMessageContent(
                            message_text=txt_grp_today,
                            parse_mode="HTML",
                        ),
                        reply_markup=open_btn,
                    )
                )

                txt_grp_week = format_week_schedule(sched, gn, subgroup=0)
                results.append(
                    InlineQueryResultArticle(
                        id=make_id(f"search_grp_{gid}_week_{today}"),
                        title=f"{gn} — Вся неделя",
                        description=f"Полное расписание группы {gn}",
                        input_message_content=InputTextMessageContent(
                            message_text=txt_grp_week,
                            parse_mode="HTML",
                        ),
                        reply_markup=open_btn,
                    )
                )
            except Exception:
                pass

    await query.answer(results, cache_time=120, is_personal=True)
