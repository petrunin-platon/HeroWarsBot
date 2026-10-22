# combat.py
import cv2
import numpy as np
import time
import os
from config import CONFIG, CONFIDENCE_THRESHOLD, ALL_ACTIVE_TITANS, ENEMY_TITANS
from vision import click_human, get_match_loc, find_and_click_bulletproof, imread_cyrillic, wait_for_ui_element, \
    get_first_match, click_point_from_info, grab_frame
import vision
from analyzer import scan_enemy_team
import click_logic
import tactics
import rollback_logic
import session_log

# Подключаем движок правил для проверки запретов
from rules_engine import engine 

ACTION_THRESHOLD = 0.75 

def _find_attack_buttons(screenshot_cv, attack_template, scores=None):
    """Центры всех кнопок «Атаковать» на снимке (в координатах окна), слева направо.
    У каждой кнопки берётся точка с лучшим совпадением: так центр не скачет между снимками (задача 10).
    scores — словарь: в него пишется совпадение для каждого центра."""
    res, _ = vision.match_scores(screenshot_cv, attack_template, ACTION_THRESHOLD)  # быстрый поиск (задача 11)
    loc = np.where(res >= ACTION_THRESHOLD)
    h, w = attack_template.shape[:-1]
    best = {}  # центр первой найденной точки кнопки -> (совпадение, центр лучшей точки)
    for pt in zip(*loc[::-1]):
        center = (pt[0] + w // 2, pt[1] + h // 2)
        score = float(res[pt[1], pt[0]])
        key = next((k for k in best if abs(center[0] - k[0]) < 40), center)
        if key not in best or score > best[key][0]:
            best[key] = (score, center)
    buttons = sorted(center for _, center in best.values())
    if scores is not None:
        scores.update({center: score for score, center in best.values()})
    return buttons


def wait_room_window_still(window_rect, sct, attack_template, opened=None):
    """Окно выбора комнат могло ещё выезжать. Вместо пауз 0,2 + 0,2 с (задача 10) ждём, пока кнопки «Атаковать»
    на двух снимках подряд стоят на месте (снимки бот делает всё равно, чтобы разобрать двери).
    opened — (когда, центр кнопки) из navigation: снимок, где окно уже было видно после нажатия на дверь.
    Возвращает (снимок BGR, кнопки); кнопок нет и за 2 с не появились — список пустой; окно слишком мало — (None, [])."""
    tol = click_logic.DOOR_STABLE_TOL_PX * vision.GEOMETRY_CACHE.get("scale", 1.0)
    started = time.monotonic()
    prev_t, prev = (opened[0], [opened[1]]) if opened else (None, None)
    while True:
        if prev is not None:
            rest = click_logic.STILL_INTERVAL_S - (time.monotonic() - prev_t)
            if rest > 0:
                time.sleep(rest)
        shot_t = time.monotonic()
        screenshot_cv = cv2.cvtColor(grab_frame(window_rect, sct), cv2.COLOR_BGRA2BGR)

        # --- ФЕЙЛ-СЕЙФ: ЗАЩИТА ОТ КРАША OpenCV ПРИ СВЕРНУТОМ ОКНЕ ---
        if attack_template.shape[0] > screenshot_cv.shape[0] or attack_template.shape[1] > screenshot_cv.shape[1]:
            print("[СИСТЕМА CV] ВНИМАНИЕ: Окно свернуто или слишком мало! Увеличьте окно (или нажмите 'Сброс размера' в GUI).")
            return None, []
        # -------------------------------------------------------------

        buttons = _find_attack_buttons(screenshot_cv, attack_template)
        if prev and len(buttons) >= len(prev) and click_logic.spots_still(prev, buttons, tol):
            return screenshot_cv, buttons
        if shot_t - started >= click_logic.STILL_TIMEOUT_S:
            # Кнопок нет совсем — двери не найдены (main.py вернётся в коридор), как и раньше
            if buttons:
                print(f"[НАВИГАЦИЯ] Кнопки «Атаковать» не замерли за {click_logic.STILL_TIMEOUT_S:.0f} с — разбираю двери как есть.")
            return screenshot_cv, buttons
        prev_t, prev = shot_t, buttons  # кнопок ещё нет (окно проявляется) или они сдвинулись — смотрим следующий снимок


# ДОБАВЛЕН ПАРАМЕТР current_state
# door_hints — (heals, danger) для выбора двери по здоровью титанов (задача 9б, tactics.door_choice): main.py:door_hints
# opened — (когда, центр кнопки «Атаковать») из navigation.take_room_window(): окно уже видели после нажатия на дверь
def find_smart_door(window_rect, sct, current_state=None, door_hints=None, opened=None):
    if current_state is None:
        current_state = {}

    attack_template = imread_cyrillic('btn_attack.png')
    if attack_template is None: 
        return None, []

    # С этого момента считается пауза реакции перед «Атаковать» (задача 10)
    window_seen = opened[0] if opened else time.monotonic()
    screenshot_cv, attack_buttons = wait_room_window_still(window_rect, sct, attack_template, opened)
    if not attack_buttons:
        return None, []
        
    roi_w = int(screenshot_cv.shape[1] * 0.12)
    roi_h_up = int(screenshot_cv.shape[0] * 0.45)
    roi_h_down = int(screenshot_cv.shape[0] * 0.05)
    
    button_elements = []
    
    for bx, by in attack_buttons:
        x1 = max(0, bx - roi_w)
        x2 = min(screenshot_cv.shape[1], bx + roi_w)
        y1 = max(0, by - roi_h_up)
        y2 = min(screenshot_cv.shape[0], by + roi_h_down)
        
        roi = screenshot_cv[y1:y2, x1:x2]
        
        best_element = "unknown"
        highest_val = 0.0
        
        elements_to_check = [
            ("water", "icon_water.png"),
            ("mix", "icon_mix.png"), 
            ("earth", "icon_earth.png"), 
            ("fire", "icon_fire.png")
        ]
        
        for elem, icon in elements_to_check:
            tpl = imread_cyrillic(icon)
            if tpl is None: continue
            if tpl.shape[0] > roi.shape[0] or tpl.shape[1] > roi.shape[1]: continue
            
            res_roi = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res_roi)
            
            if max_val > highest_val:
                highest_val = max_val
                best_element = elem
                
        button_elements.append({
            "coords": (bx, by),
            "element": best_element if highest_val > 0.50 else "unknown",
            "score": highest_val
        })
        
    # Все двери в лог (слева направо), выбор — по порядку стихий из профиля (door_order) с учётом правил skip
    doors = sorted(button_elements, key=lambda b: b["coords"][0])
    print("[НАВИГАЦИЯ] Двери (слева направо): " + ", ".join(f"{b['element'].upper()} ({b['score']:.2f})" for b in doors))
    order = tactics.door_order(engine.get_global_setting("door_order"))
    elements = [b["element"] for b in button_elements]
    heals, danger = door_hints or (None, None)
    idx, allowed, skipped, health_note = tactics.door_choice(
        elements, order, lambda r: engine.is_room_forbidden(r, current_state), heals=heals, danger=danger)
    best_btn = button_elements[idx]["coords"]
    room_type = elements[idx]

    if len(button_elements) == 1:
        if not allowed:
            print(f"[НАВИГАЦИЯ] Комната {room_type.upper()} запрещена, но она единственная! Идем в бой.")
    else:
        if allowed:
            for r_type in skipped:
                print(f"[НАВИГАЦИЯ] Комната {r_type.upper()} под запретом (правило skip), пропускаю.")
            if health_note:
                print(f"[НАВИГАЦИЯ] Выбрана комната {room_type.upper()} по здоровью титанов: {health_note}")
            else:
                print(f"[НАВИГАЦИЯ] Выбрана комната {room_type.upper()} (порядок: {' → '.join(order)})")
        else:
            print(f"[НАВИГАЦИЯ] ВНИМАНИЕ: Все доступные двери под запретом! Вынужденный вход в {room_type.upper()}")

    if best_btn:
        local_x = best_btn[0]
        # Враги — на том же снимке, где окно уже замерло (задача 11): нового снимка не нужно
        enemies = scan_enemy_team(window_rect, sct, ENEMY_TITANS, local_x,
                                  screen=vision.game_area_of(screenshot_cv, window_rect))
        start_time = time.time()
        policy = None  # появляется после первого нажатия «Атаковать»
        still_shot = screenshot_cv  # первое нажатие — по этому снимку, без нового (задача 11)

        # Жмём один раз. Повтор — только если через click_logic.RETRY_AFTER_S после нажатия окно не отреагировало
        while True:
            elapsed = time.time() - start_time
            if os.path.exists("pause.flag"): return None, []

            if still_shot is not None:
                scr_cv, still_shot = still_shot, None
            else:
                scr = grab_frame(window_rect, sct)
                scr_cv = cv2.cvtColor(scr, cv2.COLOR_BGRA2BGR)
            dyn_scores = {}
            dyn_buttons = _find_attack_buttons(scr_cv, attack_template, dyn_scores)
            
            if not dyn_buttons:
                if policy is not None:
                    # Мы нажимали, а кнопки «Атаковать» больше нет — вошли в комнату
                    print(f"[КОМБАТ] Успешный вход. Комната: {room_type.upper()} | Враги: {enemies}")
                    return room_type, enemies
                if elapsed >= 8.0: break
                time.sleep(0.1)
                continue
            
            target_btn = min(dyn_buttons, key=lambda b: abs(b[0] - local_x))
            score = dyn_scores[target_btn]
            if policy is not None:
                if policy.observe(True, score, target_btn) == click_logic.WAIT:
                    time.sleep(0.1)
                    continue
                if elapsed >= 8.0: break
                print(f"[КОМБАТ] Нажатие на 'Атаковать' не сработало (экран не отреагировал {policy.seconds_since_tap():.1f} с). Повторяю...")
                session_log.count("repeat_clicks")
            
            tap_proc = click_human(window_rect["left"] + target_btn[0], window_rect["top"] + target_btn[1],
                                   seen_at=window_seen)
            policy = click_logic.RetryPolicy(click_logic.TapWatch(tap_proc, clock=time.monotonic),
                                             score, target_btn, clock=time.monotonic)
            local_x = target_btn[0] 
                
    return None, []

def execute_angus_ult(window_rect, sct):
    print("[АНГУС] Ожидаю загрузки боя (ищу блеклую кнопку Auto)...")
    start_time, saved_coords = time.time(), None
    
    roi_rect = {
        "top": window_rect["top"] + int(window_rect["height"] * 0.6),
        "left": window_rect["left"] + int(window_rect["width"] * 0.7),
        "width": int(window_rect["width"] * 0.3),
        "height": int(window_rect["height"] * 0.4)
    }
    
    while time.time() - start_time < 15.0:
        if os.path.exists("pause.flag"): return False
        saved_coords = get_match_loc('btn_round_auto_off.png', roi_rect, sct, CONFIDENCE_THRESHOLD)
        if saved_coords: break
        time.sleep(0.05) 
        
    if not saved_coords: return False
        
    # Пауза реакции (задача 10) — только перед первым нажатием: время ульты (1,8 с) не сдвигается
    battle_seen = time.monotonic()
    auto_x, auto_y = saved_coords
    print("[АНГУС] Бой начался! Включаю Auto...")
    click_human(auto_x, auto_y, seen_at=battle_seen)
    
    turned_on = False
    wait_start = time.time()
    while time.time() - wait_start < 1.5:
        if os.path.exists("pause.flag"): return False
        if get_match_loc('btn_round_auto_on.png', roi_rect, sct, 0.7):
            turned_on = True
            break
        time.sleep(0.05) 
        
    if not turned_on: click_human(auto_x, auto_y, seen_at=battle_seen)
        
    print("[АНГУС] УСПЕХ: Автобой ВКЛЮЧЕН. Жду 1.8 сек для ульты Ангуса...")
    # Тут можно не проверять, 1.8 сек быстро пролетят
    time.sleep(1.8)
    
    print("[АНГУС] Время вышло! Выключаю Auto (динамический поиск для рандомизации)...")
    active_coords = get_match_loc('btn_round_auto_on.png', roi_rect, sct, 0.7)
    
    if active_coords:
        click_human(active_coords[0], active_coords[1], seen_at=battle_seen)
    else:
        click_human(auto_x, auto_y, seen_at=battle_seen)
    
    turned_off = False
    wait_start = time.time()
    while time.time() - wait_start < 1.5:
        if os.path.exists("pause.flag"): return False
        if get_match_loc('btn_round_auto_off.png', roi_rect, sct, 0.75):
            turned_off = True
            break
        time.sleep(0.05)
        
    if not turned_off: 
        retry_coords = get_match_loc('btn_round_auto_on.png', roi_rect, sct, 0.7)
        if retry_coords:
            click_human(retry_coords[0], retry_coords[1], seen_at=battle_seen)
        else:
            click_human(auto_x, auto_y, seen_at=battle_seen)
        
    print("[АНГУС] УСПЕХ: Автобой ВЫКЛЮЧЕН.")
    return True

def execute_rollback(window_rect, sct, press_retry=True, on_game_wait=None):
    """Откат боя: «Ещё раз» → пауза (один раз) → «Отступить» → коридор. Шаги и ожидания — в rollback_logic.py.
    press_retry=False — бой уже идёт (умный старт), «Ещё раз» не нажимаем.
    on_game_wait() — один раз, когда экран долго не узнаётся и бот начал ждать игру (нет связи): скриншот для разбора.
    Возвращает rollback_logic.RollbackResult (в условии `if` ведёт себя как True/False)."""
    print("[ОТКАТ] Запускаю протокол отката боя...")

    if press_retry:
        if not find_and_click_bulletproof('btn_retry.png', window_rect, sct, ACTION_THRESHOLD, timeout=6.0):
            return rollback_logic.RollbackResult(rollback_logic.NO_RETRY, "Не найдена кнопка «Ещё раз».")
        print("[ОТКАТ] 'Ещё раз' нажата. Жду кнопку паузы (загрузка боя бывает долгой)...")

    pause_pos = {}

    # Порядок важен: пока меню паузы открыто, кнопка паузы тоже видна, поэтому «Отступить» проверяем первой
    screens = [
        (rollback_logic.RETREAT, ['btn_retreat.png'], ACTION_THRESHOLD),
        (rollback_logic.PAUSE, ['btn_pause.png'], ACTION_THRESHOLD),
        (rollback_logic.HALLWAY, ['flag_enter.png', 'btn_attack.png'], ACTION_THRESHOLD),
        (rollback_logic.RETRY, ['btn_retry.png'], ACTION_THRESHOLD),
        (rollback_logic.OK, ['btn_ok.png'], CONFIDENCE_THRESHOLD),
    ]

    def look():
        # Один снимок экрана на все проверки: так бот быстрее замечает кнопку паузы, когда бой загрузился
        found = get_first_match(screens, window_rect, sct)
        if found is None:
            return None
        label, name, info = found
        if label == rollback_logic.PAUSE:
            pause_pos["xy"] = click_point_from_info(name, info, window_rect)
        return label

    return rollback_logic.retreat_from_battle(
        look=look,
        tap_pause=lambda: click_human(pause_pos["xy"][0], pause_pos["xy"][1]),
        press_retreat=lambda: find_and_click_bulletproof('btn_retreat.png', window_rect, sct, ACTION_THRESHOLD, timeout=3.0),
        press_retry=lambda: find_and_click_bulletproof('btn_retry.png', window_rect, sct, ACTION_THRESHOLD, timeout=3.0),
        pause_flag_set=lambda: os.path.exists("pause.flag"),
        log=lambda text: print(f"[ОТКАТ] {text}"),
        clock=time.monotonic,
        sleep=time.sleep,
        on_game_wait=on_game_wait,
    )
