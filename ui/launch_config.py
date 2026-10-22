"""Что показывает карточка «Конфигурация запуска» на главной (задача 15, шаг 3; макет 01_main) — из profile.yml.

Значения — по тем же правилам, что у бота: цель сессии — main.py:get_stop_reason (нет цели по титаниту в профиле —
бот берёт 120 из config.LIMITS), режим, порог паники, сброс дня и таймаут окна SOS — tactics.Settings.
Цель одна (ваш ответ 22.10.2026, сверка 1.5 и 1.7): показывается первая ненулевая в порядке старой вкладки
«Мастер правил» — титанит, комнаты, этажи, время. Полоска «Текущей сессии» идёт по ней же.
Модуль без Tk.
"""
import os

import yaml

import tactics
from config import LIMITS

PROFILE = "profile.yml"
# Вид цели, ключ в профиле, что бот берёт без ключа
GOALS = (
    ("titanite", "target_titanite", LIMITS["target_titanite"]),
    ("rooms", "target_rooms", LIMITS["max_rooms"]),
    ("floors", "target_floors", LIMITS["max_floors"]),
    ("time", "target_time", LIMITS["max_time_minutes"]),
)


def read_profile(path=PROFILE):
    """(есть ли файл, словарь профиля). Битый файл — пустой словарь (бот тоже берёт значения по умолчанию)."""
    if not os.path.exists(path):
        return False, {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return True, {}
    return True, data if isinstance(data, dict) else {}


def _number(value):
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return 0


def launch_config(profile):
    """Цель (вид, число) или None, «бот решает сам», порог паники, час сброса дня, таймаут SOS и настройки тактики
    (у них — личные пороги паники для окна SOS: settings.panic_hp(титан))."""
    get = tactics.profile_getter(profile)
    settings = tactics.Settings(get)
    goal = None
    for kind, key, default in GOALS:
        value = _number(get(key, default))
        if value > 0:
            goal = (kind, value)
            break
    return {
        "goal": goal,
        "auto": settings.auto_rollback,
        "panic": settings.critical_hp,
        "reset_hour": settings.reset_hour,
        "sos_timeout": settings.sos_timeout_minutes,
        "settings": settings,
    }


def goal_progress(goal, rooms, titanite, floors, elapsed_s):
    """(сколько сделано, сколько нужно, доля 0..1) по цели сессии; цели нет — None."""
    if not goal:
        return None
    kind, target = goal
    done = {"titanite": titanite, "rooms": rooms, "floors": floors, "time": elapsed_s / 60}[kind]
    return done, target, max(0.0, min(1.0, done / target))
