import os

CONFIG = {
    "angus_manual_control": True,
    "debug_mode": False,  
    # Динамически получаем язык из процесса GUI (по умолчанию RU, если переменной нет)
    "game_language": os.environ.get("HEROWARS_LANG", "RU")
}

# Лимиты для остановки бота (если 0 - лимит отключен)
LIMITS = {
    "max_time_minutes": 0,      # Остановиться через X минут
    "max_rooms": 0,             # Количество комнат (0 = бесконечно)
    "max_floors": 0,            # Количество этажей (0 = бесконечно)
    "target_titanite": 120      # Остановиться, собрав X титанита
}

# Все твои доступные титаны (для сборки паков)
ALL_ACTIVE_TITANS = [
    "angus", "avalon", "eden", "silva", "verdok",
    "hyperion", "sigurd", "tidus", "nova", "mairi", "orm", "pallant",
    "araji", "ignis", "acheron", "vulcan", "moloch",
    "rigel", "iyari", "lumira"
]

# Идеально точный список из 13 возможных врагов в Подземелье
ENEMY_TITANS = [
    "angus", "avalon", "eden", "silva", "verdok",  # Земля (без Палланта)
    "hyperion", "sigurd", "nova", "mairi",         # Вода (без Тидуса и Орма)
    "araji", "ignis", "vulcan", "moloch"           # Огонь (без Ашерона и Алекто)
]

CONFIDENCE_THRESHOLD = 0.8
WINDOW_TITLE = "HeroWarsBot_Arena"