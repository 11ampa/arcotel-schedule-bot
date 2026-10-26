#!/usr/bin/env python3
"""конфигурация telegram-бота расписания акта (ф) спбгут."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# базовый url расписания колледжа
BASE_SCHEDULE_URL = os.getenv(
    "BASE_SCHEDULE_URL",
    "https://www.arcotel.ru/studentam/raspisanie-i-grafiki/raspisanie-zanyatiy-studentov-ochnoy-i-vecherney-form-obucheniya",
)

# опциональный прокси для запросов к сайту (http, https или socks5)
SCHEDULE_PROXY = os.getenv("SCHEDULE_PROXY", "").strip() or None

# московский часовой пояс
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")

# ttl кэширования расписания в секундах (15 минут)
CACHE_TTL = int(os.getenv("CACHE_TTL", "900"))

# пути хранения данных и ассетов
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
SETTINGS_FILE = DATA_DIR / "user_settings.json"
GROUPS_CACHE_FILE = DATA_DIR / "groups_cache.json"

ASSETS_DIR = BASE_DIR / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
