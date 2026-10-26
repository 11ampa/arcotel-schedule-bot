import math
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Dict, Any, List, Optional


def get_main_menu_keyboard(
    user_data: Dict[str, Any],
    active_profile: Optional[Dict[str, Any]] = None,
) -> InlineKeyboardMarkup:
    """
    Main interactive keyboard with profile pagination, day selector,
    week navigation, subgroup toggle and actions.
    """
    profiles = user_data.get("profiles", [])
    active_id = active_profile["id"] if active_profile else None
    subgroup = active_profile.get("subgroup", 0) if active_profile else 0
    view_mode = user_data.get("view_mode", "today")
    selected_day = user_data.get("selected_day_idx")
    week_offset = user_data.get("week_offset", 0)

    rows = []

    # Row 1: Profile switcher with pagination if > 3 profiles
    profiles_page = user_data.get("profiles_page", 0)
    per_page = 3
    total_pages = max(1, math.ceil(len(profiles) / per_page))
    if profiles_page >= total_pages:
        profiles_page = 0

    page_profiles = profiles[profiles_page * per_page : (profiles_page + 1) * per_page]

    row_profiles = []
    for p in page_profiles:
        is_act = p["id"] == active_id
        text = f"• {p['name']} •" if is_act else p["name"]
        row_profiles.append(InlineKeyboardButton(text=text, callback_data=f"prof_switch:{p['id']}"))

    if row_profiles:
        rows.append(row_profiles)

    # If multiple profile pages, show pagination row
    if total_pages > 1:
        rows.append([
            InlineKeyboardButton(text="◀", callback_data="prof_page:prev"),
            InlineKeyboardButton(text=f"{profiles_page + 1}/{total_pages}", callback_data="prof_page:noop"),
            InlineKeyboardButton(text="▶", callback_data="prof_page:next"),
            InlineKeyboardButton(text="+ Профиль", callback_data="profile:add"),
        ])
    elif len(profiles) <= 2:
        rows[-1].append(InlineKeyboardButton(text="+ Профиль", callback_data="profile:add"))

    # Row 2: View modes (Сегодня, Завтра, Вся неделя)
    today_btn = "• Сегодня •" if view_mode == "today" else "Сегодня"
    tomorrow_btn = "• Завтра •" if view_mode == "tomorrow" else "Завтра"
    week_btn = "• Вся неделя •" if view_mode == "week" else "Вся неделя"

    rows.append([
        InlineKeyboardButton(text=today_btn, callback_data="mode:today"),
        InlineKeyboardButton(text=tomorrow_btn, callback_data="mode:tomorrow"),
        InlineKeyboardButton(text=week_btn, callback_data="mode:week"),
    ])

    # Row 3: Day selector
    days_short = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
    row_days = []
    for idx, d_name in enumerate(days_short, start=1):
        is_sel = (view_mode == "day" and selected_day == idx)
        btn_text = f"[{d_name}]" if is_sel else d_name
        row_days.append(InlineKeyboardButton(text=btn_text, callback_data=f"day:{idx}"))
    rows.append(row_days)

    # Row 4: Week navigation
    curr_label = "Текущая нед." if week_offset == 0 else f"{week_offset:+d} нед."
    rows.append([
        InlineKeyboardButton(text="◀ Пред. нед.", callback_data="week_nav:prev"),
        InlineKeyboardButton(text=curr_label, callback_data="week_nav:current"),
        InlineKeyboardButton(text="След. нед. ▶", callback_data="week_nav:next"),
    ])

    # Row 5: Subgroup selector
    sg_all = "• Все •" if subgroup == 0 else "Все"
    sg_1 = "• 1 п/г •" if subgroup == 1 else "1 п/г"
    sg_2 = "• 2 п/г •" if subgroup == 2 else "2 п/г"
    rows.append([
        InlineKeyboardButton(text=sg_all, callback_data="subgroup:0"),
        InlineKeyboardButton(text=sg_1, callback_data="subgroup:1"),
        InlineKeyboardButton(text=sg_2, callback_data="subgroup:2"),
    ])

    # Row 6: Image card view & settings
    rows.append([
        InlineKeyboardButton(text="🖼 Карточка", callback_data="action:send_card"),
        InlineKeyboardButton(text="⚙️ Профили", callback_data="menu:profiles"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data="action:refresh"),
        InlineKeyboardButton(text="✕ Закрыть", callback_data="action:close"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_profiles_manager_keyboard(
    profiles: List[Dict[str, Any]],
    active_id: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """
    Manager view: list all profiles, delete or add new.
    """
    buttons = []
    for p in profiles:
        is_act = p["id"] == active_id
        mark = "✓ " if is_act else ""
        sg_text = f", {p['subgroup']} п/г" if p["subgroup"] > 0 else ""
        label = f"{mark}{p['name']} ({p['group_name']}{sg_text})"

        buttons.append([
            InlineKeyboardButton(text=label, callback_data=f"prof_switch:{p['id']}"),
            InlineKeyboardButton(text="Удалить ✕", callback_data=f"prof_del:{p['id']}"),
        ])

    buttons.append([
        InlineKeyboardButton(text="+ Добавить профиль", callback_data="profile:add"),
        InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="action:back_to_menu"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_group_pagination_keyboard(
    groups: Dict[str, str],
    page: int = 0,
    per_page: int = 8,
    category: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """
    Paginated list of groups (8 per page) with category support.
    """
    all_names = sorted(groups.keys())
    if category:
        all_names = [g for g in all_names if g.startswith(category)]

    total_pages = max(1, math.ceil(len(all_names) / per_page))
    page = max(0, min(page, total_pages - 1))

    page_items = all_names[page * per_page : (page + 1) * per_page]

    buttons = []
    row = []
    for g in page_items:
        row.append(InlineKeyboardButton(text=g, callback_data=f"grp_sel:{g}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Navigation row
    nav_row = [
        InlineKeyboardButton(text="◀", callback_data=f"grp_page:{page - 1}:{category or ''}"),
        InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="grp_page:noop"),
        InlineKeyboardButton(text="▶", callback_data=f"grp_page:{page + 1}:{category or ''}"),
    ]
    buttons.append(nav_row)

    # Categories button & Cancel
    action_row = []
    if category:
        action_row.append(InlineKeyboardButton(text="Все категории", callback_data="grp_cat_list"))
    else:
        action_row.append(InlineKeyboardButton(text="По направлениям", callback_data="grp_cat_list"))

    action_row.append(InlineKeyboardButton(text="⬅️ Отмена", callback_data="action:back_to_menu"))
    buttons.append(action_row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_categories_keyboard(categories: List[str]) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for cat in sorted(categories):
        row.append(InlineKeyboardButton(text=cat, callback_data=f"grp_filter_cat:{cat}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton(text="Все группы (списком)", callback_data="grp_page:0:"),
        InlineKeyboardButton(text="⬅️ Отмена", callback_data="action:back_to_menu"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_subgroup_selection_keyboard(temp_profile_name: str, group_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Вся группа (без деления)", callback_data="wizard_sg:0")],
            [InlineKeyboardButton(text="1-я подгруппа", callback_data="wizard_sg:1")],
            [InlineKeyboardButton(text="2-я подгруппа", callback_data="wizard_sg:2")],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="action:back_to_menu")],
        ]
    )


def get_onboarding_name_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Мой профиль", callback_data="wizard_name:Мой профиль"),
                InlineKeyboardButton(text="Студент", callback_data="wizard_name:Студент"),
            ],
            [
                InlineKeyboardButton(text="Я", callback_data="wizard_name:Я"),
                InlineKeyboardButton(text="Ввести имя текстом", callback_data="wizard_name_custom"),
            ],
        ]
    )
