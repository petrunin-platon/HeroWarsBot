# stats_manager.py
import json
import os
import yaml
import time  # <-- Добавлен импорт time для задержек retry
from datetime import datetime, timedelta

STATS_FILE = "stats.json"
PROFILE_FILE = "profile.yml"

# Кэш для хранения сдвига времени (читаем диск 1 раз)
_RESET_SHIFT_CACHE = None

def get_reset_shift():
    """Читает из профиля час сброса дня по местному времени с использованием кэширования."""
    global _RESET_SHIFT_CACHE
    if _RESET_SHIFT_CACHE is not None:
        return _RESET_SHIFT_CACHE

    shift = 5
    if os.path.exists(PROFILE_FILE):
        try:
            with open(PROFILE_FILE, 'r', encoding='utf-8') as f:
                profile = yaml.safe_load(f) or {}
                shift = int(profile.get("settings", {}).get("reset_hour", 5))
        except Exception:
            pass
            
    _RESET_SHIFT_CACHE = shift
    return shift

def get_game_datetime():
    """Возвращает объект datetime со сдвигом игрового времени."""
    return datetime.now() - timedelta(hours=get_reset_shift())

def get_game_date():
    """Возвращает строковую игровую дату."""
    return get_game_datetime().strftime("%Y-%m-%d")

# --- НАЧАЛО ЗАМЕНЫ ---
def load_stats():
    """Загружает статистику из файла с защитой от блокировок диска и повреждения JSON."""
    empty_stats = {
        "total_titanite": 0, 
        "total_rooms": 0, 
        "total_floors": 0, 
        "total_potions": 0,
        "daily": {}
    }
    
    if not os.path.exists(STATS_FILE):
        return empty_stats.copy()

    max_retries = 5
    retry_delay = 0.5  # Пауза в полсекунды между попытками

    for attempt in range(max_retries):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "total_potions" not in data:
                    data["total_potions"] = 0
                return data
                
        except json.JSONDecodeError as e:
            # Файл прочитался, но внутри мусор или пустота. Возвращаем нули.
            print(f"[СТАТИСТИКА] ВНИМАНИЕ: Файл stats.json поврежден. Начинаем новую статистику. ({e})")
            return empty_stats.copy()
            
        except OSError as e:
            # Файл заблокирован антивирусом, OneDrive или другой программой
            if attempt < max_retries - 1:
                print(f"[СТАТИСТИКА] Доступ к stats.json заблокирован. Попытка {attempt + 1}/{max_retries} через {retry_delay} сек...")
                time.sleep(retry_delay)
            else:
                print(f"[СТАТИСТИКА] КРИТИЧЕСКАЯ ОШИБКА: Не удалось получить доступ к stats.json после {max_retries} попыток! Защита от потери данных.")
                raise  # Пробрасываем ошибку выше, чтобы принудительно остановить бота и спасти файл
# --- КОНЕЦ ЗАМЕНЫ ---

def save_stats(stats):
    """Сохраняет структуру во временный файл, затем атомарно перезаписывает основной."""
    temp_file = f"{STATS_FILE}.tmp"
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=4, ensure_ascii=False)
    
    # Атомарная подмена файла (гарантирует защиту от Race Condition и обрывов питания)
    os.replace(temp_file, STATS_FILE)

def add_metric(metric, amount=1, date_str=None, is_bot=False):
    """(СТАРАЯ ВЕРСИЯ) Добавляет одиночное значение к счетчикам. Оставлена для обратной совместимости."""
    add_metrics_bulk({metric: amount}, date_str=date_str, is_bot=is_bot)

def add_metrics_bulk(metrics_dict, date_str=None, is_bot=False):
    """
    Пакетное добавление метрик. Сводит чтение/запись файла к одной транзакции.
    Принимает словарь, например: {"rooms": 1, "titanite": 12, "potions": 50}
    """
    if not metrics_dict:
        return

    stats = load_stats()
    
    if not date_str:
        date_str = get_game_date()

    if date_str not in stats["daily"]:
        stats["daily"][date_str] = {"titanite": 0, "rooms": 0, "floors": 0, "potions": 0}

    for metric, amount in metrics_dict.items():
        # Глобальные счетчики
        global_key = f"total_{metric}"
        if global_key in stats:
            stats[global_key] += amount
        elif global_key == "total_potions": 
            stats[global_key] = amount
        elif metric == "potions": # Защита, если ключа total_potions не было в старых базах
            stats["total_potions"] = amount

        # Дневные счетчики
        if metric in stats["daily"][date_str]:
            stats["daily"][date_str][metric] += amount
        else:
            stats["daily"][date_str][metric] = amount

        # Неизменяемый базис бота
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