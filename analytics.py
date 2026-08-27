# analytics.py
import json
import os
import glob
from datetime import datetime

# 1. Создаем папку для логов, если её нет
if not os.path.exists("logs"):
    os.makedirs("logs")

# 2. РОТАЦИЯ ЛОГОВ (Оставляем не более 20 файлов каждого типа)
def rotate_logs():
    for ext in ["*.jsonl", "*.txt"]:
        files = sorted(glob.glob(f"logs/{ext}"), key=os.path.getmtime, reverse=True)
        for old_file in files[20:]:
            try: os.remove(old_file)
            except: pass

rotate_logs()

# 3. Генерируем уникальное имя файла для текущей сессии
SESSION_ID = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
SESSION_LOG_FILE = f"logs/battle_log_{SESSION_ID}.jsonl"
GUI_LOG_FILE = "logs/battle_log.csv" 

def log_battle(room_type, enemies, pack, action, reason, team_status):
    """Журналирует бой в уникальный файл сессии"""
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "room": room_type,
        "enemies": enemies,
        "team": pack,
        "action": action,
        "reason": reason,
        "hp_status": team_status
    }
    
    with open(SESSION_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
    with open(GUI_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{entry['timestamp']},{room_type},{action},{reason}\n")

print(f"[АНАЛИТИКА] Логи сессии будут сохранены в: {SESSION_LOG_FILE}")