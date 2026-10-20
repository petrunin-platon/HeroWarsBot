# analytics.py
import json
import os
import glob
from datetime import datetime
import data_paths

# 1. История боёв лежит в bot_data/logs/ (создаём папку и один раз копируем туда старые файлы из logs/)
LOG_DIR = data_paths.logs_dir()

# 2. РОТАЦИЯ ЛОГОВ (Оставляем не более 20 файлов каждого типа). Только в bot_data/logs/, ваша папка logs/ не трогается
def rotate_logs():
    for ext in ["*.jsonl", "*.txt"]:
        files = sorted(glob.glob(f"{LOG_DIR}/{ext}"), key=os.path.getmtime, reverse=True)
        for old_file in files[20:]:
            try: 
                os.remove(old_file)
            except Exception as e: 
                print(f"[АНАЛИТИКА] Ошибка при удалении старого лога '{old_file}': {e}")

rotate_logs()

# 3. Генерируем уникальное имя файла для текущей сессии
SESSION_ID = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
SESSION_LOG_FILE = f"{LOG_DIR}/battle_log_{SESSION_ID}.jsonl"
GUI_LOG_FILE = f"{LOG_DIR}/battle_log.csv" 

def log_battle(room_type, enemies, pack, action, reason, team_status, hp_before=None, energy_before=None, heal_for=None):
    """Журналирует бой в уникальный файл сессии. Возвращает запись (для истории боёв в tactics.py).
    hp_before — {титан: ХП до боя} (задача 9б): по нему видно, виноваты враги или титан вошёл в бой раненым.
    energy_before — {титан: энергия до боя} (задача 9в): по ней прогноз потерь берётся из боёв с похожей энергией.
    heal_for — кого лечил пак отхила, который бот собрал сам (задача 9в): такой пак не становится «золотым правилом»."""
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "room": room_type,
        "enemies": enemies,
        "team": pack,
        "action": action,
        "reason": reason,
        "hp_status": team_status
    }
    if hp_before is not None:
        entry["hp_before"] = hp_before
    if energy_before is not None:
        entry["energy_before"] = energy_before
    if heal_for:
        entry["heal_for"] = heal_for
    
    with open(SESSION_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
    with open(GUI_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{entry['timestamp']},{room_type},{action},{reason}\n")

    return entry

print(f"[АНАЛИТИКА] Логи сессии будут сохранены в: {SESSION_LOG_FILE}")