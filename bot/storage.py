#!/usr/bin/env python3
"""хранилище динамических профилей и настроек пользователей."""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from bot.config import SETTINGS_FILE

_lock = asyncio.Lock()
_cache: dict[str, Any] = {}
_loaded = False


def _get_default_user_data() -> dict[str, Any]:
    return {
        "profiles": [],
        "active_profile_id": None,
        "selected_day_idx": None,
        "view_mode": "today",  # today, tomorrow, week, day
        "week_offset": 0,
        "profiles_page": 0,
        "wizard": None,  # временное состояние пошаговой настройки
    }


def _load_settings_sync() -> dict[str, Any]:
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_settings_sync(data: dict[str, Any]) -> None:
    SETTINGS_FILE.parent.mkdir(exist_ok=True)
    temp_file = SETTINGS_FILE.with_suffix(".tmp")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    temp_file.replace(SETTINGS_FILE)


async def get_user_settings(user_id: int | str) -> dict[str, Any]:
    global _cache, _loaded
    async with _lock:
        if not _loaded:
            _cache = _load_settings_sync()
            _loaded = True
        uid = str(user_id)
        if uid not in _cache:
            _cache[uid] = _get_default_user_data()
            _save_settings_sync(_cache)
        return _cache[uid]


async def update_user_settings(user_id: int | str, **kwargs: Any) -> dict[str, Any]:
    global _cache, _loaded
    async with _lock:
        if not _loaded:
            _cache = _load_settings_sync()
            _loaded = True
        uid = str(user_id)
        if uid not in _cache:
            _cache[uid] = _get_default_user_data()

        for k, v in kwargs.items():
            _cache[uid][k] = v

        _save_settings_sync(_cache)
        return _cache[uid]


async def add_user_profile(
    user_id: int | str,
    name: str,
    group_id: str,
    group_name: str,
    subgroup: int = 0,
) -> dict[str, Any]:
    global _cache, _loaded
    async with _lock:
        if not _loaded:
            _cache = _load_settings_sync()
            _loaded = True
        uid = str(user_id)
        if uid not in _cache:
            _cache[uid] = _get_default_user_data()

        pid = f"p_{uuid.uuid4().hex[:8]}"
        new_profile = {
            "id": pid,
            "name": name.strip() or "Мой профиль",
            "group_id": str(group_id),
            "group_name": str(group_name),
            "subgroup": int(subgroup),
        }
        _cache[uid].setdefault("profiles", []).append(new_profile)
        if not _cache[uid].get("active_profile_id"):
            _cache[uid]["active_profile_id"] = pid

        _save_settings_sync(_cache)
        return new_profile


async def get_active_profile(user_id: int | str) -> dict[str, Any] | None:
    data = await get_user_settings(user_id)
    profiles = data.get("profiles", [])
    active_id = data.get("active_profile_id")
    for p in profiles:
        if p["id"] == active_id:
            return p
    return profiles[0] if profiles else None


async def set_active_profile(user_id: int | str, profile_id: str) -> bool:
    global _cache, _loaded
    async with _lock:
        if not _loaded:
            _cache = _load_settings_sync()
            _loaded = True
        uid = str(user_id)
        if uid in _cache:
            _cache[uid]["active_profile_id"] = profile_id
            _save_settings_sync(_cache)
            return True
    return False


async def update_user_profile(user_id: int | str, profile_id: str, **kwargs: Any) -> bool:
    global _cache, _loaded
    async with _lock:
        if not _loaded:
            _cache = _load_settings_sync()
            _loaded = True
        uid = str(user_id)
        if uid in _cache:
            for p in _cache[uid].get("profiles", []):
                if p["id"] == profile_id:
                    p.update(kwargs)
                    _save_settings_sync(_cache)
                    return True
    return False


async def delete_user_profile(user_id: int | str, profile_id: str) -> bool:
    global _cache, _loaded
    async with _lock:
        if not _loaded:
            _cache = _load_settings_sync()
            _loaded = True
        uid = str(user_id)
        if uid in _cache:
            profiles = _cache[uid].get("profiles", [])
            _cache[uid]["profiles"] = [p for p in profiles if p["id"] != profile_id]
            if _cache[uid].get("active_profile_id") == profile_id:
                _cache[uid]["active_profile_id"] = (
                    _cache[uid]["profiles"][0]["id"] if _cache[uid]["profiles"] else None
                )
            _save_settings_sync(_cache)
            return True
    return False
