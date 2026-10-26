#!/usr/bin/env python3
"""обработчики команд меню, интерактивных кнопок и визарда настройки."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest

from bot.storage import (
    get_user_settings,
    update_user_settings,
    add_user_profile,
    get_active_profile,
    set_active_profile,
    delete_user_profile,
)
from bot.parser import (
    get_groups,
    fetch_schedule,
    format_day_schedule,
    format_week_schedule,
    get_current_moscow_date,
    filter_lessons,
    _schedule_cache,
)
from bot.renderer import generate_schedule_card_svg, render_svg_to_png
from bot.keyboards import (
    get_main_menu_keyboard,
    get_profiles_manager_keyboard,
    get_group_pagination_keyboard,
    get_categories_keyboard,
    get_subgroup_selection_keyboard,
    get_onboarding_name_keyboard,
)

router = Router()


async def render_schedule_view(user_id: int | str) -> tuple[str, Any, dict[str, Any] | None, dict[str, Any] | None]:
    """Возвращает (текст, клавиатура, активный_профиль, данные_дня_для_карточки)."""
    user_data = await get_user_settings(user_id)
    active_profile = await get_active_profile(user_id)

    if not active_profile:
        return (
            "У вас пока не настроено ни одного профиля.\n"
            "Нажмите кнопку ниже, чтобы добавить свой первый профиль.",
            get_onboarding_name_keyboard(),
            None,
            None,
        )

    group_id = active_profile["group_id"]
    group_name = active_profile["group_name"]
    subgroup = active_profile.get("subgroup", 0)
    profile_name = active_profile["name"]

    view_mode = user_data.get("view_mode", "today")
    selected_day = user_data.get("selected_day_idx")
    week_offset = user_data.get("week_offset", 0)

    today = get_current_moscow_date()
    today_weekday = today.weekday() + 1

    curr_monday = today - timedelta(days=today.weekday())
    target_monday = curr_monday + timedelta(weeks=week_offset)
    date_param = target_monday.strftime("%Y-%m-%d")

    try:
        schedule = await fetch_schedule(group_id, date_param)
    except Exception as e:
        error_text = (
            f"Не удалось загрузить расписание для группы <b>{group_name}</b>:\n"
            f"<i>{e}</i>\n\n"
            f"Нажмите «Обновить» через несколько секунд."
        )
        return error_text, get_main_menu_keyboard(user_data, active_profile), active_profile, None

    week_info = schedule.get("week_info", "")
    days = schedule.get("days", {})

    target_day_data: dict[str, Any] | None = None
    text = ""

    if view_mode == "week":
        text = format_week_schedule(schedule, group_name, subgroup, profile_label=profile_name)
    elif view_mode == "tomorrow":
        t_tomorrow = today + timedelta(days=1)
        target_day_num = t_tomorrow.weekday() + 1
        if target_day_num == 7:
            text = (
                f"<b>Воскресенье</b> [{profile_name}]\n"
                f"Группа: <b>{group_name}</b>\n"
                f"───────────────────────\n\n"
                f"<b>Завтра воскресенье — официальный выходной!</b>\n"
                f"Выберите <b>[Пн]</b>, чтобы посмотреть расписание на понедельник."
            )
        else:
            target_day_data = days.get(target_day_num)
            if target_day_data:
                text = format_day_schedule(
                    target_day_data, group_name, subgroup, week_info=week_info, profile_label=profile_name
                )
            else:
                text = f"Занятий на завтра не найдено ({group_name})."
    elif view_mode == "day" and selected_day in days:
        target_day_data = days[selected_day]
        text = format_day_schedule(
            target_day_data, group_name, subgroup, week_info=week_info, profile_label=profile_name
        )
    else:  # today
        if week_offset == 0 and today_weekday == 7:
            text = (
                f"<b>Воскресенье</b> [{profile_name}]\n"
                f"Группа: <b>{group_name}</b>\n"
                f"───────────────────────\n\n"
                f"<b>Сегодня воскресенье — выходной!</b>\n"
                f"Выберите <b>«Завтра»</b> или <b>«Вся неделя»</b> в меню."
            )
        else:
            target_idx = today_weekday if (week_offset == 0 and 1 <= today_weekday <= 6) else 1
            target_day_data = days.get(target_idx)
            if target_day_data:
                text = format_day_schedule(
                    target_day_data, group_name, subgroup, week_info=week_info, profile_label=profile_name
                )
            else:
                text = f"Занятий не найдено ({group_name})."

    keyboard = get_main_menu_keyboard(user_data, active_profile)
    return text, keyboard, active_profile, target_day_data


@router.message(CommandStart())
@router.message(Command("schedule", "raspisanie", "menu"))
async def cmd_start_or_schedule(message: Message) -> None:
    user_id = message.from_user.id
    user_data = await get_user_settings(user_id)
    profiles = user_data.get("profiles", [])

    if not profiles:
        # запуск мастера первичной настройки
        await update_user_settings(user_id, wizard={"step": "name"})
        welcome_text = (
            "<b>Добро пожаловать в бота расписания АКТ (ф) СПбГУТ!</b>\n\n"
            "Давайте настроим ваш первый профиль.\n"
            "Как вас называть в боте?"
        )
        await message.answer(welcome_text, reply_markup=get_onboarding_name_keyboard(), parse_mode="HTML")
        return

    text, keyboard, _, _ = await render_schedule_view(user_id)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    help_text = (
        "<b>Справка по боту расписания:</b>\n\n"
        "• <b>Профили</b>: Поддерживается любое количество профилей (для себя, одногруппников, друзей).\n"
        "• <b>Навигация</b>: Сегодня, Завтра, Вся неделя, конкретные дни [Пн]..[Сб] и перелистывание недель.\n"
        "• <b>Подгруппы</b>: Быстрое переключение между Всеми, 1-й и 2-й подгруппами.\n"
        "• <b>Карточка</b>: Кнопка «Карточка» генерирует стильный png-виджет с векторными SVG-иконками.\n\n"
        "<b>Инлайн-вызов в любом чате:</b>\n"
        "<code>@fz_arcotel_bot</code> — сразу предлагает карточки ваших сохраненных профилей.\n"
        "<code>@fz_arcotel_bot испп-31</code> — поиск расписания по номеру любой группы."
    )
    await message.answer(help_text, parse_mode="HTML")


@router.message(Command("clean", "clear"))
async def cmd_clean(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        pass


# Обработка текстового ввода имени в визарде
@router.message(F.text & ~F.text.startswith("/"))
async def handle_custom_name_input(message: Message) -> None:
    user_id = message.from_user.id
    user_data = await get_user_settings(user_id)
    wizard = user_data.get("wizard")

    if wizard and wizard.get("step") == "name":
        name = message.text.strip()[:32]
        await update_user_settings(user_id, wizard={"step": "group", "name": name, "page": 0})
        groups = await get_groups()
        await message.answer(
            f"Отлично, профиль: <b>{name}</b>.\n"
            f"Теперь выберите вашу учебную группу:",
            reply_markup=get_group_pagination_keyboard(groups, page=0),
            parse_mode="HTML",
        )


# Выбор имени по кнопке в визарде
@router.callback_query(F.data.startswith("wizard_name:"))
async def cb_wizard_name(callback: CallbackQuery) -> None:
    await callback.answer()
    name = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    await update_user_settings(user_id, wizard={"step": "group", "name": name, "page": 0})
    groups = await get_groups()
    await callback.message.edit_text(
        f"Профиль: <b>{name}</b>.\n"
        f"Выберите учебную группу:",
        reply_markup=get_group_pagination_keyboard(groups, page=0),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "wizard_name_custom")
async def cb_wizard_name_custom(callback: CallbackQuery) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    await update_user_settings(user_id, wizard={"step": "name"})
    await callback.message.edit_text(
        "Напишите желаемое имя профиля в чат (например: <i>Студент</i>, <i>Моё расписание</i>, <i>Группа 31</i>):",
        parse_mode="HTML",
    )


# Добавление профиля
@router.callback_query(F.data == "profile:add")
async def cb_profile_add(callback: CallbackQuery) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    await update_user_settings(user_id, wizard={"step": "name"})
    await callback.message.edit_text(
        "<b>Добавление нового профиля:</b>\n"
        "Выберите или отправьте в чат имя для профиля:",
        reply_markup=get_onboarding_name_keyboard(),
        parse_mode="HTML",
    )


# Пагинация списка групп в визарде
@router.callback_query(F.data.startswith("grp_page:"))
async def cb_grp_page(callback: CallbackQuery) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    if parts[1] == "noop":
        return
    page = int(parts[1])
    cat = parts[2] if len(parts) > 2 and parts[2] else None
    groups = await get_groups()
    try:
        await callback.message.edit_reply_markup(
            reply_markup=get_group_pagination_keyboard(groups, page=page, category=cat)
        )
    except TelegramBadRequest:
        pass


# Список категорий групп
@router.callback_query(F.data == "grp_cat_list")
async def cb_grp_cat_list(callback: CallbackQuery) -> None:
    await callback.answer()
    groups = await get_groups()
    categories = set()
    for g in groups.keys():
        m = re.match(r"^([А-Яа-яёЁA-Za-z]+)", g)
        if m:
            categories.add(m.group(1))
    await callback.message.edit_text(
        "Выберите направление обучения:",
        reply_markup=get_categories_keyboard(list(categories)),
        parse_mode="HTML",
    )


# Фильтр по категории
@router.callback_query(F.data.startswith("grp_filter_cat:"))
async def cb_grp_filter_cat(callback: CallbackQuery) -> None:
    await callback.answer()
    cat = callback.data.split(":", 1)[1]
    groups = await get_groups()
    await callback.message.edit_text(
        f"Группы направления <b>{cat}</b>:",
        reply_markup=get_group_pagination_keyboard(groups, page=0, category=cat),
        parse_mode="HTML",
    )


# Выбор конкретной группы
@router.callback_query(F.data.startswith("grp_sel:"))
async def cb_grp_sel(callback: CallbackQuery) -> None:
    await callback.answer()
    group_name = callback.data.split(":", 1)[1]
    groups = await get_groups()
    group_id = groups.get(group_name)

    if not group_id:
        await callback.answer("Группа не найдена!", show_alert=True)
        return

    user_id = callback.from_user.id
    user_data = await get_user_settings(user_id)
    wizard = user_data.get("wizard")

    if wizard:
        wizard["group_name"] = group_name
        wizard["group_id"] = group_id
        wizard["step"] = "subgroup"
        await update_user_settings(user_id, wizard=wizard)
        await callback.message.edit_text(
            f"Выбрана группа: <b>{group_name}</b>.\n"
            f"Укажите вашу подгруппу:",
            reply_markup=get_subgroup_selection_keyboard(wizard.get("name", ""), group_name),
            parse_mode="HTML",
        )
    else:
        # Если менялась группа текущего активного профиля
        active = await get_active_profile(user_id)
        if active:
            active["group_id"] = group_id
            active["group_name"] = group_name
            await update_user_settings(user_id, profiles=user_data.get("profiles", []))
        text, keyboard, _, _ = await render_schedule_view(user_id)
        try:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        except TelegramBadRequest:
            pass


# Выбор подгруппы в визарде и завершение настройки
@router.callback_query(F.data.startswith("wizard_sg:"))
async def cb_wizard_sg(callback: CallbackQuery) -> None:
    await callback.answer()
    sg = int(callback.data.split(":", 1)[1])
    user_id = callback.from_user.id
    user_data = await get_user_settings(user_id)
    wizard = user_data.get("wizard")

    if wizard:
        name = wizard.get("name", "Мой профиль")
        gid = wizard.get("group_id", "55716")
        gname = wizard.get("group_name", "ИСПП-31")
        await add_user_profile(user_id, name=name, group_id=gid, group_name=gname, subgroup=sg)
        await update_user_settings(user_id, wizard=None)

    text, keyboard, _, _ = await render_schedule_view(user_id)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        pass


# Переключение активного профиля
@router.callback_query(F.data.startswith("prof_switch:"))
async def cb_prof_switch(callback: CallbackQuery) -> None:
    await callback.answer()
    pid = callback.data.split(":", 1)[1]
    await set_active_profile(callback.from_user.id, pid)
    text, keyboard, _, _ = await render_schedule_view(callback.from_user.id)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        pass


# Пагинация списка профилей
@router.callback_query(F.data.startswith("prof_page:"))
async def cb_prof_page(callback: CallbackQuery) -> None:
    await callback.answer()
    action = callback.data.split(":", 1)[1]
    if action == "noop":
        return
    user_data = await get_user_settings(callback.from_user.id)
    curr = user_data.get("profiles_page", 0)
    new_page = curr - 1 if action == "prev" else curr + 1
    await update_user_settings(callback.from_user.id, profiles_page=max(0, new_page))
    text, keyboard, _, _ = await render_schedule_view(callback.from_user.id)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        pass


# Меню управления профилями
@router.callback_query(F.data == "menu:profiles")
async def cb_menu_profiles(callback: CallbackQuery) -> None:
    await callback.answer()
    user_data = await get_user_settings(callback.from_user.id)
    profiles = user_data.get("profiles", [])
    active_id = user_data.get("active_profile_id")
    text = (
        "<b>Управление профилями:</b>\n\n"
        "Вы можете добавить любое количество людей с разными группами и подгруппами.\n"
        "Нажмите на профиль для активации или удалите ненужный."
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_profiles_manager_keyboard(profiles, active_id),
        parse_mode="HTML",
    )


# Удаление профиля
@router.callback_query(F.data.startswith("prof_del:"))
async def cb_prof_del(callback: CallbackQuery) -> None:
    pid = callback.data.split(":", 1)[1]
    await delete_user_profile(callback.from_user.id, pid)
    await callback.answer("Профиль удален.")
    user_data = await get_user_settings(callback.from_user.id)
    profiles = user_data.get("profiles", [])
    active_id = user_data.get("active_profile_id")

    if not profiles:
        text, keyboard, _, _ = await render_schedule_view(callback.from_user.id)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        return

    text = "<b>Управление профилями:</b>"
    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_profiles_manager_keyboard(profiles, active_id),
            parse_mode="HTML",
        )
    except TelegramBadRequest:
        pass


# Переключение режима отображения (сегодня/завтра/неделя)
@router.callback_query(F.data.startswith("mode:"))
async def cb_mode_switch(callback: CallbackQuery) -> None:
    await callback.answer()
    mode = callback.data.split(":")[1]
    await update_user_settings(callback.from_user.id, view_mode=mode, selected_day_idx=None)
    text, keyboard, _, _ = await render_schedule_view(callback.from_user.id)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        pass


# Выбор конкретного дня недели
@router.callback_query(F.data.startswith("day:"))
async def cb_day_select(callback: CallbackQuery) -> None:
    await callback.answer()
    day_idx = int(callback.data.split(":")[1])
    await update_user_settings(callback.from_user.id, view_mode="day", selected_day_idx=day_idx)
    text, keyboard, _, _ = await render_schedule_view(callback.from_user.id)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        pass


# Перелистывание недели
@router.callback_query(F.data.startswith("week_nav:"))
async def cb_week_nav(callback: CallbackQuery) -> None:
    await callback.answer()
    action = callback.data.split(":")[1]
    user_data = await get_user_settings(callback.from_user.id)
    curr_offset = user_data.get("week_offset", 0)

    if action == "prev":
        new_offset = curr_offset - 1
    elif action == "next":
        new_offset = curr_offset + 1
    else:
        new_offset = 0

    await update_user_settings(callback.from_user.id, week_offset=new_offset)
    text, keyboard, _, _ = await render_schedule_view(callback.from_user.id)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        pass


# Переключение подгруппы в меню
@router.callback_query(F.data.startswith("subgroup:"))
async def cb_subgroup(callback: CallbackQuery) -> None:
    await callback.answer()
    sg = int(callback.data.split(":")[1])
    active = await get_active_profile(callback.from_user.id)
    if active:
        active["subgroup"] = sg
        user_data = await get_user_settings(callback.from_user.id)
        await update_user_settings(callback.from_user.id, profiles=user_data.get("profiles", []))

    text, keyboard, _, _ = await render_schedule_view(callback.from_user.id)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        pass


# Генерация и отправка карточки-расписания с векторными SVG-иконками
@router.callback_query(F.data == "action:send_card")
async def cb_send_card(callback: CallbackQuery) -> None:
    await callback.answer("Рендерю карточку с SVG-иконками...")
    user_id = callback.from_user.id
    active_profile = await get_active_profile(user_id)
    if not active_profile:
        return

    user_data = await get_user_settings(user_id)
    group_id = active_profile["group_id"]
    group_name = active_profile["group_name"]
    subgroup = active_profile.get("subgroup", 0)
    profile_name = active_profile["name"]

    selected_day = user_data.get("selected_day_idx")
    today = get_current_moscow_date()
    curr_monday = today - timedelta(days=today.weekday())
    target_monday = curr_monday + timedelta(weeks=user_data.get("week_offset", 0))

    try:
        schedule = await fetch_schedule(group_id, target_monday.strftime("%Y-%m-%d"))
    except Exception as e:
        await callback.message.answer(f"Ошибка загрузки данных: {e}")
        return

    days = schedule.get("days", {})
    target_idx = selected_day if selected_day else (today.weekday() + 1 if 1 <= today.weekday() + 1 <= 6 else 1)
    day_data = days.get(target_idx, {})

    day_name = day_data.get("day_name", "Расписание")
    date_str = day_data.get("date_str", "")
    lessons = filter_lessons(day_data.get("lessons", []), subgroup)
    week_info = schedule.get("week_info", "")

    svg_content = generate_schedule_card_svg(
        day_name=day_name,
        date_str=date_str,
        profile_name=profile_name,
        group_name=group_name,
        subgroup=subgroup,
        week_info=week_info,
        lessons=lessons,
    )
    png_bytes = render_svg_to_png(svg_content)

    if png_bytes:
        photo = BufferedInputFile(png_bytes, filename=f"schedule_{group_name}_{target_idx}.png")
        await callback.message.answer_photo(
            photo=photo,
            caption=f"<b>{profile_name}</b> | {group_name} ({day_name} {date_str})",
            parse_mode="HTML",
        )
    else:
        await callback.message.answer("Не удалось сгенерировать карточку.")


# Обновить кэш
@router.callback_query(F.data == "action:refresh")
async def cb_refresh(callback: CallbackQuery) -> None:
    active = await get_active_profile(callback.from_user.id)
    if active:
        gid = active["group_id"]
        keys = [k for k in _schedule_cache.keys() if k.startswith(f"{gid}:")]
        for k in keys:
            _schedule_cache.pop(k, None)

    await callback.answer("Расписание обновлено!")
    text, keyboard, _, _ = await render_schedule_view(callback.from_user.id)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        pass


# Закрыть
@router.callback_query(F.data == "action:close")
async def cb_close(callback: CallbackQuery) -> None:
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass


# Назад в главное меню
@router.callback_query(F.data == "action:back_to_menu")
async def cb_back_to_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    await update_user_settings(callback.from_user.id, wizard=None)
    text, keyboard, _, _ = await render_schedule_view(callback.from_user.id)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest:
        pass
