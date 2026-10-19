# data_paths.py
# Все пути к файлам, которые бот и окно программы пишут сами. Всё лежит в bot_data/ (папка в .gitignore),
# поэтому обновления с GitHub не мешают вашим данным.
#   bot_data/stats.json          статистика
#   bot_data/rules/*.yml         рабочие правила (rules/ в репозитории — правила по умолчанию)
#   bot_data/logs/              история боёв (battle_log_*.jsonl, battle_log.csv), лог бота, замеры
#   bot_data/debug/             скриншоты окон SOS (sos_комнатаN_стихия_время.png) и нечитаемых окон результата
#   bot_data/profile.yml.bak     копия профиля
#   bot_data/temp_sos.png, bot_data/temp_test.png   скриншоты для Telegram
# Пути относительные: бот и окно программы всегда запускаются из папки проекта.
# При импорте модуль ничего не делает. Старые файлы копируются при первом обращении к любому пути.
import glob
import os
import shutil

BOT_DATA_DIR = "bot_data"
LOGS_DIR = f"{BOT_DATA_DIR}/logs"
RULES_DIR = f"{BOT_DATA_DIR}/rules"
DEBUG_DIR = f"{BOT_DATA_DIR}/debug"
DEFAULT_RULES_DIR = "rules"
STATS_FILE = f"{BOT_DATA_DIR}/stats.json"
PROFILE_BACKUP = f"{BOT_DATA_DIR}/profile.yml.bak"
TEMP_SOS_FILE = f"{BOT_DATA_DIR}/temp_sos.png"
TEMP_TEST_FILE = f"{BOT_DATA_DIR}/temp_test.png"

ROOM_TYPES = ("earth", "water", "fire", "mix")

# Старые места файлов (до переезда в bot_data/)
LEGACY_STATS = "stats.json"
LEGACY_PROFILE_BACKUP = "profile.yml.bak"
LEGACY_LOGS_DIR = "logs"

# Файл-метка: история боёв из logs/ уже копировалась. Нужен, чтобы ротация не удаляла копии, а они не возвращались.
HISTORY_MARK = f"{BOT_DATA_DIR}/.history_copied"

# Для каждой папки bot_data один раз за запуск процесса
_CHECKED = set()


def _copy_if_missing(src, dst):
    """Копирует файл, только если src есть, а dst ещё нет. Исходный файл не трогает. True, если скопировал."""
    if not os.path.isfile(src) or os.path.exists(dst):
        return False
    folder = os.path.dirname(dst)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp = f"{dst}.copy_tmp"
    shutil.copy2(src, tmp)
    # Если за это время файл уже создал другой процесс (бот и окно запускаются почти вместе), его не перезаписываем
    if os.path.exists(dst):
        os.remove(tmp)
        return False
    os.replace(tmp, dst)
    return True


def _copy_legacy_history():
    """История боёв из logs/ (battle_log_*.jsonl, battle_log.csv) → bot_data/logs/. Один раз."""
    if os.path.exists(HISTORY_MARK):
        return []
    sources = sorted(glob.glob(f"{LEGACY_LOGS_DIR}/battle_log_*.jsonl")) + [f"{LEGACY_LOGS_DIR}/battle_log.csv"]
    copied = [src for src in sources if _copy_if_missing(src, f"{LOGS_DIR}/{os.path.basename(src)}")]
    os.makedirs(BOT_DATA_DIR, exist_ok=True)
    with open(HISTORY_MARK, "w", encoding="utf-8") as f:
        f.write("1")
    return copied


def ensure_bot_data():
    """Создаёт bot_data/ и один раз копирует туда старые файлы. Ничего не удаляет и не перезаписывает.
    Безопасно вызывать сколько угодно раз: за запуск процесса работает один раз."""
    key = os.path.abspath(BOT_DATA_DIR)
    if key in _CHECKED:
        return
    _CHECKED.add(key)

    for folder in (BOT_DATA_DIR, LOGS_DIR, RULES_DIR):
        os.makedirs(folder, exist_ok=True)

    copied = []
    if _copy_if_missing(LEGACY_STATS, STATS_FILE):
        copied.append(LEGACY_STATS)
    if _copy_if_missing(LEGACY_PROFILE_BACKUP, PROFILE_BACKUP):
        copied.append(LEGACY_PROFILE_BACKUP)
    for room in ROOM_TYPES:
        if _copy_if_missing(f"{DEFAULT_RULES_DIR}/{room}.yml", f"{RULES_DIR}/{room}.yml"):
            copied.append(f"{DEFAULT_RULES_DIR}/{room}.yml")
    copied += _copy_legacy_history()

    if copied:
        print(f"[ДАННЫЕ] Первый запуск после обновления: скопировано в {BOT_DATA_DIR}/ файлов: {len(copied)} "
              f"({', '.join(copied)}). Старые файлы остались на месте.")


# --- пути для остальных модулей: сначала проверяют bot_data/, потом отдают путь ---
def stats_file():
    ensure_bot_data()
    return STATS_FILE


def rules_path(room_type):
    """Рабочий файл правил стихии: bot_data/rules/<стихия>.yml."""
    ensure_bot_data()
    return f"{RULES_DIR}/{room_type}.yml"


def logs_dir():
    ensure_bot_data()
    return LOGS_DIR


def debug_dir():
    """Скриншоты для разбора: окна SOS и нечитаемые окна результата. Папку создаёт этот вызов."""
    ensure_bot_data()
    os.makedirs(DEBUG_DIR, exist_ok=True)
    return DEBUG_DIR


def profile_backup_file():
    ensure_bot_data()
    return PROFILE_BACKUP


def temp_sos_file():
    ensure_bot_data()
    return TEMP_SOS_FILE


def temp_test_file():
    ensure_bot_data()
    return TEMP_TEST_FILE
