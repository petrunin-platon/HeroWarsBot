# stats_manager.py
import json
import os
import yaml
from datetime import datetime, timedelta

STATS_FILE = "stats.json"
PROFILE_FILE = "profile.yml"

def get_reset_shift():
    """Читает из профиля час сброса дня по местному времени (по умолчанию 5 утра)."""
    shift = 5
    if os.path.exists(PROFILE_FILE):
        try:
            with open(PROFILE_FILE, 'r', encoding='utf-8') as f:
                profile = yaml.safe_load(f) or {}
                shift = int(profile.get("settings", {}).get("reset_hour", 5))
        except Exception:
            pass
    return shift

def get_game_datetime():
    """Возвращает объект datetime со сдвигом игрового времени."""
    return datetime.now() - timedelta(hours=get_reset_shift())

def get_game_date():
    """Возвращает строковую игровую дату."""
    return get_game_datetime().strftime("%Y-%m-%d")

def load_stats():
    """Загружает статистику из файла или создает пустую структуру."""
    if not os.path.exists(STATS_FILE):
        return {
            "total_titanite": 0, 
            "total_rooms": 0, 
            "total_floors": 0, 
            "total_potions": 0,
            "daily": {}
        }
    try:
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if "total_potions" not in data:
                data["total_potions"] = 0
            return data
    except:
        return {"total_titanite": 0, "total_rooms": 0, "total_floors": 0, "total_potions": 0, "daily": {}}

def save_stats(stats):
    """Сохраняет структуру в файл."""
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=4, ensure_ascii=False)

def add_metric(metric, amount=1, date_str=None, is_bot=False):
    """Добавляет значение к глобальному и дневному счетчику."""
    stats = load_stats()
    
    if not date_str:
        date_str = get_game_date()

    # Глобальные счетчики
    global_key = f"total_{metric}"
    if global_key in stats:
        stats[global_key] += amount
    elif global_key == "total_potions": 
        stats[global_key] = amount

    # Дневные счетчики
    if date_str not in stats["daily"]:
        stats["daily"][date_str] = {"titanite": 0, "rooms": 0, "floors": 0, "potions": 0}

    if metric in stats["daily"][date_str]:
        stats["daily"][date_str][metric] += amount
    else:
        stats["daily"][date_str][metric] = amount

    # Неизменяемый базис бота (защита от неверного ручного ввода)
    if is_bot:
        bot_key = f"bot_{metric}"
        if bot_key in stats["daily"][date_str]:
            stats["daily"][date_str][bot_key] += amount
        else:
            stats["daily"][date_str][bot_key] = amount

    save_stats(stats)

def reset_stats():
    """Полностью обнуляет базу данных статистики."""
    empty_stats = {
        "total_titanite": 0, 
        "total_rooms": 0, 
        "total_floors": 0, 
        "total_potions": 0,
        "daily": {}
    }
    save_stats(empty_stats)