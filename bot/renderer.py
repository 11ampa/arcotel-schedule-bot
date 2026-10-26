import asyncio
import html
import re
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from bot.config import ICONS_DIR

# Cache loaded SVG icons
_icon_cache: Dict[str, str] = {}


def get_icon_inner(name: str) -> str:
    if name in _icon_cache:
        return _icon_cache[name]

    icon_path = ICONS_DIR / f"{name}.svg"
    if not icon_path.exists():
        return ""

    content = icon_path.read_text(encoding="utf-8")
    m = re.search(r"<svg[^>]*>(.*?)</svg>", content, re.DOTALL)
    inner = m.group(1).strip() if m else ""
    _icon_cache[name] = inner
    return inner


def escape_svg(text: str) -> str:
    return html.escape(text, quote=True)


def generate_schedule_card_svg(
    day_name: str,
    date_str: str,
    profile_name: str,
    group_name: str,
    subgroup: int,
    week_info: str,
    lessons: List[Dict[str, Any]],
) -> str:
    width = 820
    header_h = 130
    lesson_h = 100
    gap = 12

    if not lessons:
        height = 340
    else:
        height = header_h + len(lessons) * (lesson_h + gap) + 40

    calendar_icon = get_icon_inner("calendar")
    clock_icon = get_icon_inner("clock")
    users_icon = get_icon_inner("users")
    map_pin_icon = get_icon_inner("map-pin")
    layers_icon = get_icon_inner("layers")

    sg_text = f" • {subgroup} подгруппа" if subgroup > 0 else ""
    safe_profile = escape_svg(profile_name)
    safe_group = escape_svg(group_name)
    safe_date = escape_svg(f"{day_name}, {date_str}".strip(", "))
    safe_week = escape_svg(week_info)

    svg_parts = [
        f"""<svg width='{width}' height='{height}' viewBox='0 0 {width} {height}' xmlns='http://www.w3.org/2000/svg'>
  <defs>
    <linearGradient id='bgGrad' x1='0%' y1='0%' x2='100%' y2='100%'>
      <stop offset='0%' stop-color='#090d16'/>
      <stop offset='100%' stop-color='#111827'/>
    </linearGradient>
    <linearGradient id='accentGrad' x1='0%' y1='0%' x2='100%' y2='0%'>
      <stop offset='0%' stop-color='#3b82f6'/>
      <stop offset='100%' stop-color='#06b6d4'/>
    </linearGradient>
  </defs>

  <!-- Background -->
  <rect width='{width}' height='{height}' rx='24' fill='url(#bgGrad)' stroke='#1e293b' stroke-width='2'/>

  <!-- Header Section -->
  <g transform='translate(36, 32)'>
    <!-- Profile & Group Badge -->
    <rect x='0' y='0' width='auto' height='26' rx='6' fill='#1e293b' stroke='#334155'/>
    <text x='10' y='18' font-family='system-ui, -apple-system, Roboto, sans-serif' font-size='13' font-weight='600' fill='#38bdf8'>
      {safe_profile.upper()} • {safe_group}{sg_text.upper()}
    </text>

    <!-- Date line with calendar icon -->
    <g transform='translate(0, 36)'>
      <g transform='translate(0, 2) scale(1.1)' stroke='#60a5fa' fill='none' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
        {calendar_icon}
      </g>
      <text x='34' y='22' font-family='system-ui, -apple-system, Roboto, sans-serif' font-size='24' font-weight='bold' fill='#f8fafc'>
        {safe_date}
      </text>
    </g>

    <!-- Week info tag -->
    <text x='0' y='88' font-family='system-ui, -apple-system, Roboto, sans-serif' font-size='13' fill='#94a3b8'>
      {safe_week}
    </text>
  </g>
"""
    ]

    # Lessons rendering
    if not lessons:
        svg_parts.append(
            f"""
  <g transform='translate(36, {header_h + 30})'>
    <rect width='{width - 72}' height='120' rx='16' fill='#1e293b' fill-opacity='0.4' stroke='#334155' stroke-dasharray='6 6'/>
    <text x='{(width - 72) / 2}' y='55' text-anchor='middle' font-family='system-ui, -apple-system, Roboto, sans-serif' font-size='20' font-weight='600' fill='#f8fafc'>
      Занятий нет — выходной!
    </text>
    <text x='{(width - 72) / 2}' y='85' text-anchor='middle' font-family='system-ui, -apple-system, Roboto, sans-serif' font-size='14' fill='#64748b'>
      Отдыхайте или готовьтесь к предстоящим парам
    </text>
  </g>
"""
        )
    else:
        curr_y = header_h + 20
        for idx, l in enumerate(lessons):
            safe_num = escape_svg(str(l.get("num", "?")))
            safe_time = escape_svg(str(l.get("time", "")))
            safe_subj = escape_svg(str(l.get("subject", "")))
            safe_teacher = escape_svg(str(l.get("teacher", "")))
            safe_room = escape_svg(str(l.get("room", "")))
            safe_type = str(l.get("type", ""))
            l_subgroup = l.get("subgroup", 0)

            # Type color badge
            type_bg = "#1e293b"
            type_color = "#94a3b8"
            if "лекция" in safe_type.lower():
                type_bg = "#1e3a8a"
                type_color = "#93c5fd"
            elif "лаборатор" in safe_type.lower():
                type_bg = "#064e3b"
                type_color = "#6ee7b7"
            elif "практич" in safe_type.lower():
                type_bg = "#4c1d95"
                type_color = "#c4b5fd"

            # Truncate subject if too long
            if len(safe_subj) > 46:
                safe_subj = safe_subj[:44] + "..."

            card_svg = f"""
  <g transform='translate(36, {curr_y})'>
    <rect width='{width - 72}' height='{lesson_h}' rx='16' fill='#131c2e' stroke='#1e293b' stroke-width='1.5'/>

    <!-- Lesson Number badge -->
    <rect x='16' y='18' width='36' height='36' rx='10' fill='url(#accentGrad)'/>
    <text x='34' y='42' text-anchor='middle' font-family='system-ui, -apple-system, Roboto, sans-serif' font-size='16' font-weight='bold' fill='#ffffff'>
      {safe_num}
    </text>

    <!-- Time with clock icon -->
    <g transform='translate(64, 27) scale(0.85)' stroke='#64748b' fill='none' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
      {clock_icon}
    </g>
    <text x='88' y='41' font-family='system-ui, -apple-system, Roboto, sans-serif' font-size='14' font-weight='600' fill='#94a3b8'>
      {safe_time}
    </text>

    <!-- Lesson type pill -->
    <rect x='200' y='25' width='{len(safe_type) * 9 + 18}' height='22' rx='6' fill='{type_bg}'/>
    <text x='209' y='40' font-family='system-ui, -apple-system, Roboto, sans-serif' font-size='12' font-weight='600' fill='{type_color}'>
      {escape_svg(safe_type)}
    </text>
"""
            # Subgroup pill if applicable
            if l_subgroup > 0:
                card_svg += f"""
    <rect x='{210 + len(safe_type) * 9 + 18}' y='25' width='60' height='22' rx='6' fill='#312e81'/>
    <text x='{220 + len(safe_type) * 9 + 18}' y='40' font-family='system-ui, -apple-system, Roboto, sans-serif' font-size='12' font-weight='600' fill='#a5b4fc'>
      {l_subgroup} п/г
    </text>
"""

            # Subject Title
            card_svg += f"""
    <text x='64' y='68' font-family='system-ui, -apple-system, Roboto, sans-serif' font-size='17' font-weight='bold' fill='#f8fafc'>
      {safe_subj}
    </text>

    <!-- Bottom info: Room and Teacher -->
    <g transform='translate(64, 76)'>
"""
            offset_x = 0
            if safe_room:
                card_svg += f"""
      <g transform='translate({offset_x}, 2) scale(0.75)' stroke='#38bdf8' fill='none' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
        {map_pin_icon}
      </g>
      <text x='{offset_x + 20}' y='15' font-family='system-ui, -apple-system, Roboto, sans-serif' font-size='13' font-weight='500' fill='#38bdf8'>
        {safe_room}
      </text>
"""
                offset_x += len(safe_room) * 8 + 40

            if safe_teacher:
                card_svg += f"""
      <g transform='translate({offset_x}, 2) scale(0.75)' stroke='#94a3b8' fill='none' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
        {users_icon}
      </g>
      <text x='{offset_x + 20}' y='15' font-family='system-ui, -apple-system, Roboto, sans-serif' font-size='13' fill='#94a3b8'>
        {safe_teacher}
      </text>
"""
            card_svg += """
    </g>
  </g>
"""
            svg_parts.append(card_svg)
            curr_y += lesson_h + gap

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def render_svg_to_png(svg_string: str) -> bytes:
    try:
        proc = subprocess.run(
            ["rsvg-convert", "-f", "png"],
            input=svg_string.encode("utf-8"),
            capture_output=True,
            check=True,
            timeout=5,
        )
        return proc.stdout
    except Exception as e:
        print(f"Error rendering SVG to PNG: {e}")
        return b""
