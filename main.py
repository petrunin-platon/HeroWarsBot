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
from vision import get_window_rect, find_and_click_bulletproof, get_match_loc, wait_for_ui_element, get_first_match, grab_frame, find_many
import vision
from combat import find_smart_door, execute_angus_ult, execute_rollback
from navigation import smart_navigate_hallway, take_room_window
from click_logic import after_failed_battle_start, START_BATTLE_ATTEMPTS
import rollback_logic
from telegram_agent import send_alert
from i18n import get_text
from team_manager import verify_and_set_team, scan_slots, slot_titan_names, recheck_bars
from analyzer import scan_team_health, reread_team_health, team_status_lines
from analytics import log_battle
from battle_verdict import evaluate_battle
from rules_engine import engine
from stats_manager import add_metric, add_metrics_bulk, get_game_date
import data_paths
import result_scan
import stuck_guard
import tactics
import titan_state

WINDOW_TITLE = "HeroWarsBot_Arena"
GRACEFUL_STOP = False

# Один снимок на шаг (задача 11): какие кнопки ищутся вместе с флажком коридора в этих состояниях
STATE_BUTTONS = {
    "WAIT_FOR_OK": [('btn_ok.png', CONFIDENCE_THRESHOLD)],
    "SET_TEAM": [('btn_in_battle.png', CONFIDENCE_THRESHOLD), ('btn_auto.png', CONFIDENCE_THRESHOLD)],
}
# Признаки, что бой начался (PREP_AUTO): пауза, круглые кнопки автобоя или сразу окно результата
BATTLE_SIGNS = [
    ("battle", ['btn_pause.png', 'btn_round_auto_off.png', 'btn_round_auto_on.png'], 0.75),
    ("result", ['btn_ok.png'], CONFIDENCE_THRESHOLD),
]
# ХП и энергия титанов после последнего боя. Хранятся в bot_data/titan_state.json до конца игрового дня
GLOBAL_TITAN_STATE = titan_state.TitanMemory(data_paths.titan_state_file(), get_game_date)
if GLOBAL_TITAN_STATE:
    print(f"[СОСТОЯНИЕ] Состояние титанов за игровой день {GLOBAL_TITAN_STATE.day} загружено "
          f"(сохранено {GLOBAL_TITAN_STATE.saved_at}): {GLOBAL_TITAN_STATE.describe()}")
# Пак, который проверяется в этой комнате после отката: {"room", "enemies", "team", "base_condition", "source", "tried", "learn"}.
# source: "gui"/"telegram" — пак выбрали вы, "auto" — запасной пак, бот выбрал сам (tactics.py).
# learn: False — запасной пак ставится только в помощь раненому титану, удачный бой правилом не запоминается (задача 9б)
PENDING_RULE = None

# Настройки тактики (profile.yml) и история боёв против этих врагов (bot_data/logs/*.jsonl)
TACTICS = tactics.Settings(engine.get_global_setting)
for _line in TACTICS.describe():
    print(_line)
# История судится по нынешним порогам: откат из-за того, что титан вошёл в бой раненым, пак не портит (задача 9б)
HISTORY = tactics.BattleHistory.load(data_paths.logs_dir(), TACTICS)

def add_golden_rules():
    """«Золотые правила» (задача 9б): паки, которые много раз побеждали этот состав врагов, бот сам ставит против него.
    Условия — как у кнопки во вкладке «Аналитика». Только если бот решает сам (auto_rollback)."""
    if not TACTICS.auto_rollback:
        return
    for gold in tactics.golden_packs(HISTORY, TACTICS, roster=tactics.own_titans(engine.all_packs(), TACTICS)):
        rule = engine.add_golden_rule(gold["room"], gold["enemies"], gold["team"], gold["wins"], gold["battles"],
                                      gold["avg_hp"])
        if rule:
            print(f"[ОБУЧЕНИЕ] {gold['room']}: '{rule['name']}' — пак {rule['team']}. Сохранено на 1-е место.")

add_golden_rules()

# Защита от зависаний (stuck_guard.py): сторож «давно нет пройденных комнат» и пределы ожидания по состояниям
WATCHDOG = stuck_guard.Watchdog()
STATE_CLOCK = stuck_guard.StateClock()

def user_waited():
    """Бот ждал вас (окно SOS, пауза, ручной бой, окно не в фокусе, ПК заблокирован): это время сторож и пределы не считают."""
    WATCHDOG.waited_for_user()
    STATE_CLOCK.reset()

def alert_screen_locked(seconds):
    """ПК заблокирован (Win+L) больше минуты: бот не может делать снимки и ждёт. Сообщаем один раз."""
    sent, note = send_alert(f"🔒 Экран ПК заблокирован уже {seconds:.0f} с: бот не видит игру и ждёт. "
                            "Разблокируйте ПК — бот продолжит сам.")
    print(f"[ЭКРАН] Сообщение в Telegram: {note}")

# Снимок экрана не получается (ПК заблокирован): vision.grab_frame ждёт и зовёт эти функции
vision.SCREEN_HOOKS["long_wait"] = alert_screen_locked
vision.SCREEN_HOOKS["resumed"] = lambda seconds: user_waited()

# --- NON-BLOCKING STDIN LISTENER ---
STDIN_QUEUE = queue.Queue()

def stdin_listener():
    """Фоновый поток для чтения команд из GUI без блокировки ОС. Каждая команда — со временем получения"""
    for line in sys.stdin:
        STDIN_QUEUE.put((time.time(), line.strip()))

threading.Thread(target=stdin_listener, daemon=True).start()

def wait_for_input(since=None, timeout_minutes=0):
    """Ожидание ввода с обработкой прерываний.
    since — время, когда бот задал вопрос: команды, пришедшие раньше, — ответы на старое окно, их пропускаем
    (например, вы нажали кнопку, когда бот уже решил сам). timeout_minutes — сколько ждать (0 — сколько угодно);
    не дождались — None (задача 9б: бот решает сам)."""
    deadline = time.time() + timeout_minutes * 60 if timeout_minutes else None
    while True:
        try:
            received, decision = STDIN_QUEUE.get(timeout=0.2)
            if since is not None and received < since:
                print(f"[ЛОГИКА] Пропускаю ответ '{decision}': он пришёл на прошлое окно.")
                continue
            user_waited()
            return decision
        except queue.Empty:
            if GRACEFUL_STOP:
                print("[ТАКТИКА] Экстренная остановка по команде пользователя (Ctrl+Q).")
                SESSION_LOG.set_stop_reason("Ручная остановка пользователем (Ctrl+Q)")
                sys.exit(0)
            if deadline and time.time() >= deadline:
                user_waited()
                print(f"\n[ТАКТИКА] Ответа нет {timeout_minutes} мин. Решаю сам.")
                return None

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
CURRENT_CONDITION = {}  # условие правила, которое дало текущий пак ({} — базовый пак). Нужно для обучения
CURRENT_HEAL = None  # кого лечит текущий пак, если пак отхила бот собрал сам (задача 9в); иначе None
HEAL_NOT_PLACED = set()  # кого бот не смог поставить в пак отхила: до конца запуска их паком отхила не лечит (сессия 08)
ROOM_AUTO_ROLLBACKS = 0  # сколько раз бот сам откатил бой в этой комнате
START_FAILS = 0  # сколько раз подряд не удалось начать бой («Авто» не сработала)
TEAM_SEEN = None  # когда появился экран выбора команды: от этого момента пауза реакции перед «Авто» (задача 10)

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
        scr = grab_frame(game_window, sct)
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
        scr = grab_frame(game_window, sct)
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
    global ROOM_AUTO_ROLLBACKS
    SESSION_STATS["rooms_cleared"] += 1
    ROOM_AUTO_ROLLBACKS = 0
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

def result_has_x2(frames, result_seen, game_window, sct):
    """Значок «x2» на окне результата (задача 11): на последнем снимке, с которого бот читал ХП (он сделан, когда окно
    уже проявилось: RESULT_ANIMATION_S после появления «ОК»). Если такого снимка нет — на новом снимке, как раньше."""
    if frames and frames[-1][0] >= result_seen + result_scan.RESULT_ANIMATION_S:
        _, screenshot_cv, _ = frames[-1]
        return vision.find_on_frame((screenshot_cv, 0, 0), 'badge_x2.png', 0.75) is not None
    return bool(get_match_loc('badge_x2.png', game_window, sct, 0.75))

def hp_before(pack):
    """ХП титанов пака перед боем (из GLOBAL_TITAN_STATE): {титан: ХП}. Кого бот сегодня не видел — нет в словаре.
    С задачи 9в это ХП с экрана выбора команды (read_team_screen), а не только память."""
    return {t: GLOBAL_TITAN_STATE[t]["hp"] for t in pack if "hp" in GLOBAL_TITAN_STATE.get(t, {})}

def energy_before(pack):
    """Энергия титанов пака перед боем (задача 9в): {титан: %}. Кого бот сегодня не видел — нет в словаре."""
    return {t: GLOBAL_TITAN_STATE[t]["energy"] for t in pack if "energy" in GLOBAL_TITAN_STATE.get(t, {})}

def record_battle(room, enemies, pack, action, reason, team_status, before=None, energy=None):
    """Бой в историю (bot_data/logs/*.jsonl) и в память для выбора запасного пака. before и energy — ХП и энергия до боя.
    Бой пака отхила, который бот собрал сам, помечается (heal_for): «золотым правилом» такой пак не становится."""
    heal_for = CURRENT_HEAL if pack == CURRENT_PACK else None
    HISTORY.add(log_battle(room, enemies, pack, action, reason, team_status, hp_before=before, energy_before=energy,
                           heal_for=heal_for))

def apply_screen_bars(bars, game_window, sct):
    """ХП и энергия с экрана выбора команды (задача 9в) — в GLOBAL_TITAN_STATE и в лог.
    Если бот помнил другое (или не знал: после ручной игры, паузы, перезапуска), в скобках — что он помнил.
    Такие полоски сначала перечитываются (recheck_bars): вдруг они ещё не дорисовались."""
    if not bars:
        return
    _, _, doubtful = titan_state.screen_reading(GLOBAL_TITAN_STATE, bars)
    if doubtful:
        recheck_bars(doubtful, bars, game_window, sct)
    updates, text, fixed = titan_state.screen_reading(GLOBAL_TITAN_STATE, bars)
    if updates:
        GLOBAL_TITAN_STATE.update(updates)
    for _ in fixed:
        SESSION_LOG.count("screen_hp")
    print(f"[СОСТОЯНИЕ] Перед боем (экран выбора команды): {text}")

def read_team_screen(game_window, sct):
    """Экран выбора команды (задача 9в): кто стоит в слотах, их ХП и энергия — один снимок, до выбора пака.
    Если бот уже ставил пак в этой стихии (LAST_USED_TEAMS), ищет только этих титанов — так быстрее.
    Возвращает (кто виден в слотах — {титан: info} для verify_and_set_team, или None, если прочитались не все;
    кого бот прочитал)."""
    guess = LAST_USED_TEAMS.get(current_room) or []
    found, _, bars = scan_slots(guess or slot_titan_names(), game_window, sct)
    apply_screen_bars(bars, game_window, sct)
    complete = not guess or len(found) == len(set(guess))
    return (found if complete else None), set(bars)

def pack_danger(room, enemies):
    """Функция «чем пак опасен для раненых титанов в этой комнате» (tactics.wounded_at_risk) — для выбора пака и двери."""
    def danger(pack):
        risks = tactics.wounded_at_risk(room, enemies, pack, GLOBAL_TITAN_STATE, TACTICS, HISTORY)
        return tactics.describe_risks(risks, GLOBAL_TITAN_STATE)
    return danger

def plan_heal(room, enemies, pack, notes=None):
    """Пак отхила, который бот собирает сам (задача 9в, tactics.heal_plan): (пак, кого лечим, пояснение) или None.
    Только если бот решает сам (auto_rollback)."""
    if not TACTICS.auto_rollback:
        return None
    return tactics.heal_plan(room, pack, GLOBAL_TITAN_STATE, TACTICS, HISTORY, engine.base_packs(),
                             forbidden=engine.forbidden_titans(room, enemies, GLOBAL_TITAN_STATE), enemies=enemies,
                             special_ult=engine.special_ult_for, notes=notes, not_placed=HEAL_NOT_PLACED,
                             reserve=tactics.own_titans(engine.all_packs(), TACTICS))

def door_hints():
    """Подсказки для выбора двери по здоровью (задача 9б, tactics.door_choice):
    heals — правило отхила, которое сработает за дверью (с задачи 9в — и пак отхила, который бот соберёт сам);
    danger — чем стихия опасна для раненых (по прошлым боям).
    Врагов за дверью бот ещё не видел, поэтому берётся пак, который он поставил бы без анти-паков."""
    def planned(room):
        choice = engine.battle_decision(room, [], GLOBAL_TITAN_STATE)
        heal = plan_heal(room, [], choice["team"]) if not choice["condition"] else None
        return choice["team"], heal

    def heals(room):
        rule = engine.heal_rule_for(room, GLOBAL_TITAN_STATE, tactics.HEALERS)
        if rule:
            return rule
        _, heal = planned(room)
        return f"бот соберёт пак отхила: {heal[2]}" if heal else ""

    def danger(room):
        pack, heal = planned(room)
        pack = heal[0] if heal else pack
        return pack_danger(room, [])(pack) if pack and pack != ["STOP"] else ""
    return heals, danger

def find_backup(tried, allow_risky=True):
    """Запасной пак для текущей комнаты (tactics.choose_backup). tried — паки, которые уже проиграли здесь.
    Паки, опасные для раненых титанов, — в последнюю очередь (allow_risky=False — совсем не брать).
    Почему паки из вашего списка и правил не взяты, пишется в лог."""
    notes = []
    backup, source = tactics.choose_backup(
        current_room, CURRENT_ENEMIES, tried, GLOBAL_TITAN_STATE, TACTICS, engine.room_packs(current_room), HISTORY,
        forbidden=engine.forbidden_titans(current_room, CURRENT_ENEMIES, GLOBAL_TITAN_STATE),
        risky=pack_danger(current_room, CURRENT_ENEMIES), allow_risky=allow_risky, notes=notes,
        roster=tactics.own_titans(engine.all_packs(), TACTICS))
    for note in notes:
        print(f"[ТАКТИКА] Не беру запасной пак {note}")
    return backup, source

def pending_pack(team, source, tried, learn=True):
    """Пак для проверки в этой же комнате после отката (PENDING_RULE).
    learn=False — пак ставится в помощь раненому титану: если он справится, правило не запоминается (задача 9б)."""
    return {
        "room": current_room,
        "enemies": list(CURRENT_ENEMIES),
        "team": team,
        "base_condition": dict(CURRENT_CONDITION),
        "source": source,
        "tried": [list(p) for p in tried],
        "learn": learn,
    }

def start_auto_rollback(backup, tried, learn, active_pack, reason, team_status, before, energy, game_window, sct):
    """Бот сам откатывает бой и переиграет запасным паком (auto_rollback или вы не ответили на окно SOS)."""
    global PENDING_RULE, ROOM_AUTO_ROLLBACKS
    record_battle(current_room, CURRENT_ENEMIES, active_pack, "ROLLBACK", f"Авто-откат: {reason}", team_status, before,
                  energy)
    PENDING_RULE = pending_pack(backup, "auto", tried, learn=learn)
    ROOM_AUTO_ROLLBACKS += 1
    SESSION_LOG.count("rollbacks")
    SESSION_LOG.count("auto_rollbacks")
    ROOM_TIMER.begin("rollback")
    # При неудаче run_rollback сам оповестит и включит мягкую паузу
    run_rollback(game_window, sct)

def close_sos_window(text):
    """Бот решил сам: окно программы закрывает окно SOS (строка [SOS_CLOSE]), а вам уходит сообщение в Telegram."""
    print(f"[SOS_CLOSE] {text}")
    sys.stdout.flush()
    lines = ["🤖 Вы не ответили на окно «Требуется вмешательство», бот решил сам", text]
    if current_room in ROOM_NAMES_RU:
        lines.append(f"Комната: {ROOM_NAMES_RU[current_room]}")
    if CURRENT_ENEMIES:
        lines.append("Враги: " + ", ".join(get_text("RU", f"titan_{e}") for e in CURRENT_ENEMIES))
    image = data_paths.temp_sos_file() if os.path.exists(data_paths.temp_sos_file()) else None

    def send():
        sent, note = send_alert("\n".join(lines), image)
        print(f"[ТАКТИКА] Сообщение в Telegram: {note}")
    threading.Thread(target=send, daemon=True).start()  # без интернета бот не ждёт

def soft_pause(text):
    """Безопасная остановка: мягкая пауза (pause.flag). Бот ждёт в коридоре, пока вы её не снимете."""
    with open("pause.flag", "w") as f:
        f.write("1")
    print(f"[ВНИМАНИЕ] Бот на мягкой паузе: {text}. Посмотрите, что на экране телефона, и снимите паузу в окне программы.")

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

# Постоянное соединение с телефоном открывается заранее, заодно замер: из чего складывается задержка нажатия (задача 11)
threading.Thread(target=vision.measure_adb, daemon=True).start()

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
        # Один снимок на шаг (задача 11): флажок коридора и кнопки этого состояния ищутся на одном снимке
        SCREEN = {}
        if STATE in ["WAIT_FOR_OK", "SET_TEAM", "PREP_AUTO", "PREP_SPECIAL_ANGUS"]:
            SCREEN_AT = time.monotonic()
            _, SCREEN = find_many(game_window, sct, [('flag_enter.png', CONFIDENCE_THRESHOLD)] + STATE_BUTTONS.get(STATE, []))
            if 'flag_enter.png' in SCREEN:
                print(f"\n[СЕТЬ] Сбой! Бот в состоянии {STATE}, но на экране коридор. Сброс состояния...")
                STATE = "HALLWAY"
                time.sleep(1.0)
                continue
        # =================================================

        if STATE == "WAIT_FOR_OK" and 'btn_ok.png' not in SCREEN:
            time.sleep(0.1)  # бой ещё идёт: не грузим слабый ПК поиском без остановки
            continue

        if STATE == "WAIT_FOR_OK":
            ROOM_TIMER.begin("result")
            result_seen = SCREEN_AT  # от этого момента пауза реакции перед «ОК» (задача 10)
            counted_room = None  # номер комнаты, если она засчитана и нужна строка [ВРЕМЯ]
            active_pack = CURRENT_PACK

            if active_pack:
                # Окно ещё проявляется: читаем через RESULT_ANIMATION_S (1,2 с) после появления «ОК» (задача 11, ваш совет).
                # Потом перечитываем полоски, пока три снимка подряд не покажут одно и то же (полоски иногда заполняются
                # дольше 1,2 с). Цифры в лог — только итоговые, по ним бот и решает
                result_scan.wait_window_settled(result_seen)
                icons = {}  # где нашлись иконки титанов: по ним полоски перечитываются быстро
                scanned_at = []
                result_frames = []  # снимки окна результата: на последнем ищем значок «x2» (задача 11)

                def scan_result():
                    scanned_at.append(time.monotonic())
                    return scan_team_health(game_window, sct, active_pack, found=icons, frames=result_frames, quiet=True)

                # Не найден хотя бы один титан — окно, скорее всего, перекрыто или не дорисовано: пересканируем
                team_status, unreadable = result_scan.scan_with_retries(scan_result, active_pack, sleep=time.sleep)
                if unreadable and result_scan.window_closed(
                        active_pack, team_status, bool(get_match_loc('btn_ok.png', game_window, sct, CONFIDENCE_THRESHOLD))):
                    print("[ЛОГИКА] Окно с «ОК» закрылось, пока бот ждал анимацию: ни одного титана и кнопки «ОК» нет. "
                          "Читать нечего — возвращаюсь в коридор.")
                    ROOM_TIMER.restart("hallway")
                    STATE = "HALLWAY"
                    continue
                if not unreadable:
                    team_status = result_scan.wait_bars_still(
                        team_status, active_pack, lambda: reread_team_health(game_window, sct, icons, result_frames),
                        scanned_at[-1], pairs=result_scan.RESULT_STILL_PAIRS)
                print(f"\n[АНАЛИЗАТОР] Окно результата (через {time.monotonic() - result_seen:.1f} с после появления «ОК»):")
                for line in team_status_lines(active_pack, team_status):
                    print(line)
                
                effective_delta = CURRENT_ALLOWED_DELTA if CURRENT_ALLOWED_DELTA is not None else TACTICS.max_hp_delta

                # Бой оценивается по ХП и по правилам отхила, которые сработали из-за этого боя.
                # Движок правил заново не спрашиваем: после удачного отхила он бы ответил «базовый пак»
                # и бот ложно счёл бы бой плохим. Правила по энергии сработают перед следующим боем.
                # Тестовый пак (PENDING_RULE) проверяется только по ХП (и по общим потерям пака).
                verdict = evaluate_battle(
                    active_pack, team_status, GLOBAL_TITAN_STATE, TACTICS.critical_hp, effective_delta,
                    engine=None if PENDING_RULE else engine, room=current_room, enemies=CURRENT_ENEMIES,
                    group_loss=TACTICS.group_loss, titan_critical_hp=TACTICS.titan_critical_hp
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
                before = hp_before(active_pack)  # ХП до боя: пишется в историю, по нему видно, кто виноват
                before_energy = energy_before(active_pack)  # энергия до боя: по ней прогноз потерь (задача 9в)

                # Кто виноват в плохом бое (задача 9б): враги или титан вошёл в бой раненым (со 100% ХП бой был бы
                # нормальным). Во втором случае запасной пак — разовая помощь: удачный бой правилом не запоминается
                wounded = ", ".join(f"{t.upper()} {hp}%" for t, hp in before.items() if hp < 100)
                weak_entry = is_panic and not unreadable and bool(wounded) and \
                    not TACTICS.full_hp_reason(active_pack, team_status, before, effective_delta)
                learn = not (weak_entry or unreadable) and (PENDING_RULE.get("learn", True) if PENDING_RULE else True)

                if is_panic:
                    tactic_result = {"action": "rollback", "reason": panic_reason}
                else:
                    tactic_result = {"action": "success", "reason": "Потери в пределах нормы"}

                # === БОТ РЕШАЕТ САМ (auto_rollback): откат и запасной пак без окна SOS ===
                if is_panic and TACTICS.auto_rollback:
                    tried = (PENDING_RULE["tried"] if PENDING_RULE else []) + [active_pack]
                    blocker = tactics.auto_rollback_blocker(
                        TACTICS, CURRENT_SPECIAL_ULT == "angus", unreadable, ROOM_AUTO_ROLLBACKS,
                        user_pack=bool(PENDING_RULE) and PENDING_RULE["source"] != "auto")
                    backup, source = (None, None) if blocker else find_backup(tried)
                    if backup:
                        print(f"\n[ТАКТИКА] Плохой бой: {panic_reason}")
                        if weak_entry:
                            print(f"[ТАКТИКА] Враги ни при чём: в бой вошли раненые ({wounded}), со 100% ХП бой был бы "
                                  "нормальным. Запасной пак — разовая помощь, правило против этих врагов не запоминаю.")
                        print(f"[ТАКТИКА] Откатываю бой сам и переиграю паком {backup} (взят: {source}).")
                        start_auto_rollback(backup, tried, learn, active_pack, panic_reason, team_status, before,
                                            before_energy, game_window, sct)
                        STATE = "HALLWAY"
                        continue
                    why = blocker or "подходящего запасного пака нет (другие паки уже проигрывали этим врагам или в них раненые титаны)"
                    print(f"[ТАКТИКА] Сам не откатываю: {why}. Спрашиваю вас.")

                if tactic_result["action"] == "rollback":
                    critical_data = {
                        "titans": {},
                        "is_manual": (CURRENT_SPECIAL_ULT == "angus") 
                    }
                    for t in active_pack:
                        critical_data["titans"][t] = team_status.get(t, {}).get("hp", 0)
                            
                    try:
                        scr = grab_frame(game_window, sct)
                        cv2.imwrite(data_paths.temp_sos_file(), cv2.cvtColor(scr, cv2.COLOR_BGRA2BGR))
                    except Exception as e:
                        print(f"[СИСТЕМА] Ошибка сохранения скриншота: {e}")
                            
                    save_debug_shot("sos", game_window, sct)
                    print(f"[SOS] Причина: {panic_reason}")
                    SESSION_LOG.count("sos")
                    sos_asked = time.time()
                    print(f"\n[SOS_TRIGGER] {json.dumps(critical_data)}")
                    sys.stdout.flush()

                    print("[ЛОГИКА] Ожидание команды от GUI или Telegram...")
                    with ROOM_TIMER.excluded("sos_wait"):
                        decision = wait_for_input(since=sos_asked, timeout_minutes=TACTICS.sos_timeout_minutes)
                    force_window_focus()

                    if decision is None:
                        # === ВЫ НЕ ОТВЕТИЛИ (задача 9б): запасной пак, принять бой или безопасно остановиться ===
                        tried = (PENDING_RULE["tried"] if PENDING_RULE else []) + [active_pack]
                        can_rollback = CURRENT_SPECIAL_ULT != "angus" and ROOM_AUTO_ROLLBACKS < TACTICS.auto_rollback_tries
                        backup, source = find_backup(tried) if can_rollback else (None, None)
                        choice, why = tactics.decide_without_you(active_pack, team_status, can_rollback, backup)
                        print(f"[ТАКТИКА] Решение без вас: {why}.")
                        close_sos_window(f"{panic_reason}\nРешение: {why}.")
                        if choice == tactics.ROLLBACK:
                            print(f"[ТАКТИКА] Запасной пак {backup} взят: {source}.")
                            start_auto_rollback(backup, tried, learn, active_pack, panic_reason, team_status, before,
                                                before_energy, game_window, sct)
                            STATE = "HALLWAY"
                            continue
                        if choice == tactics.PAUSE:
                            PENDING_RULE = None
                            soft_pause(why)
                            ROOM_TIMER.restart("hallway")
                            STATE = "HALLWAY"  # после снятия паузы умный старт откатит бой или закроет окно «ОК»
                            continue
                        PENDING_RULE = None  # бой принят как есть: тестовый пак больше не проверяем
                        decision = "IGNORE"

                    if decision == "MANUAL":
                        print("\n[ТАКТИКА] Ручной режим: бот ничего не нажимает и ждёт, пока вы вернётесь в коридор.")
                        print("[ИНФО] Окно игры свободно. Нажмите «Ещё раз» и переиграйте бой руками или закройте окно «ОК».")
                        x2 = bool(get_match_loc('badge_x2.png', game_window, sct, 0.75))
                        play = play_manually(game_window, sct, stuck_guard.RESULT)
                        PENDING_RULE = None  # комнату проходили вы, тестовый пак больше не проверяем
                        ROOM_AUTO_ROLLBACKS = 0
                        # Вы могли поставить в слоты других титанов: в следующий раз бот проверит слоты
                        LAST_USED_TEAMS = {"earth": [], "water": [], "fire": [], "mix": []}
                        if play.room_cleared and not play.replayed:
                            # Окно результата просто закрыли — бой засчитан как есть, ХП с этого окна верные
                            print("[ТАКТИКА] Вы закрыли окно результата без переигровки. Засчитываю бой.")
                            GLOBAL_TITAN_STATE.update(temporary_state)
                            record_battle(current_room, CURRENT_ENEMIES, active_pack, "SUCCESS", "Окно SOS: закрыто вручную",
                                          team_status, before, before_energy)
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
                            
                            tried = (PENDING_RULE["tried"] if PENDING_RULE else []) + [active_pack]
                            PENDING_RULE = pending_pack(
                                new_team, "telegram" if decision.startswith("ROLLBACK_TG") else "gui", tried)

                        record_battle(current_room, CURRENT_ENEMIES, active_pack, "ROLLBACK", tactic_result["reason"],
                                      team_status, before, before_energy)
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
                    if PENDING_RULE and PENDING_RULE["source"] == "auto" and not is_panic:
                        # Запасной пак, который бот выбрал сам, справился: запоминаем без вопросов.
                        # Но не тот, что ставился в помощь раненым: враги ни при чём, правило мешало бы потом (сессия 07)
                        if PENDING_RULE.get("learn", True):
                            print(f"[ТАКТИКА] Запасной пак {PENDING_RULE['team']} справился. Запоминаю его против этих врагов.")
                            engine.learn_new_rule(
                                PENDING_RULE["room"], PENDING_RULE["enemies"], PENDING_RULE["team"],
                                base_condition=PENDING_RULE["base_condition"], success_loss=max_observed_loss, source="auto")
                        else:
                            print(f"[ТАКТИКА] Запасной пак {PENDING_RULE['team']} справился. Правило не запоминаю: "
                                  "это была разовая помощь раненым титанам.")
                        PENDING_RULE = None

                    if PENDING_RULE:
                        # ДЕЛАЕМ СКРИНШОТ УСПЕШНОГО БОЯ ДЛЯ ТЕЛЕГРАМА
                        try:
                            scr = grab_frame(game_window, sct)
                            cv2.imwrite(data_paths.temp_test_file(), cv2.cvtColor(scr, cv2.COLOR_BGRA2BGR))
                        except Exception as e:
                            print(f"[СИСТЕМА] Ошибка сохранения скриншота теста: {e}")
                            
                        # ДОБАВЛЯЕМ ИСТОЧНИК В ОТВЕТ
                        success_data = {
                            "titans": team_status,
                            "source": PENDING_RULE.get("source", "gui")
                        }
                        test_asked = time.time()
                        print(f"\n[SOS_TRIGGER] TEST_SUCCESS:{json.dumps(success_data)}")
                        sys.stdout.flush()
                        with ROOM_TIMER.excluded("sos_wait"):
                            decision = wait_for_input(since=test_asked, timeout_minutes=TACTICS.sos_timeout_minutes)
                        force_window_focus()
                        if decision is None:
                            # Вы не ответили (задача 9б): пак, который вы выбрали, справился — запоминаем, как «Подтвердить»
                            why = f"пак {PENDING_RULE['team']} справился — запоминаю его, как если бы вы нажали «Подтвердить»"
                            print(f"[ТАКТИКА] Решение без вас: {why}.")
                            close_sos_window(f"Проверка пака\nРешение: {why}.")
                            decision = "CONFIRM"
                        
                        if decision == "CONFIRM":
                            # Допуск потерь — из этого (удачного) боя, а не из проигранного
                            engine.learn_new_rule(
                                PENDING_RULE["room"], PENDING_RULE["enemies"], PENDING_RULE["team"],
                                base_condition=PENDING_RULE["base_condition"], success_loss=max_observed_loss,
                                source=PENDING_RULE["source"])
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
                                PENDING_RULE["tried"].append(list(active_pack))
                                if decision.startswith("ROLLBACK_TG"):
                                    PENDING_RULE["source"] = "telegram"

                            SESSION_LOG.count("rollbacks")
                            ROOM_TIMER.begin("rollback")
                            run_rollback(game_window, sct)
                            STATE = "HALLWAY"
                            continue
                                
                    if not PENDING_RULE:
                        GLOBAL_TITAN_STATE.update(temporary_state)
                        record_battle(current_room, CURRENT_ENEMIES, active_pack, "SUCCESS", tactic_result.get('reason', 'Одобрено'),
                                      team_status, before, before_energy)
                        
                        x2 = result_has_x2(result_frames, result_seen, game_window, sct)
                        counted_room = count_cleared_room(x2)

                        if CONFIG.get("debug_mode"):
                            print("\n[ПАУЗА ОТЛАДКИ] Бой завершен. Подтвердите продолжение в GUI.")
                            sys.stdout.flush()
                            with ROOM_TIMER.excluded("sos_wait"):
                                wait_for_input()
                            force_window_focus()

            find_and_click_bulletproof('btn_ok.png', game_window, sct, CONFIDENCE_THRESHOLD, seen_at=result_seen)
            STATE = "HALLWAY"
            if counted_room:
                # Окно результата закрыто — комната завершена. Паузы 0,5 с после «ОК» больше нет (задача 10):
                # коридор сам ждёт, пока флажок двери встанет на место
                print(SESSION_LOG.finish_room(counted_room, current_room))
            else:
                ROOM_TIMER.restart("hallway")
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
                
            if GLOBAL_TITAN_STATE.new_day():
                print(f"[СОСТОЯНИЕ] Начался новый игровой день {GLOBAL_TITAN_STATE.day}: у всех титанов снова 100% ХП. "
                      "Состояние титанов сброшено.")

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
            # Дверь по здоровью титанов (задача 9б) — только если бот решает сам
            found_room, enemies = find_smart_door(game_window, sct, GLOBAL_TITAN_STATE,
                                                  door_hints=door_hints() if TACTICS.auto_rollback else None,
                                                  opened=take_room_window())
            if found_room:
                current_room = found_room
                CURRENT_ENEMIES = enemies
                STATE = "SET_TEAM"
            else:
                print("[СЕТЬ] Двери не найдены (ошибка загрузки окна). Сброс в HALLWAY...")
                STATE = "HALLWAY"
            continue
            
        elif STATE == "SET_TEAM":
            if 'btn_in_battle.png' not in SCREEN and 'btn_auto.png' not in SCREEN:
                time.sleep(0.05)  # экран выбора команды ещё не открылся
            else:
                ROOM_TIMER.begin("team")  # экран выбора команды виден: коридор и вход закончились
                TEAM_SEEN = SCREEN_AT
                # Точное ХП и энергия перед боем (задача 9в): полоски у титанов в слотах, до выбора пака
                slots_seen, slots_read = read_team_screen(game_window, sct)
                CURRENT_HEAL = None

                # Запасной пак бота — только для той же комнаты (та же стихия и те же враги), где был откат.
                # Счётчик откатов не сбрасываем: комната не пройдена, второй раз сам бот откатывать не будет
                if PENDING_RULE and PENDING_RULE["source"] == "auto" and (
                        PENDING_RULE["room"] != current_room or set(PENDING_RULE["enemies"]) != set(CURRENT_ENEMIES)):
                    print(f"[ТАКТИКА] Это не та комната, где был откат ({PENDING_RULE['room']} {PENDING_RULE['enemies']}, "
                          f"сейчас {current_room} {CURRENT_ENEMIES}). Запасной пак здесь не ставлю.")
                    PENDING_RULE = None

                if PENDING_RULE and PENDING_RULE["room"] == current_room:
                    target_pack = PENDING_RULE["team"]
                    CURRENT_ALLOWED_DELTA = None
                    CURRENT_CONDITION = PENDING_RULE["base_condition"]
                    if PENDING_RULE["source"] == "auto":
                        reason = "Запасной пак после отката"
                        CURRENT_SPECIAL_ULT = engine.special_ult_for(target_pack)
                    else:
                        reason = "Тестирование нового пака"
                        CURRENT_SPECIAL_ULT = "angus" if "angus" in target_pack else "auto"
                else:
                    choice = engine.battle_decision(current_room, CURRENT_ENEMIES, GLOBAL_TITAN_STATE)
                    target_pack, reason = choice["team"], choice["reason"]
                    CURRENT_ALLOWED_DELTA, CURRENT_SPECIAL_ULT = choice["delta"], choice["special_ult"]
                    CURRENT_CONDITION = choice["condition"]

                    # Пак отхила по правилам игры (задача 9в): ваше правило отхила не сработало, а кто-то ранен —
                    # бот сам ставит раненого в пак смешанной (или лекаря-помощника, если раненый в паке не поднимается).
                    # Только вместо базового пака и только если бот решает сам. Удачный бой правилом не запоминается
                    if TACTICS.auto_rollback and not CURRENT_CONDITION and target_pack and target_pack != ["STOP"] \
                            and not HISTORY.lost_to(current_room, CURRENT_ENEMIES, target_pack):
                        heal_notes = []
                        heal = plan_heal(current_room, CURRENT_ENEMIES, target_pack, heal_notes)
                        for note in heal_notes:
                            print(f"[ТАКТИКА] Отхил: {note}.")
                        if heal:
                            target_pack, CURRENT_HEAL, why = heal
                            print(f"[ТАКТИКА] Пак отхила (бот собрал сам): {target_pack}. {why}. "
                                  "Это разовая помощь: правило не запоминаю.")
                            reason = f"Пак отхила: {why}"
                            CURRENT_CONDITION = {"titan_hp_below": {CURRENT_HEAL: TACTICS.heal_hp}}
                            CURRENT_ALLOWED_DELTA = None
                            CURRENT_SPECIAL_ULT = engine.special_ult_for(target_pack)
                            SESSION_LOG.count("heal_packs")

                    # Только если бот решает сам (auto_rollback) — сразу ставим запасной пак, когда:
                    # 1) этот пак проигрывает этим врагам (последний бой откатили по вине врагов, побед не больше
                    #    поражений) — удачный бой запомнится как правило;
                    # 2) раненый титан, судя по прошлым боям, упадёт ниже порога паники (задача 9б, сессия 07, комната 54) —
                    #    это разовая помощь, правило не запоминается. Пак правила отхила/спасения так не заменяется.
                    if TACTICS.auto_rollback and target_pack and target_pack != ["STOP"]:
                        losing = HISTORY.lost_to(current_room, CURRENT_ENEMIES, target_pack)
                        risks = [] if losing or tactics.is_rescue_condition(CURRENT_CONDITION) else tactics.wounded_at_risk(
                            current_room, CURRENT_ENEMIES, target_pack, GLOBAL_TITAN_STATE, TACTICS, HISTORY)
                        backup, source = find_backup([target_pack], allow_risky=losing) if losing or risks else (None, None)
                        if losing and backup:
                            print(f"[ТАКТИКА] Пак {target_pack} проигрывает этим врагам (в прошлый раз бой откатили). "
                                  f"Сразу ставлю {backup} (взят: {source}).")
                        elif backup:
                            print(f"[ТАКТИКА] С паком {target_pack} раненые упадут ниже порога паники "
                                  f"({tactics.describe_risks(risks, GLOBAL_TITAN_STATE)}). Сразу ставлю {backup} (взят: {source}). "
                                  "Это разовая помощь: правило не запоминаю.")
                        elif risks:
                            print(f"[ТАКТИКА] Раненые могут упасть ниже порога паники "
                                  f"({tactics.describe_risks(risks, GLOBAL_TITAN_STATE)}), "
                                  f"но подходящего запасного пака нет. Ставлю {target_pack}.")
                        if backup:
                            PENDING_RULE = pending_pack(backup, "auto", [target_pack], learn=losing)
                            target_pack = backup
                            reason = ("Запасной пак: основной проигрывал этим врагам" if losing
                                      else "Запасной пак: помощь раненым")
                            CURRENT_ALLOWED_DELTA = None
                            CURRENT_SPECIAL_ULT = engine.special_ult_for(backup)
                
                # =================================================================
                # УМНАЯ ОСТАНОВКА: СВЯЗЬ С GUI (ИНТЕРАКТИВНОЕ СПАСЕНИЕ)
                # =================================================================
                if target_pack == ["STOP"]:
                    print(f"\n[АЛЕРТ] ФАТАЛЬНО: {reason}")
                    slots_seen = None  # пока бот ждёт ответа, на экране могли что-то поменять: слоты снимем заново
                    
                    # Отправляем SOS-сигнал в GUI со спец-типом NO_VALID_TEAM
                    stop_data = {
                        "type": "NO_VALID_TEAM",
                        "room": current_room,
                        "enemies": CURRENT_ENEMIES,
                        "reason": reason
                    }
                    print(f"[SOS] Причина: {reason}")
                    SESSION_LOG.count("sos")
                    sos_asked = time.time()
                    print(f"\n[SOS_TRIGGER] {json.dumps(stop_data)}")
                    sys.stdout.flush()

                    print("[ЛОГИКА] Ожидание команды от GUI (MANUAL или NEW_PACK)...")
                    with ROOM_TIMER.excluded("sos_wait"):
                        decision = wait_for_input(since=sos_asked, timeout_minutes=TACTICS.sos_timeout_minutes)
                    force_window_focus()

                    if decision is None:
                        # Вы не ответили (задача 9б): запасной пак без раненых и запрещённых титанов или мягкая пауза
                        backup, source = find_backup([], allow_risky=False)
                        if backup:
                            why = f"ставлю запасной пак {backup} (взят: {source}), правило не запоминаю"
                            print(f"[ТАКТИКА] Решение без вас: {why}.")
                            close_sos_window(f"{reason}\nРешение: {why}.")
                            PENDING_RULE = pending_pack(backup, "auto", [], learn=False)
                            target_pack = backup
                            CURRENT_SPECIAL_ULT = engine.special_ult_for(backup)
                            decision = ""  # дальше — обычная сборка пака
                        else:
                            why = "подходящего запасного пака нет"
                            print(f"[ТАКТИКА] Решение без вас: {why}. Встаю на мягкую паузу.")
                            close_sos_window(f"{reason}\nРешение: {why}, бот на мягкой паузе.")
                            soft_pause(why)
                            ROOM_TIMER.restart("hallway")
                            STATE = "HALLWAY"
                            continue

                    if decision == "MANUAL":
                        print("[ТАКТИКА] Ручной режим: выберите титанов и пройдите комнату сами. Бот ждёт, пока вы вернётесь в коридор.")
                        play = play_manually(game_window, sct, stuck_guard.TEAM)
                        PENDING_RULE = None
                        ROOM_AUTO_ROLLBACKS = 0
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
                        engine.learn_new_rule(current_room, CURRENT_ENEMIES, new_team, base_condition=CURRENT_CONDITION)
                        
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
                
                # Сборку пропускаем, только если на экране и правда видны все титаны пака (задача 11). Сессия 09:
                # бот помнил, что поставил Араджи, Игниса и Ашерона, а в слотах вместо Араджи стоял Вулкан
                if target_pack == LAST_USED_TEAMS.get(current_room) and slots_seen is not None \
                        and set(slots_seen) == set(target_pack):
                    print(f"[ТАКТИКА] Пак {target_pack} уже стоит в комнате {current_room}. Пропускаем сборку!")
                    team_ready = True
                else:
                    placed = {}
                    team_ready = verify_and_set_team(target_pack, ALL_ACTIVE_TITANS, game_window, sct,
                                                     seen=slots_seen, bars=placed)
                    if team_ready:
                        LAST_USED_TEAMS[current_room] = target_pack
                    # ХП и энергия тех, кого бот только что поставил: до сборки их в слотах не было (задача 9в)
                    apply_screen_bars({t: b for t, b in placed.items() if t not in slots_read}, game_window, sct)
                
                if not team_ready and CURRENT_HEAL:
                    # Пак отхила бот придумал сам — из-за него останавливаться нельзя (сессия 08: Алекто не встала
                    # в слот). Больше этого титана паком отхила не лечим и снова выбираем пак, уже без него
                    print(f"[ТАКТИКА] Пак отхила для {CURRENT_HEAL.upper()} собрать не удалось. Ставлю обычный пак, "
                          f"{CURRENT_HEAL.upper()} паком отхила до конца запуска не лечу.")
                    HEAL_NOT_PLACED.add(CURRENT_HEAL)
                    LAST_USED_TEAMS.pop(current_room, None)
                    STATE_CLOCK.reset()  # попытки сборки — не зависание
                    continue

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
            if find_and_click_bulletproof('btn_in_battle.png', game_window, sct, CONFIDENCE_THRESHOLD, seen_at=TEAM_SEEN):
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
            find_and_click_bulletproof('btn_auto.png', game_window, sct, CONFIDENCE_THRESHOLD, timeout=3.0, seen_at=TEAM_SEEN)
            
            # Умное ожидание ЛЮБОГО признака боя (Пауза, Авто-кнопки или сразу победа) — один снимок на все (задача 11)
            wait_start = time.time()
            battle_confirmed = False
            while time.time() - wait_start < 10.0:
                if get_first_match(BATTLE_SIGNS, game_window, sct):
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