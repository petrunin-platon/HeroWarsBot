# main.py
import json
import time
import mss
import sys
import os
import pygetwindow as gw
import cv2
import numpy as np
import threading
import queue
import builtins 
import ctypes # <-- ИСПОЛЬЗУЕМ CTYPES ВМЕСТО KEYBOARD

# --- ПЕРЕОПРЕДЕЛЕНИЕ PRINT ДЛЯ GUI ---
# Заставляем Python всегда сбрасывать буфер в терминал без задержек
original_print = builtins.print
def unbuffered_print(*args, **kwargs):
    kwargs.setdefault('flush', True)
    original_print(*args, **kwargs)
builtins.print = unbuffered_print
# -------------------------------------

from config import CONFIG, LIMITS, CONFIDENCE_THRESHOLD, ALL_ACTIVE_TITANS
from vision import get_window_rect, find_and_click_bulletproof, get_match_loc
from combat import find_smart_door, execute_angus_ult, execute_rollback
from navigation import check_and_activate_checkpoint, enter_dungeon_room
from team_manager import verify_and_set_team
from analyzer import scan_team_health
from analytics import log_battle
from rules_engine import engine
from stats_manager import add_metric

WINDOW_TITLE = "HeroWarsBot_Arena"
GRACEFUL_STOP = False
GLOBAL_TITAN_STATE = {}
PENDING_RULE = None  

# --- NON-BLOCKING STDIN LISTENER ---
STDIN_QUEUE = queue.Queue()

def stdin_listener():
    """Фоновый поток для чтения команд из GUI без блокировки ОС"""
    for line in sys.stdin:
        STDIN_QUEUE.put(line.strip())

threading.Thread(target=stdin_listener, daemon=True).start()

def wait_for_input():
    """Ожидание ввода с обработкой прерываний"""
    while True:
        try:
            return STDIN_QUEUE.get(timeout=0.2)
        except queue.Empty:
            if GRACEFUL_STOP:
                print("[ТАКТИКА] Экстренная остановка по команде пользователя (Ctrl+Q).")
                sys.exit(0)

def trigger_graceful_stop():
    global GRACEFUL_STOP
    if not GRACEFUL_STOP:
        print("\n[ИНФО] Команда 'Ctrl+Q' принята! Бот завершит бой и остановится.")
        GRACEFUL_STOP = True

def trigger_emergency_stop():
    print("\n[ЭКСТРЕННАЯ ОСТАНОВКА] Принудительное завершение (Ctrl+Shift+Q)!")
    os._exit(0) 

# --- БЕЗОПАСНЫЙ (AV-FRIENDLY) ПЕРЕХВАТЧИК ГОРЯЧИХ КЛАВИШ ---
def background_hotkey_listener():
    """Пассивный поллинг клавиш через ctypes. Не триггерит антивирусы как keylogger."""
    VK_Q = 0x51
    VK_CONTROL = 0x11
    VK_SHIFT = 0x10
    
    while True:
        # Проверяем нажата ли клавиша Q (младший бит игнорируем, проверяем старший)
        if ctypes.windll.user32.GetAsyncKeyState(VK_Q) & 0x8000:
            ctrl_pressed = ctypes.windll.user32.GetAsyncKeyState(VK_CONTROL) & 0x8000
            shift_pressed = ctypes.windll.user32.GetAsyncKeyState(VK_SHIFT) & 0x8000
            
            if ctrl_pressed and shift_pressed:
                trigger_emergency_stop()
                time.sleep(0.5) # Защита от двойного срабатывания
            elif ctrl_pressed:
                trigger_graceful_stop()
                time.sleep(0.5) 
        time.sleep(0.05) # Спим, чтобы не грузить процессор (20 тиков в секунду)

threading.Thread(target=background_hotkey_listener, daemon=True).start()
# -----------------------------------------------------------

def wait_for_focus():
    try:
        active_window = gw.getActiveWindow()
        if active_window is not None and WINDOW_TITLE not in active_window.title:
            print(f"\n[ВНИМАНИЕ] Окно игры перекрыто ({active_window.title[:15]}...). Бот ждет фокуса...")
            while True:
                time.sleep(1.0)
                current = gw.getActiveWindow()
                if current is not None and WINDOW_TITLE in current.title:
                    print("[ИНФО] Окно снова активно. Продолжаем работу.")
                    time.sleep(0.5) # Даем интерфейсу прогрузиться после разворачивания
                    break
    except Exception:
        pass

def force_window_focus():
    import pyautogui # Импортируем прямо здесь для надежности
    try:
        windows = gw.getWindowsWithTitle(WINDOW_TITLE)
        if windows:
            win = windows[0]
            if win.isMinimized:
                win.restore()
            
            # Хак: симуляция нажатия Alt обходит защиту Windows от кражи фокуса
            pyautogui.press('alt') 
            
            try:
                win.activate()
            except Exception as e:
                # Игнорируем знаменитый баг библиотеки pygetwindow (ошибка 0)
                if "Error code from Windows: 0" in str(e):
                    pass
                else:
                    print(f"[ОШИБКА ФОКУСА] {e}")
                    
            time.sleep(0.5)
            print("[ИНФО] Фокус принудительно отправлен окну игры.")
            
            # ЖЕСТКАЯ БЛОКИРОВКА: если фокус так и не переключился (например, мигает в панели задач), 
            # заставляем бота ждать, пока юзер сам не кликнет на окно.
            wait_for_focus()
    except Exception as e:
        print(f"[ОШИБКА ФОКУСА] Общая ошибка: {e}")

STATE = "HALLWAY"
current_room = "unknown"
CURRENT_ENEMIES = []
CURRENT_PACK = [] 
CURRENT_SPECIAL_ULT = "auto"
CURRENT_ALLOWED_DELTA = None

LAST_USED_TEAMS = {"earth": [], "water": [], "fire": [], "mix": []}

SESSION_STATS = {
    "start_time": time.time(),
    "rooms_cleared": 0,
    "titanite_gathered": 0
}

def get_stop_reason():
    if GRACEFUL_STOP:
        return "Ручная остановка пользователем (Ctrl+Q)"
        
    max_time = engine.get_global_setting("target_time", LIMITS["max_time_minutes"])
    max_rooms = engine.get_global_setting("target_rooms", LIMITS["max_rooms"])
    max_floors = engine.get_global_setting("target_floors", LIMITS["max_floors"])
    target_titanite = engine.get_global_setting("target_titanite", LIMITS["target_titanite"])

    elapsed_minutes = (time.time() - SESSION_STATS["start_time"]) / 60
    if max_time > 0 and elapsed_minutes >= max_time:
        return f"Превышен лимит времени ({max_time} мин)"
    if target_titanite > 0 and SESSION_STATS["titanite_gathered"] >= target_titanite:
        return f"Цель по титаниту достигнута ({SESSION_STATS['titanite_gathered']}/{target_titanite})"
    if max_floors > 0:
        floors_done = SESSION_STATS["rooms_cleared"] // 5
        if floors_done >= max_floors and SESSION_STATS["rooms_cleared"] % 5 == 0:
            return f"Пройдено {max_floors} этажей."
    if max_rooms > 0 and SESSION_STATS["rooms_cleared"] >= max_rooms:
        return f"Пройдено {max_rooms} комнат."
    return None

with mss.MSS() as sct:
    while True:
        wait_for_focus() 
        
        game_window = get_window_rect(WINDOW_TITLE)
        if not game_window: 
            time.sleep(0.5)
            continue
        
        if STATE == "WAIT_FOR_OK" and get_match_loc('btn_ok.png', game_window, sct, CONFIDENCE_THRESHOLD):
            active_pack = CURRENT_PACK 
            
            if active_pack:
                print("[ЛОГИКА] Ожидание завершения анимаций (1.5 сек)...")
                time.sleep(1.5)
                
                team_status = scan_team_health(game_window, sct, active_pack)
                
                global_panic = engine.get_global_setting("critical_hp", 40)
                effective_delta = CURRENT_ALLOWED_DELTA if CURRENT_ALLOWED_DELTA is not None else engine.get_global_setting("max_hp_delta", 30)
                
                is_panic = False
                panic_reason = ""
                max_observed_loss = 0
                
                temporary_state = {}

                for titan in active_pack:
                    stats = team_status.get(titan)
                    
                    if not stats:
                        current_hp = 0
                        energy = 0
                    else:
                        current_hp = stats.get("hp", 100)
                        energy = stats.get("energy", 100)

                    before_hp = GLOBAL_TITAN_STATE.get(titan, {}).get("hp", 100)
                    hp_lost = max(0, before_hp - current_hp)
                    
                    if hp_lost > max_observed_loss:
                        max_observed_loss = hp_lost

                    temporary_state[titan] = {
                        "hp": current_hp,
                        "energy": energy 
                    }

                    if current_hp == 0:
                        is_panic = True
                        panic_reason = f"ФАТАЛЬНО! {titan.upper()} мертв (иконка не найдена или ХП=0)!"
                        break
                    elif current_hp < global_panic:
                        is_panic = True
                        panic_reason = f"Критический порог! {titan.upper()} имеет {current_hp}% ХП (порог: {global_panic}%)"
                        break
                    elif hp_lost > effective_delta:
                        is_panic = True
                        panic_reason = f"Превышена Дельта потерь! {titan.upper()} потерял {hp_lost}% ХП (допуск: {effective_delta}%)"
                        break
                
                if not is_panic and not PENDING_RULE:
                    post_battle_state = GLOBAL_TITAN_STATE.copy()
                    post_battle_state.update(temporary_state)
                    
                    rule_team, rule_reason, _, _ = engine.get_battle_decision(current_room, CURRENT_ENEMIES, post_battle_state)
                    
                    if rule_team != active_pack:
                        is_panic = True
                        panic_reason = f"Сработало правило: {rule_reason}"
                        print(f"\n[АЛЕРТ] Движок правил заблокировал результат: {rule_reason}")

                if is_panic:
                    tactic_result = {"action": "rollback", "reason": panic_reason}
                else:
                    tactic_result = {"action": "success", "reason": "Потери в пределах нормы"}
                
                if tactic_result["action"] == "rollback":
                    critical_data = {
                        "titans": {},
                        "is_manual": (CURRENT_SPECIAL_ULT == "angus") 
                    }
                    for t in active_pack:
                        critical_data["titans"][t] = team_status.get(t, {}).get("hp", 0)
                            
                    try:
                        scr = np.array(sct.grab(game_window))
                        cv2.imwrite("temp_sos.png", cv2.cvtColor(scr, cv2.COLOR_BGRA2BGR))
                    except Exception as e:
                        print(f"[СИСТЕМА] Ошибка сохранения скриншота: {e}")
                            
                    print(f"\n[SOS_TRIGGER] {json.dumps(critical_data)}")
                    sys.stdout.flush()
                    
                    print("[ЛОГИКА] Ожидание команды от GUI или Telegram...")
                    decision = wait_for_input() 
                    force_window_focus() 
                    
                    if decision == "MANUAL":
                        print("\n[ТАКТИКА] Включен ручной режим. Бот ОТКЛЮЧАЕТСЯ!")
                        print("[ИНФО] Окно игры свободно. Нажми 'Ещё раз' и переиграй бой руками.")
                        # Жесткий стоп. Гарантирует, что бот НЕ нажмет кнопку "ОК"
                        sys.exit(0)
                        
                    elif decision == "STOP":
                        print("[ТАКТИКА] Экстренная остановка по команде пользователя.")
                        sys.exit(0)
                        
                    elif decision.startswith("ROLLBACK"):
                        new_team = []
                        if ":" in decision:
                            team_str = decision.split(":")[1]
                            new_team = [t.strip() for t in team_str.split(",") if t.strip()]
                            
                            # ЗАЩИТА ОТ ФАНТОМНЫХ ПУСТЫХ ПАКОВ
                            if not new_team:
                                print("\n[ЗАЩИТА] Получен пустой пак. Игнорирую фантомную команду!")
                                continue
                                
                            print(f"\n[ТАКТИКА] Получен тестовый пак: {new_team}")
                            
                            before_battle_hp = {t: GLOBAL_TITAN_STATE.get(t, {}).get("hp", 100) for t in active_pack}
                            
                            PENDING_RULE = {
                                "room": current_room,
                                "enemies": CURRENT_ENEMIES,
                                "team": new_team,
                                "max_observed_loss": max_observed_loss,
                                "before_state": before_battle_hp,
                                "source": "telegram" if decision.startswith("ROLLBACK_TG") else "gui"
                            }
                            
                        log_battle(current_room, CURRENT_ENEMIES, active_pack, "ROLLBACK", tactic_result["reason"], team_status)
                        
                        if execute_rollback(game_window, sct):
                            STATE = "HALLWAY"
                            continue
                        else:
                            print("\n[ВНИМАНИЕ] Ошибка авто-отката! Перейдите в коридор вручную.")
                            with open("pause.flag", "w") as f: 
                                f.write("1")
                            STATE = "HALLWAY"
                            continue
                            
                    elif decision == "IGNORE":
                        print("[ТАКТИКА] Просадка проигнорирована по решению пользователя.")
                        tactic_result["action"] = "success"
                        
                if tactic_result["action"] != "rollback": 
                    if PENDING_RULE:
                        # ДЕЛАЕМ СКРИНШОТ УСПЕШНОГО БОЯ ДЛЯ ТЕЛЕГРАМА
                        try:
                            scr = np.array(sct.grab(game_window))
                            cv2.imwrite("temp_test.png", cv2.cvtColor(scr, cv2.COLOR_BGRA2BGR))
                        except Exception as e:
                            print(f"[СИСТЕМА] Ошибка сохранения скриншота теста: {e}")
                            
                        # ДОБАВЛЯЕМ ИСТОЧНИК В ОТВЕТ
                        success_data = {
                            "titans": team_status,
                            "source": PENDING_RULE.get("source", "gui")
                        }
                        print(f"\n[SOS_TRIGGER] TEST_SUCCESS:{json.dumps(success_data)}")
                        sys.stdout.flush()
                        decision = wait_for_input()
                        force_window_focus()
                        
                        if decision == "CONFIRM":
                            engine.learn_new_rule(
                                PENDING_RULE["room"], 
                                PENDING_RULE["enemies"], 
                                PENDING_RULE["team"],
                                custom_delta=PENDING_RULE.get("max_observed_loss"),
                                before_state=PENDING_RULE.get("before_state")
                            )
                            LAST_USED_TEAMS[current_room] = PENDING_RULE["team"]
                            PENDING_RULE = None
                            
                        elif decision.startswith("ROLLBACK"):
                            new_team = []
                            if ":" in decision:
                                team_str = decision.split(":")[1]
                                new_team = [t.strip() for t in team_str.split(",") if t.strip()]
                                
                                # ЗАЩИТА ОТ ФАНТОМНЫХ ПУСТЫХ ПАКОВ
                                if not new_team:
                                    print("\n[ЗАЩИТА] Получен пустой пак. Игнорирую фантомную команду!")
                                    continue
                                    
                                PENDING_RULE["team"] = new_team 
                                if decision.startswith("ROLLBACK_TG"):
                                    PENDING_RULE["source"] = "telegram"
                            
                            if execute_rollback(game_window, sct):
                                STATE = "HALLWAY"
                                continue
                            else:
                                with open("pause.flag", "w") as f: 
                                    f.write("1")
                                STATE = "HALLWAY"
                                continue
                                
                    if not PENDING_RULE:
                        GLOBAL_TITAN_STATE.update(temporary_state)
                        log_battle(current_room, CURRENT_ENEMIES, active_pack, "SUCCESS", tactic_result.get('reason', 'Одобрено'), team_status)
                        
                        SESSION_STATS["rooms_cleared"] += 1
                        add_metric("rooms", 1, is_bot=True) 
                        
                        if SESSION_STATS["rooms_cleared"] % 5 == 0:
                            add_metric("floors", 1, is_bot=True)
                    
                        if get_match_loc('badge_x2.png', game_window, sct, 0.75):
                            SESSION_STATS["titanite_gathered"] += 12
                            add_metric("titanite", 12, is_bot=True)
                            add_metric("potions", 50, is_bot=True)
                        else:
                            SESSION_STATS["titanite_gathered"] += 6
                            add_metric("titanite", 6, is_bot=True)
                            add_metric("potions", 25, is_bot=True)
                            
                        print(f"[СТАТИСТИКА] Комнат: {SESSION_STATS['rooms_cleared']} | Титанит: {SESSION_STATS['titanite_gathered']}")
                            
                        if CONFIG.get("debug_mode"):
                            print("\n[ПАУЗА ОТЛАДКИ] Бой завершен. Подтвердите продолжение в GUI.")
                            sys.stdout.flush() 
                            wait_for_input()
                            force_window_focus()

            find_and_click_bulletproof('btn_ok.png', game_window, sct, CONFIDENCE_THRESHOLD)
            STATE = "HALLWAY"
            time.sleep(0.5) 
            continue
            
        if STATE == "HALLWAY":
            if os.path.exists("pause.flag"):
                print("\n[МЯГКАЯ ПАУЗА] Бот ждет в коридоре...")
                while os.path.exists("pause.flag"):
                    time.sleep(1)
                LAST_USED_TEAMS = {"earth": [], "water": [], "fire": [], "mix": []}
                print("[ИНФО] Пауза снята. Кэш составов очищен. Возобновление движения.\n")
                
            stop_reason = get_stop_reason()
            if stop_reason:
                print(f"\n🛑 ОСТАНОВКА: {stop_reason}")
                sys.exit(0)
                
            CURRENT_ENEMIES = []
            
            if get_match_loc('btn_attack.png', game_window, sct, CONFIDENCE_THRESHOLD):
                STATE = "ROOM_SELECTION"
                continue
            if enter_dungeon_room(game_window, sct):
                STATE = "ROOM_SELECTION"
                continue
            if check_and_activate_checkpoint(game_window, sct):
                continue 
                
        elif STATE == "ROOM_SELECTION":
            # ИСПРАВЛЕНИЕ: Передаем актуальный GLOBAL_TITAN_STATE в боевой модуль!
            found_room, enemies = find_smart_door(game_window, sct, GLOBAL_TITAN_STATE)
            if found_room:
                current_room = found_room
                CURRENT_ENEMIES = enemies
                STATE = "SET_TEAM"
            continue
            
        elif STATE == "SET_TEAM":
            if get_match_loc('btn_in_battle.png', game_window, sct, CONFIDENCE_THRESHOLD) or get_match_loc('btn_auto.png', game_window, sct, CONFIDENCE_THRESHOLD):
                
                if PENDING_RULE and PENDING_RULE["room"] == current_room:
                    target_pack = PENDING_RULE["team"]
                    reason = "Тестирование нового пака"
                    CURRENT_ALLOWED_DELTA = None
                    CURRENT_SPECIAL_ULT = "angus" if "angus" in target_pack else "auto"
                else:
                    target_pack, reason, CURRENT_ALLOWED_DELTA, CURRENT_SPECIAL_ULT = engine.get_battle_decision(
                        current_room, CURRENT_ENEMIES, GLOBAL_TITAN_STATE
                    )
                
                # =================================================================
                # УМНАЯ ОСТАНОВКА: СВЯЗЬ С GUI (ИНТЕРАКТИВНОЕ СПАСЕНИЕ)
                # =================================================================
                if target_pack == ["STOP"]:
                    print(f"\n[АЛЕРТ] ФАТАЛЬНО: {reason}")
                    
                    # Отправляем SOS-сигнал в GUI со спец-типом NO_VALID_TEAM
                    stop_data = {
                        "type": "NO_VALID_TEAM",
                        "room": current_room,
                        "enemies": CURRENT_ENEMIES,
                        "reason": reason
                    }
                    print(f"\n[SOS_TRIGGER] {json.dumps(stop_data)}")
                    sys.stdout.flush()
                    
                    print("[ЛОГИКА] Ожидание команды от GUI (MANUAL или NEW_PACK)...")
                    decision = wait_for_input()
                    force_window_focus()
                    
                    if decision == "MANUAL":
                        print("[ТАКТИКА] Включен ручной режим. Жду старта боя (кликните 'В бой' в игре)...")
                        with open("pause.flag", "w") as f: 
                            f.write("1")
                        
                        while os.path.exists("pause.flag"):
                            wait_for_focus()
                            # Если бой начался (появилась пауза или отключенный автобой)
                            if get_match_loc('btn_round_auto_off.png', game_window, sct, 0.75) or get_match_loc('btn_round_auto_on.png', game_window, sct, 0.75):
                                print("[ИНФО] Зафиксировано ручное начало боя. Снимаю паузу.")
                                if os.path.exists("pause.flag"):
                                    os.remove("pause.flag")
                                STATE = "WAIT_FOR_OK" # Переходим к ожиданию победы
                                break
                            time.sleep(1)
                        continue 
                        
                    elif decision.startswith("NEW_PACK"):
                        # Парсим новый пак из GUI, например: "NEW_PACK: iyari, sigurd, moloch, hyperion, araji"
                        team_str = decision.split(":")[1]
                        new_team = [t.strip() for t in team_str.split(",") if t.strip()]
                        print(f"\n[ТАКТИКА] Применен экстренный пак от пользователя: {new_team}")
                        
                        # Автоматически сохраняем этот пак в правила
                        engine.learn_new_rule(current_room, CURRENT_ENEMIES, new_team)
                        
                        # Подменяем целевой пак и идем расставлять его!
                        target_pack = new_team
                        CURRENT_SPECIAL_ULT = "angus" if "angus" in target_pack else "auto"
                        
                    elif decision == "STOP":
                        print("[ТАКТИКА] Экстренная остановка по команде пользователя.")
                        sys.exit(0)
                # =================================================================
                
                CURRENT_PACK = target_pack
                print(f"\n[ТАКТИКА] Комната {current_room} | Пак: {target_pack} | Стратегия: {CURRENT_SPECIAL_ULT}")
                
                if not target_pack:
                    print(f"\n[ОШИБКА] Пак не найден в правилах.")
                    sys.exit(0)
                
                if target_pack == LAST_USED_TEAMS.get(current_room):
                    print(f"[ТАКТИКА] Пак {target_pack} уже стоит в комнате {current_room}. Пропускаем сборку!")
                    team_ready = True
                else:
                    team_ready = verify_and_set_team(target_pack, ALL_ACTIVE_TITANS, game_window, sct)
                    if team_ready:
                        LAST_USED_TEAMS[current_room] = target_pack
                
                if not team_ready:
                    print(f"\n[ОШИБКА] Ошибка расстановки титанов.")
                    sys.exit(0)
                
                if CURRENT_SPECIAL_ULT == "angus":
                    STATE = "PREP_SPECIAL_ANGUS"
                else:
                    STATE = "PREP_AUTO"
            continue
            
        elif STATE == "PREP_SPECIAL_ANGUS": 
            if find_and_click_bulletproof('btn_in_battle.png', game_window, sct, CONFIDENCE_THRESHOLD):
                execute_angus_ult(game_window, sct)
                STATE = "WAIT_FOR_OK" 
            continue
            
        elif STATE == "PREP_AUTO":
            if find_and_click_bulletproof('btn_auto.png', game_window, sct, CONFIDENCE_THRESHOLD):
                STATE = "WAIT_FOR_OK"
            continue
            
        time.sleep(0.1)