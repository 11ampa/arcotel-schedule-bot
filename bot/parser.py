#!/usr/bin/env python3
"""асинхронный парсер и форматтер расписания с сайта arcotel.ru."""
from __future__ import annotations

import aiohttp
import asyncio
import html
import json
import re
import time
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

from bot.config import (
    BASE_SCHEDULE_URL,
    CACHE_TTL,
    GROUPS_CACHE_FILE,
    SCHEDULE_PROXY,
    TIMEZONE,
)

# in-memory кэш расписания: ключ -> (timestamp, data)
_schedule_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_groups_cache: dict[str, str] | None = None
_groups_cache_time: float = 0

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}


def get_current_moscow_date() -> date:
    return datetime.now(ZoneInfo(TIMEZONE)).date()


def create_client_session() -> aiohttp.ClientSession:
    if SCHEDULE_PROXY:
        try:
            from aiohttp_socks import ProxyConnector
            connector = ProxyConnector.from_url(SCHEDULE_PROXY, ssl=False)
            return aiohttp.ClientSession(connector=connector)
        except Exception:
            pass
    connector = aiohttp.TCPConnector(ssl=False)
    return aiohttp.ClientSession(connector=connector)


async def get_groups() -> dict[str, str]:
    global _groups_cache, _groups_cache_time
    now = time.time()
    if _groups_cache and (now - _groups_cache_time < 86400):
        return _groups_cache

    if GROUPS_CACHE_FILE.exists():
        try:
            with open(GROUPS_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data and isinstance(data, dict):
                    _groups_cache = data
                    _groups_cache_time = now
        except Exception:
            pass

    try:
        async with create_client_session() as session:
            async with session.get(BASE_SCHEDULE_URL, headers=DEFAULT_HEADERS, timeout=12) as resp:
                if resp.status == 200:
                    html_text = await resp.text()
                    soup = BeautifulSoup(html_text, "html.parser")
                    groups: dict[str, str] = {}
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        m = re.search(r"\bgroup=(\d+)", href)
                        name = a.get_text(strip=True)
                        if m and name:
                            gid = m.group(1)
                            if re.match(r"^[А-Яа-яёЁA-Za-z0-9\-]+$", name):
                                groups[name] = gid
                    if groups:
                        _groups_cache = groups
                        _groups_cache_time = now
                        try:
                            with open(GROUPS_CACHE_FILE, "w", encoding="utf-8") as f:
                                json.dump(groups, f, ensure_ascii=False, indent=2)
                        except Exception:
                            pass
                        return groups
    except Exception as e:
        print(f"ошибка получения групп: {e}")

    return _groups_cache or {
        "ИСПП-31": "55716",
        "ИСПП-34": "55720",
        "ИСПП-41": "55957",
        "ИСПП-43": "56507",
        "ИСПП-45": "55959",
        "ИСПП-51": "56746",
        "ИСПП-55": "56750",
    }


def parse_schedule_html(html_text: str, group_id: str) -> dict[str, Any]:
    soup = BeautifulSoup(html_text, "html.parser")

    week_div = soup.find("div", class_="vt234")
    week_info = " ".join(week_div.stripped_strings) if week_div else ""

    prev_a = soup.find("a", id="rasp-prev")
    next_a = soup.find("a", id="rasp-next")

    def extract_date_param(a_tag: Any) -> str | None:
        if not a_tag or not a_tag.has_attr("href"):
            return None
        m = re.search(r"date=([\d-]+)", a_tag["href"])
        return m.group(1) if m else None

    prev_date = extract_date_param(prev_a)
    next_date = extract_date_param(next_a)

    days_meta: dict[int, dict[str, Any]] = {}
    for day_head in soup.find_all("div", class_=re.compile(r"vt237\b")):
        day_i = day_head.get("data-i")
        if day_i and day_i.isdigit():
            day_num = int(day_i)
            sub_div = day_head.find("div", class_="vt238")
            day_name = sub_div.get_text(strip=True) if sub_div else ""
            full_text = day_head.get_text(" ", strip=True)
            date_text = full_text.replace(day_name, "").strip()
            days_meta[day_num] = {
                "day_num": day_num,
                "day_name": day_name.capitalize(),
                "date_str": date_text,
            }

    default_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]
    for i in range(1, 7):
        if i not in days_meta:
            days_meta[i] = {
                "day_num": i,
                "day_name": default_names[i - 1],
                "date_str": "",
            }

    days_lessons: dict[int, list[dict[str, Any]]] = {i: [] for i in range(1, 7)}
    rows = soup.find_all("div", class_=re.compile(r"vt244\b"))

    for row in rows:
        if "vt244a" in row.get("class", []):
            continue

        first_col = row.find("div", class_="vt239")
        if not first_col:
            continue

        num_div = first_col.find("div", class_="vt283")
        num = num_div.get_text(strip=True) if num_div else "?"

        time_lines = [s for s in first_col.stripped_strings if s != num]
        time_str = "-".join(time_lines) if time_lines else ""

        for day_i in range(1, 7):
            day_col = row.find("div", class_=re.compile(rf"rasp-day{day_i}\b"))
            if not day_col:
                continue
            cards = day_col.find_all("div", class_="vt258")
            for card in cards:
                subj_div = card.find("div", class_="vt240")
                subj = subj_div.get_text(strip=True) if subj_div else ""

                teacher_span = card.find("span", class_="teacher")
                teacher = teacher_span.get_text(strip=True) if teacher_span else ""

                room_div = card.find("div", class_="vt242")
                room = room_div.get_text(strip=True) if room_div else ""

                type_div = card.find("div", class_=re.compile(r"vt243\b"))
                ltype = type_div.get_text(strip=True) if type_div else ""

                subgroup = 0
                m_sg = re.search(r"\((\d)\s*(?:п/?г)?\)", subj)
                if m_sg:
                    subgroup = int(m_sg.group(1))

                days_lessons[day_i].append({
                    "num": num,
                    "time": time_str,
                    "subject": subj,
                    "teacher": teacher,
                    "room": room,
                    "type": ltype,
                    "subgroup": subgroup,
                })

    result_days = {}
    for i in range(1, 7):
        result_days[i] = {
            "day_num": i,
            "day_name": days_meta[i]["day_name"],
            "date_str": days_meta[i]["date_str"],
            "lessons": days_lessons[i],
        }

    return {
        "group_id": group_id,
        "week_info": week_info,
        "prev_date": prev_date,
        "next_date": next_date,
        "days": result_days,
    }


async def fetch_schedule(group_id: str, date_str: str | None = None) -> dict[str, Any]:
    global _schedule_cache
    cache_key = f"{group_id}:{date_str or ''}"
    now = time.time()

    if cache_key in _schedule_cache:
        cached_time, cached_data = _schedule_cache[cache_key]
        if now - cached_time < CACHE_TTL:
            return cached_data

    url = f"{BASE_SCHEDULE_URL}?group={group_id}"
    if date_str:
        url += f"&date={date_str}"

    try:
        async with create_client_session() as session:
            async with session.get(url, headers=DEFAULT_HEADERS, timeout=12) as resp:
                if resp.status == 200:
                    html_text = await resp.text()
                    data = parse_schedule_html(html_text, group_id)
                    _schedule_cache[cache_key] = (now, data)
                    return data
                raise RuntimeError(f"HTTP {resp.status} от arcotel.ru")
    except Exception as e:
        if cache_key in _schedule_cache:
            return _schedule_cache[cache_key][1]
        raise e


def filter_lessons(lessons: list[dict[str, Any]], subgroup: int) -> list[dict[str, Any]]:
    if subgroup in (1, 2):
        return [l for l in lessons if l["subgroup"] in (0, subgroup)]
    return lessons


def format_lesson(lesson: dict[str, Any]) -> str:
    num = lesson["num"]
    time_str = lesson["time"]
    subj = lesson["subject"]
    teacher = lesson["teacher"]
    room = lesson["room"]
    ltype = lesson["type"]
    subgroup = lesson["subgroup"]

    type_badge = f" [{ltype}]" if ltype else ""
    sg_badge = f" [п/г {subgroup}]" if subgroup > 0 else ""

    lines = [f"<b>{num}. {time_str}</b> — <b>{subj}</b>{type_badge}{sg_badge}"]
    details = []
    if room:
        details.append(room)
    if teacher:
        details.append(teacher)
    if details:
        lines.append("   " + " | ".join(details))

    return "\n".join(lines)


def format_day_schedule(
    day_data: dict[str, Any],
    group_name: str,
    subgroup: int = 0,
    week_info: str = "",
    profile_label: str = "",
) -> str:
    day_name = day_data["day_name"]
    date_str = day_data["date_str"]
    raw_lessons = day_data["lessons"]
    lessons = filter_lessons(raw_lessons, subgroup)

    sg_text = f" ({subgroup}-я п/г)" if subgroup > 0 else ""
    profile_text = f" [{profile_label}]" if profile_label else ""

    header_lines = [
        f"<b>{day_name}</b> {date_str}{profile_text}",
        f"Группа: <b>{group_name}</b>{sg_text}",
    ]
    if week_info:
        header_lines.append(f"<i>{week_info}</i>")
    header_lines.append("───────────────────────")

    if not lessons:
        header_lines.append("\n<b>Занятий нет — выходной!</b>")
        return "\n".join(header_lines)

    lesson_texts = [format_lesson(l) for l in lessons]
    return "\n".join(header_lines) + "\n\n" + "\n\n".join(lesson_texts)


def format_week_schedule(
    schedule_data: dict[str, Any],
    group_name: str,
    subgroup: int = 0,
    profile_label: str = "",
) -> str:
    sg_text = f" ({subgroup}-я п/г)" if subgroup > 0 else ""
    profile_text = f" [{profile_label}]" if profile_label else ""

    header_lines = [
        f"<b>Расписание на неделю</b>{profile_text}",
        f"Группа: <b>{group_name}</b>{sg_text}",
    ]
    if schedule_data.get("week_info"):
        header_lines.append(f"<i>{schedule_data['week_info']}</i>")
    header_lines.append("═══════════════════════")

    day_blocks = []
    days = schedule_data.get("days", {})

    has_any_lesson = False
    for day_i in range(1, 7):
        day_data = days.get(day_i)
        if not day_data:
            continue
        lessons = filter_lessons(day_data["lessons"], subgroup)
        day_header = f"<b>{day_data['day_name']}</b> ({day_data['date_str']})"

        if not lessons:
            day_blocks.append(f"{day_header}\n<i>— Нет занятий</i>")
        else:
            has_any_lesson = True
            lines = [day_header]
            for l in lessons:
                sg_badge = f" [п/г {l['subgroup']}]" if l["subgroup"] > 0 else ""
                lines.append(f"  • {l['num']} пара ({l['time']}): {l['subject']}{sg_badge} {l['room']}")
            day_blocks.append("\n".join(lines))

    if not has_any_lesson:
        return "\n".join(header_lines) + "\n\n<i>На этой неделе занятий нет!</i>"

    return "\n".join(header_lines) + "\n\n" + "\n\n".join(day_blocks)
