#!/usr/bin/env python3
"""комплексный тест всех подсистем бота расписания."""
from __future__ import annotations

import asyncio
from bot.storage import (
    get_user_settings,
    add_user_profile,
    get_active_profile,
    set_active_profile,
    delete_user_profile,
)
from bot.parser import get_groups, fetch_schedule, format_day_schedule, format_week_schedule
from bot.renderer import generate_schedule_card_svg, render_svg_to_png
from bot.keyboards import (
    get_main_menu_keyboard,
    get_group_pagination_keyboard,
    get_categories_keyboard,
    get_profiles_manager_keyboard,
)
from bot.handlers.menu import render_schedule_view


async def test_full_suite() -> int:
    print("=== ТЕСТ 1: Получение групп с сайта arcotel.ru ===")
    groups = await get_groups()
    assert len(groups) >= 30, f"слишком мало групп: {len(groups)}"
    assert "ИСПП-31" in groups, "группа ИСПП-31 не найдена!"
    print(f"успешно: найдено {len(groups)} групп.")

    print("\n=== ТЕСТ 2: Динамические профили (без хардкода) ===")
    uid = "test_user_42"
    p1 = await add_user_profile(uid, name="Егор", group_id="55716", group_name="ИСПП-31", subgroup=1)
    p2 = await add_user_profile(uid, name="Светлана", group_id="55716", group_name="ИСПП-31", subgroup=2)
    p3 = await add_user_profile(uid, name="Кирилл", group_id="55715", group_name="ССА-31", subgroup=0)

    settings = await get_user_settings(uid)
    assert len(settings["profiles"]) == 3, "должно быть 3 профиля!"

    active = await get_active_profile(uid)
    assert active["id"] == p1["id"], "первый профиль должен быть активным!"

    # переключение на Светлану
    await set_active_profile(uid, p2["id"])
    active_sveta = await get_active_profile(uid)
    assert active_sveta["name"] == "Светлана"
    print("успешно: создание, переключение и хранение профилей проверено.")

    print("\n=== ТЕСТ 3: Пагинация меню и групп ===")
    kb_main = get_main_menu_keyboard(settings, active_sveta)
    assert len(kb_main.inline_keyboard) >= 5, "в главном меню должно быть минимум 5 строк кнопок!"

    kb_grp_p0 = get_group_pagination_keyboard(groups, page=0, per_page=8)
    assert len(kb_grp_p0.inline_keyboard) >= 4, "в списке групп должна быть пагинация!"

    kb_cats = get_categories_keyboard(["ИСПП", "ИСС", "КСК", "ОИБ"])
    assert len(kb_cats.inline_keyboard) >= 2, "кнопки категорий сформированы!"
    print("успешно: пагинация и клавиатуры протестированы.")

    print("\n=== ТЕСТ 4: Рендеринг текстового расписания ===")
    text, kb, act, day_data = await render_schedule_view(uid)
    assert "ИСПП-31" in text
    assert "Светлана" in text
    print(f"успешно: текстовое расписание собрано:\n{text[:180]}...")

    print("\n=== ТЕСТ 5: Генерация визуальной карточки с SVG-иконками ===")
    sched = await fetch_schedule("55716")
    mon = sched["days"][1]
    svg = generate_schedule_card_svg(
        day_name=mon["day_name"],
        date_str=mon["date_str"],
        profile_name="Егор",
        group_name="ИСПП-31",
        subgroup=1,
        week_info=sched.get("week_info", ""),
        lessons=mon["lessons"],
    )
    assert "<svg" in svg and "</svg>" in svg
    assert "clock" in svg or "calendar" in svg

    png = render_svg_to_png(svg)
    assert len(png) > 5000, f"размер png подозрительно мал: {len(png)} байт"
    print(f"успешно: сгенерирована карточка PNG ({len(png)} байт).")

    print("\n=== ТЕСТ 6: Удаление профиля ===")
    await delete_user_profile(uid, p3["id"])
    settings_after = await get_user_settings(uid)
    assert len(settings_after["profiles"]) == 2, "должно остаться 2 профиля!"
    print("успешно: удаление профиля проверено.")

    print("\nВСЕ ТЕСТЫ УСПЕШНО ПРОЙДЕНЫ! 🎉")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(test_full_suite()))
