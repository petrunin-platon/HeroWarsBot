import os

CONFIG = {
    "angus_manual_control": False,  # задача 12: земля автобоем, ручная ульта — переключателем в окне
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

# Файл-флаг для управления мягкой паузой бота
PAUSE_FLAG_FILE = "pause.flag"

# Системный заголовок окна трансляции (scrcpy / эмулятор)
GAME_WINDOW_TITLE = "HeroWarsBot_Arena"

# Версия программы (показывается в окне программы)
APP_VERSION = "1.6.1"

# Репозиторий программы на GitHub («владелец/имя»). Бот переехал в другой репозиторий — поменяйте только эту строку:
# от неё берутся кнопка «GitHub проекта» и «Проверить обновления» (страница релизов) в окне «О программе»
GITHUB_REPO = "petrunin-platon/HeroWarsBot"

# Почта автора: кнопка «Написать автору», строка Email в «О программе» и «Отправить лог автору» на главной
AUTHOR_EMAIL = "petrunin.platon@gmail.com"
