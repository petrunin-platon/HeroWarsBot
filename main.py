# main.py
import json
from datetime import datetime
import time
import mss
import sys
import os
import pygetwindow as gw
import cv2
import numpy as np
import threading
import queue
import atexit
import ctypes # <-- ИСПОЛЬЗУЕМ CTYPES ВМЕСТО KEYBOARD

# --- ПЕРЕОПРЕДЕЛЕНИЕ PRINT ДЛЯ GUI ---
# Время в начале каждой строки, сброс буфера без задержек и копия всего лога в bot_data/logs/.
# Включаем до остальных импортов, чтобы их строки тоже попали в лог.
import session_log
session_log.install()
SESSION_LOG = session_log.SESSION
ROOM_TIMER = SESSION_LOG.timer
# -------------------------------------

from config import CONFIG, LIMITS, CONFIDENCE_THRESHOLD, ALL_ACTIVE_TITANS
from vision import get_window_rect, find_and_click_bulletproof, get_match_loc, wait_for_ui_element, get_first_match
from combat import find_smart_door, execute_angus_ult, execute_rollback
from navigation import smart_navigate_hallway
from click_logic import after_failed_battle_start, START_BATTLE_ATTEMPTS
import rollback_logic
from telegram_agent import send_alert
from i18n import get_text
from team_manager import verify_and_set_team
from analyzer import scan_team_health
from analytics import log_battle
from battle_verdict import evaluate_battle
from rules_engine import engine
from stats_manager import add_metric, add_metrics_bulk
import data_paths
import result_scan
import stuck_guard

WINDOW_TITLE = "HeroWarsBot_Arena"
GRACEFUL_STOP = False
GLOBAL_TITAN_STATE = {}
PENDING_RULE = None  

# Защита от зависаний (stuck_guard.py): сторож «давно нет пройденных комнат» и пределы ожидания по состояниям
WATCHDOG = stuck_guard.Watchdog()
STATE_CLOCK = stuck_guard.StateClock()

def user_waited():
    """Бот ждал вас (окно SOS, пауза, ручной бой, окно не в фокусе): это время сторож и пределы не считают."""
    WATCHDOG.waited_for_user()
    STATE_CLOCK.reset()

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
            decision = STDIN_QUEUE.get(timeout=0.2)
            user_waited()
            return decision
        except queue.Empty:
            if GRACEFUL_STOP:
                print("[ТАКТИКА] Экстренная остановка по команде пользователя (Ctrl+Q).")
                SESSION_LOG.set_stop_reason("Ручная остановка пользователем (Ctrl+Q)")
                sys.exit(0)

def trigger_graceful_stop():
    global GRACEFUL_STOP
    if not GRACEFUL_STOP:
        print("\n[ИНФО] Команда 'Ctrl+Q' принята! Бот завершит бой и остановится.")
        GRACEFUL_STOP = True

def print_session_summary():
    """Блок [ИТОГ]. Печатается один раз при любой остановке."""
    SESSION_LOG.print_summary(SESSION_STATS["rooms_cleared"], SESSION_STATS["titanite_gathered"])

def alert_on_crash():
    """Бот упал с ошибкой Python: ошибку и итог уже напечатали, сообщаем ещё и в Telegram."""
    reason = SESSION_LOG.stop_reason or ""
    if not reason.startswith("Ошибка"):
        return
    try:
        text = (f"⛔ Бот остановился из-за ошибки\n{reason}\n"
                f"Пройдено комнат: {SESSION_STATS['rooms_cleared']}. Подробности — в логе бота.")
        sent, note = send_alert(text)
        print(f"[ОШИБКА] Сообщение в Telegram: {note}")
    except Exception:
        pass

def trigger_emergency_stop():
    print("\n[ЭКСТРЕННАЯ ОСТАНОВКА] Принудительное завершение (Ctrl+Shift+Q)!")
    SESSION_LOG.set_stop_reason("Экстренная остановка пользователем (Ctrl+Shift+Q)")
    try:
        print_session_summary()  # os._exit не запускает atexit, поэтому итог печатаем здесь
    except Exception:
        pass
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
            user_waited()  # пока окно было перекрыто, сторож не считает
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
START_FAILS = 0  # сколько раз подряд не удалось начать бой («Авто» не сработала)

LAST_USED_TEAMS = {"earth": [], "water": [], "fire": [], "mix": []}

SESSION_STATS = {
    "start_time": time.time(),
    "rooms_cleared": 0,
    "titanite_gathered": 0
}

# Итог сессии при любой остановке: лимит, Ctrl+Q, STOP, ошибка Python.
# atexit вызывает функции в обратном порядке: сначала итог, потом сообщение об ошибке в Telegram
atexit.register(alert_on_crash)
atexit.register(print_session_summary)

def save_debug_shot(kind, game_window, sct):
    """Скриншот окна игры в bot_data/debug/: <kind>_комната<N>_<стихия>_<время>.png. Ошибка сохранения бота не останавливает."""
    try:
        name = result_scan.debug_shot_name(kind, SESSION_STATS["rooms_cleared"] + 1, current_room, datetime.now())
        path = os.path.join(data_paths.debug_dir(), name)
        scr = np.array(sct.grab(game_window))
        cv2.imwrite(path, cv2.cvtColor(scr, cv2.COLOR_BGRA2BGR))
        print(f"[ОТЛАДКА] Скриншот сохранён: {path}")
        return path
    except Exception as e:
        print(f"[ОТЛАДКА] Не удалось сохранить скриншот: {e}")
        return None


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

ROOM_NAMES_RU = {"water": "вода", "mix": "смешанная", "earth": "земля", "fire": "огонь"}

def handle_rollback_failure(result, game_window, sct):
    """Откат не удался: пишем причину, шлём в Telegram текст и скриншот, ставим мягкую паузу.
    Окно «Требуется вмешательство» не трогаем (оно в ui/), поэтому сообщаем через Telegram и лог."""
    print(f"\n[ОТКАТ] ОШИБКА ({result.code}): {result.text}")
    if result.code == rollback_logic.SOFT_PAUSE:
        return  # мягкую паузу включил сам пользователь, сообщать не нужно

    screenshot = None
    try:
        scr = np.array(sct.grab(game_window))
        screenshot = data_paths.temp_sos_file()
        cv2.imwrite(screenshot, cv2.cvtColor(scr, cv2.COLOR_BGRA2BGR))
    except Exception as e:
        print(f"[СИСТЕМА] Ошибка сохранения скриншота: {e}")

    lines = ["⚠️ Откат боя не удался", result.text]
    if result.code == rollback_logic.BATTLE_ENDED:
        lines.append("Окно результата осталось на экране: посмотрите, кто выжил. После снятия паузы бот нажмёт «ОК».")
    else:
        lines.append("Посмотрите, что на экране телефона, и верните бота в коридор.")
    lines.append("Бот на мягкой паузе.")
    if current_room in ROOM_NAMES_RU:
        lines.append(f"Комната: {ROOM_NAMES_RU[current_room]}")
    if CURRENT_ENEMIES:
        lines.append("Враги: " + ", ".join(get_text("RU", f"titan_{e}") for e in CURRENT_ENEMIES))
    sent, note = send_alert("\n".join(lines), screenshot)
    print(f"[ОТКАТ] Сообщение в Telegram: {note}")

    with open("pause.flag", "w") as f:
        f.write("1")
    print("[ВНИМАНИЕ] Бот на мягкой паузе. Исправьте ситуацию в игре и снимите паузу в окне программы.")

def run_rollback(game_window, sct, press_retry=True):
    """Откат боя. True — бот в коридоре. Иначе пользователь уже оповещён и включена мягкая пауза."""
    result = execute_rollback(game_window, sct, press_retry=press_retry)
    if result.ok:
        return True
    handle_rollback_failure(result, game_window, sct)
    return False

def count_cleared_room(x2):
    """Комната пройдена: статистика сессии и дня, строка [СТАТИСТИКА]. Возвращает номер комнаты."""
    SESSION_STATS["rooms_cleared"] += 1
    WATCHDOG.progress()

    bulk_updates = {"rooms": 1}

    if SESSION_STATS["rooms_cleared"] % 5 == 0:
        bulk_updates["floors"] = 1

    if x2:
        SESSION_STATS["titanite_gathered"] += 12
        bulk_updates["titanite"] = 12
        bulk_updates["potions"] = 50
    else:
        SESSION_STATS["titanite_gathered"] += 6
        bulk_updates["titanite"] = 6
        bulk_updates["potions"] = 25

    # Пакетная отправка: одно чтение и одна запись на весь бой
    add_metrics_bulk(bulk_updates, is_bot=True)

    print(f"[СТАТИСТИКА] Комнат: {SESSION_STATS['rooms_cleared']} | Титанит: {SESSION_STATS['titanite_gathered']}")
    return SESSION_STATS["rooms_cleared"]

STATE_NAMES_RU = {
    "SET_TEAM": "экран выбора команды не появился",
    "WAIT_FOR_OK": "бой не закончился (нет окна результата)",
}

def report_state_timeout(state, limit, game_window, sct):
    """Бот слишком долго в одном состоянии: скриншот для разбора и строка в логе. Дальше — умный старт."""
    what = STATE_NAMES_RU.get(state, state)
    print(f"\n[СТОРОЖ] Зависание: {what} за {limit:.0f} с (состояние {STATE}). Запускаю умный старт.")
    SESSION_LOG.count("stuck")
    save_debug_shot("stuck", game_window, sct)

def raise_watchdog_alarm(game_window, sct):
    """Давно не пройдено ни одной комнаты: скриншот, строка в логе, сообщение в Telegram.
    Возвращает True, если пора на мягкую паузу (тревог подряд слишком много)."""
    minutes = WATCHDOG.limit / 60
    pause = WATCHDOG.should_pause()
    text = f"Бот {minutes:.0f} мин не прошёл ни одной комнаты (состояние {STATE})."
    print(f"\n[СТОРОЖ] {text} Тревога {WATCHDOG.alarms} из {WATCHDOG.alarms_before_pause}.")
    SESSION_LOG.count("stuck")
    screenshot = save_debug_shot("stuck", game_window, sct)

    lines = ["⚠️ Бот, похоже, завис", text]
    if pause:
        lines.append("Умный старт не помог. Бот на мягкой паузе: посмотрите, что на экране телефона, "
                     "верните игру в коридор подземелья и снимите паузу в окне программы.")
    else:
        lines.append("Пробую умный старт.")
    if current_room in ROOM_NAMES_RU:
        lines.append(f"Последняя комната: {ROOM_NAMES_RU[current_room]}")
    lines.append(f"Пройдено комнат: {SESSION_STATS['rooms_cleared']}")
    sent, note = send_alert("\n".join(lines), screenshot)
    print(f"[СТОРОЖ] Сообщение в Telegram: {note}")

    if pause:
        with open("pause.flag", "w") as f:
            f.write("1")
        print("[ВНИМАНИЕ] Бот на мягкой паузе. Исправьте ситуацию в игре и снимите паузу в окне программы.")
    return pause

# Что видно на экране, пока вы проходите комнату руками (в порядке важности)
MANUAL_SCREENS = [
    (stuck_guard.RESULT, ['btn_ok.png'], CONFIDENCE_THRESHOLD),
    (stuck_guard.BATTLE, ['btn_pause.png', 'btn_round_auto_off.png', 'btn_round_auto_on.png'], 0.75),
    (stuck_guard.TEAM, ['btn_auto.png', 'btn_in_battle.png'], CONFIDENCE_THRESHOLD),
    (stuck_guard.HALLWAY, ['flag_enter.png', 'btn_activate.png'], CONFIDENCE_THRESHOLD),
    (stuck_guard.HALLWAY, ['btn_attack.png'], 0.68),
]

def play_manually(game_window, sct, first_screen):
    """«Пройти руками»: бот ничего не нажимает и ждёт, пока вы вернётесь в коридор. Возвращает ManualPlay."""
    play = stuck_guard.ManualPlay(first_screen=first_screen)
    with ROOM_TIMER.excluded("sos_wait"):  # пока вы играете, время в замеры не идёт
        while True:
            if GRACEFUL_STOP:
                print("[ТАКТИКА] Остановка по команде пользователя (Ctrl+Q) во время ручного прохождения.")
                SESSION_LOG.set_stop_reason("Ручная остановка пользователем (Ctrl+Q)")
                sys.exit(0)
            wait_for_focus()
            found = get_first_match(MANUAL_SCREENS, game_window, sct)
            if play.observe(found[0] if found else None):
                break
            time.sleep(0.5)
    user_waited()
    return play

def handle_failed_start(button, game_window, sct):
    """Бой не начался после нажатия «Авто» или «В бой». Возвращает следующее состояние."""
    global START_FAILS
    team_screen = bool(get_match_loc('btn_auto.png', game_window, sct, CONFIDENCE_THRESHOLD) or
                       get_match_loc('btn_in_battle.png', game_window, sct, CONFIDENCE_THRESHOLD))
    state, START_FAILS = after_failed_battle_start(team_screen, START_FAILS)
    if state == "SET_TEAM":
        print(f"[СЕТЬ] Бой не начался, экран выбора команды всё ещё открыт. Пробую ещё раз ({START_FAILS} из {START_BATTLE_ATTEMPTS - 1})...")
    elif state == "STOP":
        print(f"\n[ОШИБКА] Бой не удалось начать {START_FAILS} раза подряд: кнопка «{button}» не срабатывает.")
        SESSION_LOG.set_stop_reason(f"Не удалось начать бой: «{button}» не срабатывает")
        sys.exit(0)
    else:
        print("[СЕТЬ] Бой не начался. Сброс в HALLWAY...")
    return state

def recover_context(game_window, sct):
    print("\n[УМНЫЙ СТАРТ] Сканирую экран для восстановления контекста...")
    
    # 1. Экран результатов автобоя («Ещё раз» есть) — откатываем
    if get_match_loc('btn_retry.png', game_window, sct, CONFIDENCE_THRESHOLD):
        print("[УМНЫЙ СТАРТ] Найден экран результатов. Запускаю откат боя...")
        run_rollback(game_window, sct)
        return "HALLWAY"

    # 1а. Окно результата без «Ещё раз» (ручной бой уже сыгран, переиграть нельзя) — просто закрываем
    if get_match_loc('btn_ok.png', game_window, sct, CONFIDENCE_THRESHOLD):
        print("[УМНЫЙ СТАРТ] Окно результата без кнопки «Ещё раз»: бой уже сыгран. Закрываю «ОК».")
        find_and_click_bulletproof('btn_ok.png', game_window, sct, CONFIDENCE_THRESHOLD)
        return "HALLWAY"
        
    # 2. Активный бой (ищем кнопку паузы или круглые кнопки автобоя)
    if get_match_loc('btn_pause.png', game_window, sct, 0.75) or \
       get_match_loc('btn_round_auto_off.png', game_window, sct, 0.75) or \
       get_match_loc('btn_round_auto_on.png', game_window, sct, 0.75):
        print("[УМНЫЙ СТАРТ] Бот находится в бою! Принудительно отступаю...")
        if run_rollback(game_window, sct, press_retry=False):
            print("[УМНЫЙ СТАРТ] Отступление выполнено. Возврат в HALLWAY.")
        return "HALLWAY"
        
    # 3. Экран сборки пака (видим большую кнопку В бой / Авто)
    if get_match_loc('btn_auto.png', game_window, sct, CONFIDENCE_THRESHOLD) or \
       get_match_loc('btn_in_battle.png', game_window, sct, CONFIDENCE_THRESHOLD):
        print("[УМНЫЙ СТАРТ] Бот на экране сборки пака. Запускаю бой для отката...")
        # Жмем автобой, чтобы принудительно начать битву
        find_and_click_bulletproof('btn_auto.png', game_window, sct, CONFIDENCE_THRESHOLD, timeout=8.0)
        print("[УМНЫЙ СТАРТ] Жду окно результатов для проведения отката (может занять время)...")
        
        wait_start = time.time()
        while time.time() - wait_start < 120:
            if get_match_loc('btn_retry.png', game_window, sct, 0.75):
                print("[УМНЫЙ СТАРТ] Бой окончен. Запускаю протокол отката...")
                run_rollback(game_window, sct)
                return "HALLWAY"
            time.sleep(1.0)
            
        print("[УМНЫЙ СТАРТ] Таймаут ожидания конца боя. Сброс в HALLWAY.")
        return "HALLWAY"
        
    # 4. Коридор или выбор комнат (по умолчанию)
    print("[УМНЫЙ СТАРТ] Контекст не требует экстренных действий. Начинаю с HALLWAY.")
    return "HALLWAY"

with mss.MSS() as sct:
    NEEDS_CONTEXT_RECOVERY = True
    
    while True:
        wait_for_focus() 
        
        game_window = get_window_rect(WINDOW_TITLE)
        if not game_window: 
            time.sleep(0.5)
            continue
            
        if NEEDS_CONTEXT_RECOVERY:
            STATE = recover_context(game_window, sct)
            NEEDS_CONTEXT_RECOVERY = False
            ROOM_TIMER.restart("hallway")  # старт и конец паузы в замеры комнат не входят
            STATE_CLOCK.reset()
            continue

        # === ЗАЩИТА ОТ ЗАВИСАНИЙ ===
        # Слишком долго нет экрана выбора команды или окна результата — умный старт
        limit = STATE_CLOCK.expired(STATE)
        if limit:
            report_state_timeout(STATE, limit, game_window, sct)
            NEEDS_CONTEXT_RECOVERY = True
            continue
        # Сторож: давно не пройдено ни одной комнаты — сообщить и попробовать умный старт
        if WATCHDOG.due():
            if raise_watchdog_alarm(game_window, sct):
                STATE = "HALLWAY"  # мягкая пауза: бот ждёт в коридоре, пока вы её не снимете
            else:
                NEEDS_CONTEXT_RECOVERY = True
            continue
        # =================================================
            
        # === ГЛОБАЛЬНАЯ ЗАЩИТА ОТ ДИСКОННЕКТОВ И ЛАГОВ ===
        if STATE in ["WAIT_FOR_OK", "SET_TEAM", "PREP_AUTO", "PREP_SPECIAL_ANGUS"]:
            if get_match_loc('flag_enter.png', game_window, sct, CONFIDENCE_THRESHOLD):
                print(f"\n[СЕТЬ] Сбой! Бот в состоянии {STATE}, но на экране коридор. Сброс состояния...")
                STATE = "HALLWAY"
                time.sleep(1.0)
                continue
        # =================================================
        
        if STATE == "WAIT_FOR_OK" and get_match_loc('btn_ok.png', game_window, sct, CONFIDENCE_THRESHOLD):
            ROOM_TIMER.begin("result")
            counted_room = None  # номер комнаты, если она засчитана и нужна строка [ВРЕМЯ]
            active_pack = CURRENT_PACK

            if active_pack:
                print("[ЛОГИКА] Ожидание завершения анимаций (1.5 сек)...")
                time.sleep(1.5)
                
                # Не нашлись 2 титана и больше — окно, скорее всего, перекрыто или не дорисовано: пересканируем
                team_status, unreadable = result_scan.scan_with_retries(
                    lambda: scan_team_health(game_window, sct, active_pack), active_pack, sleep=time.sleep)
                
                global_panic = engine.get_global_setting("critical_hp", 40)
                effective_delta = CURRENT_ALLOWED_DELTA if CURRENT_ALLOWED_DELTA is not None else engine.get_global_setting("max_hp_delta", 30)

                # Бой оценивается по ХП и по правилам отхила, которые сработали из-за этого боя.
                # Движок правил заново не спрашиваем: после удачного отхила он бы ответил «базовый пак»
                # и бот ложно счёл бы бой плохим. Правила по энергии сработают перед следующим боем.
                # Тестовый пак (PENDING_RULE) проверяется только по ХП.
                verdict = evaluate_battle(
                    active_pack, team_status, GLOBAL_TITAN_STATE, global_panic, effective_delta,
                    engine=None if PENDING_RULE else engine, room=current_room, enemies=CURRENT_ENEMIES
                )
                is_panic = verdict["bad"]
                panic_reason = verdict["reason"]
                if unreadable:
                    # Комнату не засчитываем: решает человек (окно SOS), скриншот остаётся для разбора
                    is_panic = True
                    panic_reason = ("Не удалось прочитать окно результата: не найдены "
                                    f"{result_scan.describe_missing(active_pack, team_status)}")
                    save_debug_shot("result_unreadable", game_window, sct)
                max_observed_loss = verdict["max_loss"]
                temporary_state = verdict["after_state"]

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
                        cv2.imwrite(data_paths.temp_sos_file(), cv2.cvtColor(scr, cv2.COLOR_BGRA2BGR))
                    except Exception as e:
                        print(f"[СИСТЕМА] Ошибка сохранения скриншота: {e}")
                            
                    save_debug_shot("sos", game_window, sct)
                    print(f"[SOS] Причина: {panic_reason}")
                    SESSION_LOG.count("sos")
                    print(f"\n[SOS_TRIGGER] {json.dumps(critical_data)}")
                    sys.stdout.flush()

                    print("[ЛОГИКА] Ожидание команды от GUI или Telegram...")
                    with ROOM_TIMER.excluded("sos_wait"):
                        decision = wait_for_input()
                    force_window_focus()

                    if decision == "MANUAL":
                        print("\n[ТАКТИКА] Ручной режим: бот ничего не нажимает и ждёт, пока вы вернётесь в коридор.")
                        print("[ИНФО] Окно игры свободно. Нажмите «Ещё раз» и переиграйте бой руками или закройте окно «ОК».")
                        x2 = bool(get_match_loc('badge_x2.png', game_window, sct, 0.75))
                        play = play_manually(game_window, sct, stuck_guard.RESULT)
                        PENDING_RULE = None  # комнату проходили вы, тестовый пак больше не проверяем
                        # Вы могли поставить в слоты других титанов: в следующий раз бот проверит слоты
                        LAST_USED_TEAMS = {"earth": [], "water": [], "fire": [], "mix": []}
                        if play.room_cleared and not play.replayed:
                            # Окно результата просто закрыли — бой засчитан как есть, ХП с этого окна верные
                            print("[ТАКТИКА] Вы закрыли окно результата без переигровки. Засчитываю бой.")
                            GLOBAL_TITAN_STATE.update(temporary_state)
                            log_battle(current_room, CURRENT_ENEMIES, active_pack, "SUCCESS", "Окно SOS: закрыто вручную", team_status)
                            print(SESSION_LOG.finish_room(count_cleared_room(x2), current_room))
                        elif play.room_cleared:
                            # Переиграли руками: ХП титанов бот не видел, поэтому забывает их
                            print("[ТАКТИКА] Комната пройдена вручную. Засчитываю её, состояние титанов сброшено.")
                            GLOBAL_TITAN_STATE.clear()
                            print(SESSION_LOG.finish_room(count_cleared_room(x2), current_room))
                        else:
                            print("[ТАКТИКА] Вы вернулись в коридор без победы в этой комнате. Комнату не засчитываю.")
                            GLOBAL_TITAN_STATE.clear()
                            ROOM_TIMER.restart("hallway")
                        print("[ИНФО] Продолжаю работу сам.")
                        STATE = "HALLWAY"
                        continue

                    elif decision == "STOP":
                        print("[ТАКТИКА] Экстренная остановка по команде пользователя.")
                        SESSION_LOG.set_stop_reason("Команда STOP из окна SOS")
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
                        SESSION_LOG.count("rollbacks")
                        ROOM_TIMER.begin("rollback")

                        # При неудаче run_rollback сам оповестит и включит мягкую паузу
                        run_rollback(game_window, sct)
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
                            cv2.imwrite(data_paths.temp_test_file(), cv2.cvtColor(scr, cv2.COLOR_BGRA2BGR))
                        except Exception as e:
                            print(f"[СИСТЕМА] Ошибка сохранения скриншота теста: {e}")
                            
                        # ДОБАВЛЯЕМ ИСТОЧНИК В ОТВЕТ
                        success_data = {
                            "titans": team_status,
                            "source": PENDING_RULE.get("source", "gui")
                        }
                        print(f"\n[SOS_TRIGGER] TEST_SUCCESS:{json.dumps(success_data)}")
                        sys.stdout.flush()
                        with ROOM_TIMER.excluded("sos_wait"):
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

                            SESSION_LOG.count("rollbacks")
                            ROOM_TIMER.begin("rollback")
                            run_rollback(game_window, sct)
                            STATE = "HALLWAY"
                            continue
                                
                    if not PENDING_RULE:
                        GLOBAL_TITAN_STATE.update(temporary_state)
                        log_battle(current_room, CURRENT_ENEMIES, active_pack, "SUCCESS", tactic_result.get('reason', 'Одобрено'), team_status)
                        
                        x2 = bool(get_match_loc('badge_x2.png', game_window, sct, 0.75))
                        counted_room = count_cleared_room(x2)

                        if CONFIG.get("debug_mode"):
                            print("\n[ПАУЗА ОТЛАДКИ] Бой завершен. Подтвердите продолжение в GUI.")
                            sys.stdout.flush()
                            with ROOM_TIMER.excluded("sos_wait"):
                                wait_for_input()
                            force_window_focus()

            find_and_click_bulletproof('btn_ok.png', game_window, sct, CONFIDENCE_THRESHOLD)
            STATE = "HALLWAY"
            if counted_room:
                # Окно результата закрыто — комната завершена. Пауза 0.5 с ниже уже считается следующей комнате
                print(SESSION_LOG.finish_room(counted_room, current_room))
            else:
                ROOM_TIMER.restart("hallway")
            time.sleep(0.5)
            continue
            
        if STATE == "HALLWAY":
            ROOM_TIMER.begin("hallway")
            if os.path.exists("pause.flag"):
                print("\n[МЯГКАЯ ПАУЗА] Бот ждет в коридоре...")
                while os.path.exists("pause.flag"):
                    time.sleep(1)
                user_waited()
                WATCHDOG.progress()  # вы разобрались с проблемой: тревоги сторожа считаются заново
                LAST_USED_TEAMS = {"earth": [], "water": [], "fire": [], "mix": []}
                GLOBAL_TITAN_STATE.clear()
                print("[ИНФО] Пауза снята. Кэш составов и здоровья очищен. Включаю механизм Умного Старта.\n")
                NEEDS_CONTEXT_RECOVERY = True
                continue
                
            stop_reason = get_stop_reason()
            if stop_reason:
                print(f"\n🛑 ОСТАНОВКА: {stop_reason}")
                SESSION_LOG.set_stop_reason(stop_reason)
                sys.exit(0)
                
            CURRENT_ENEMIES = []
            
            STATE = smart_navigate_hallway(game_window, sct)
            continue
                
        elif STATE == "ROOM_SELECTION":
            # ИСПРАВЛЕНИЕ: Передаем актуальный GLOBAL_TITAN_STATE в боевой модуль!
            found_room, enemies = find_smart_door(game_window, sct, GLOBAL_TITAN_STATE)
            if found_room:
                current_room = found_room
                CURRENT_ENEMIES = enemies
                STATE = "SET_TEAM"
            else:
                print("[СЕТЬ] Двери не найдены (ошибка загрузки окна). Сброс в HALLWAY...")
                STATE = "HALLWAY"
            continue
            
        elif STATE == "SET_TEAM":
            if get_match_loc('btn_in_battle.png', game_window, sct, CONFIDENCE_THRESHOLD) or get_match_loc('btn_auto.png', game_window, sct, CONFIDENCE_THRESHOLD):
                ROOM_TIMER.begin("team")  # экран выбора команды виден: коридор и вход закончились

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
                    print(f"[SOS] Причина: {reason}")
                    SESSION_LOG.count("sos")
                    print(f"\n[SOS_TRIGGER] {json.dumps(stop_data)}")
                    sys.stdout.flush()

                    print("[ЛОГИКА] Ожидание команды от GUI (MANUAL или NEW_PACK)...")
                    with ROOM_TIMER.excluded("sos_wait"):
                        decision = wait_for_input()
                    force_window_focus()

                    if decision == "MANUAL":
                        print("[ТАКТИКА] Ручной режим: выберите титанов и пройдите комнату сами. Бот ждёт, пока вы вернётесь в коридор.")
                        play = play_manually(game_window, sct, stuck_guard.TEAM)
                        # Вы могли поставить в слоты других титанов: в следующий раз бот проверит слоты
                        LAST_USED_TEAMS = {"earth": [], "water": [], "fire": [], "mix": []}
                        GLOBAL_TITAN_STATE.clear()  # ХП после вашего боя бот не видел
                        if play.room_cleared:
                            print("[ТАКТИКА] Комната пройдена вручную. Засчитываю её, состояние титанов сброшено.")
                            print(SESSION_LOG.finish_room(count_cleared_room(False), current_room))
                        else:
                            print("[ТАКТИКА] Вы вернулись в коридор без победы в этой комнате. Комнату не засчитываю.")
                            ROOM_TIMER.restart("hallway")
                        print("[ИНФО] Продолжаю работу сам.")
                        STATE = "HALLWAY"
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
                        SESSION_LOG.set_stop_reason("Команда STOP из окна «Нет подходящего пака»")
                        sys.exit(0)
                # =================================================================
                
                CURRENT_PACK = target_pack
                print(f"\n[ТАКТИКА] Комната {current_room} | Пак: {target_pack} | Стратегия: {CURRENT_SPECIAL_ULT}")
                
                if not target_pack:
                    print(f"\n[ОШИБКА] Пак не найден в правилах.")
                    SESSION_LOG.set_stop_reason("Пак не найден в правилах")
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
                    SESSION_LOG.set_stop_reason("Ошибка расстановки титанов")
                    sys.exit(0)
                
                if CURRENT_SPECIAL_ULT == "angus":
                    STATE = "PREP_SPECIAL_ANGUS"
                else:
                    STATE = "PREP_AUTO"
            continue
            
        elif STATE == "PREP_SPECIAL_ANGUS":
            ROOM_TIMER.begin("battle")
            if find_and_click_bulletproof('btn_in_battle.png', game_window, sct, CONFIDENCE_THRESHOLD):
                START_FAILS = 0
                execute_angus_ult(game_window, sct)
                STATE = "WAIT_FOR_OK" 
            else:
                # Раньше бот здесь повторял попытку бесконечно
                STATE = handle_failed_start("В бой", game_window, sct)
            continue
            
        elif STATE == "PREP_AUTO":
            ROOM_TIMER.begin("battle")
            print("[ТАКТИКА] Выполняю быстрый старт боя...")
            # «Авто» жмём с проверкой: если экран выбора команды не закрылся, нажатие повторится
            # (одно потерянное нажатие раньше приводило к зависанию: бот ждал боя, которого не было)
            find_and_click_bulletproof('btn_auto.png', game_window, sct, CONFIDENCE_THRESHOLD, timeout=3.0)
            
            # Умное ожидание ЛЮБОГО признака боя (Пауза, Авто-кнопки или сразу победа)
            wait_start = time.time()
            battle_confirmed = False
            while time.time() - wait_start < 10.0:
                if get_match_loc('btn_pause.png', game_window, sct, 0.75) or \
                   get_match_loc('btn_round_auto_off.png', game_window, sct, 0.75) or \
                   get_match_loc('btn_round_auto_on.png', game_window, sct, 0.75) or \
                   get_match_loc('btn_ok.png', game_window, sct, CONFIDENCE_THRESHOLD):
                    battle_confirmed = True
                    break
                time.sleep(0.1)
                
            if battle_confirmed:
                START_FAILS = 0
                STATE = "WAIT_FOR_OK"
            else:
                STATE = handle_failed_start("Авто", game_window, sct)
            continue
            
        time.sleep(0.1)