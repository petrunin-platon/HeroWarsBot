# navigation.py
import time
from config import CONFIDENCE_THRESHOLD
from vision import (click_human, get_match_loc, get_match_info, click_point_from_info, find_and_click_bulletproof,
                    wait_for_ui_element, wait_after_tap)
from click_logic import StableTracker, DOOR_STABLE_TOL_PX, FLOOR_FLAG_WAIT_S
import vision
import session_log

# Окно выбора комнат после нажатия на дверь: (когда увидели, центр кнопки «Атаковать» в координатах окна).
# Его берёт find_smart_door (main.py), чтобы не ждать, пока окно «успокоится», отдельной паузой (задача 10)
ROOM_WINDOW = {"seen": None}


def take_room_window():
    """Что видели после нажатия на дверь (или None) — один раз."""
    seen, ROOM_WINDOW["seen"] = ROOM_WINDOW["seen"], None
    return seen


def smart_navigate_hallway(window_rect, sct):
    print("[НАВИГАЦИЯ] Сканирую коридор (динамическое ожидание)...")
    wait_start = time.time()
    ROOM_WINDOW["seen"] = None
    # Дверь жмём, только когда флажок стоит на месте
    door = StableTracker(clock=time.monotonic, tol=DOOR_STABLE_TOL_PX * vision.GEOMETRY_CACHE.get("scale", 1.0))
    
    while time.time() - wait_start < 10.0:
        # 1. Приоритет 1: Кнопка атаки (уже стоим у открытой двери).
        # Пока флажок едет, её не ищем: без нажатия на дверь окно не откроется, а каждый поиск — лишний снимок (задача 10)
        if door.first_seen is None and get_match_loc('btn_attack.png', window_rect, sct, 0.68):
            return "ROOM_SELECTION"
            
        # 2. Приоритет 2: Флаг двери (перехватывает фокус до чекпоинта)
        flag = get_match_info('flag_enter.png', window_rect, sct, CONFIDENCE_THRESHOLD)
        if flag:
            if not door.update((flag["x"], flag["y"])):
                time.sleep(0.05)  # флажок ещё едет — смотрим следующий снимок
                continue
            if door.gave_up:
                print("[НАВИГАЦИЯ] Флажок так и не замер — жму как есть.")
            print("[НАВИГАЦИЯ] Дверь зафиксирована. Начинаю вход...")
            door_xy = click_point_from_info('flag_enter.png', flag, window_rect)
            tap = click_human(door_xy[0], door_xy[1], seen_at=door.first_seen)
            
            # Ждем окно выбора комнат. Отсчёт идёт от момента, когда нажатие дошло до телефона.
            # Паузы 0,2 + 0,2 с «дать окну успокоиться» больше нет: find_smart_door сам проверит, что кнопки стоят на месте
            opened = wait_after_tap('btn_attack.png', window_rect, sct, tap, 0.68)
            if opened:
                print("[УСПЕХ] Окно выбора комнат открылось.")
                ROOM_WINDOW["seen"] = opened
                return "ROOM_SELECTION"
            else:
                print("[ОШИБКА] Окно атаки не появилось после клика в дверь (лаги?).")
                session_log.count("door_misses")
                return "HALLWAY" # Возвращаемся в цикл: флажок смотрим заново, без паузы
        door.reset()
                
        # 3. Приоритет 3: Точка сохранения (сработает ТОЛЬКО если нет флага двери)
        checkpoint_coords = get_match_loc('btn_activate.png', window_rect, sct, CONFIDENCE_THRESHOLD)
        if checkpoint_coords:
            print("[НАВИГАЦИЯ] Этаж пройден! Активируем точку сохранения...")
            # Время точки сохранения считаем отдельно, в «коридор» комнаты оно не входит
            with session_log.excluded("checkpoint"):
                click_human(checkpoint_coords[0], checkpoint_coords[1])

                print("[НАВИГАЦИЯ] Жду окно с наградой...")
                claim_coords = wait_for_ui_element('btn_claim.png', window_rect, sct, CONFIDENCE_THRESHOLD, timeout=8.0, settle_time=0.2)

                if claim_coords:
                    find_and_click_bulletproof('btn_claim.png', window_rect, sct, CONFIDENCE_THRESHOLD, timeout=4.0)
                    print("[НАВИГАЦИЯ] Награда забрана. Спускаемся на следующий этаж...")
                    wait_for_new_floor(window_rect, sct)
                    return "HALLWAY"
                else:
                    print("[ОШИБКА НАВИГАЦИИ] Окно с наградой так и не появилось.")
                    return "HALLWAY"
                
        time.sleep(0.1) # Сверхбыстрый поллинг экрана
        
    # Бот считает, что он в коридоре, а на экране выбор команды (например, не сработало нажатие «Авто»).
    # Раньше он в таком случае бесконечно искал дверь, теперь возвращается к выбору команды.
    if get_match_loc('btn_auto.png', window_rect, sct, CONFIDENCE_THRESHOLD) or \
       get_match_loc('btn_in_battle.png', window_rect, sct, CONFIDENCE_THRESHOLD):
        print("[НАВИГАЦИЯ] Вместо коридора виден экран выбора команды. Возвращаюсь к выбору команды...")
        return "SET_TEAM"

    # Бой закончился позже, чем бот его ждал (долгая загрузка), и окно результата уже на экране.
    # Раньше бот искал дверь под этим окном бесконечно (сессия 06, 18:01:55).
    if get_match_loc('btn_ok.png', window_rect, sct, CONFIDENCE_THRESHOLD):
        print("[НАВИГАЦИЯ] Вместо коридора виден экран результата боя. Перехожу к его обработке...")
        return "WAIT_FOR_OK"

    print("[НАВИГАЦИЯ] Таймаут в коридоре (10 сек). Перезапуск цикла...")
    return "HALLWAY"

def wait_for_new_floor(window_rect, sct):
    """После награды ждём не фиксированные 4 с, а появление флажка двери на новом этаже.
    Пока идёт спуск (~8–10 с), кнопка «Активировать» ещё видна, поэтому в коридор раньше не возвращаемся.
    Подвижную дверь дальше отсекает проверка «флажок стоит на месте»."""
    started = time.monotonic()
    while time.monotonic() - started < FLOOR_FLAG_WAIT_S:
        if get_match_info('flag_enter.png', window_rect, sct, CONFIDENCE_THRESHOLD):
            print(f"[НАВИГАЦИЯ] На новом этаже появилась дверь через {time.monotonic() - started:.1f} с после награды.")
            return
        time.sleep(0.1)
    print(f"[НАВИГАЦИЯ] Дверь на новом этаже не появилась за {FLOOR_FLAG_WAIT_S:.0f} с — продолжаю как есть.")
