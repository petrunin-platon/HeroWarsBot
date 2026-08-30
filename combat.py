# combat.py
import cv2
import numpy as np
import time
import pyautogui
import pygetwindow as gw
from config import CONFIG, CONFIDENCE_THRESHOLD, ALL_ACTIVE_TITANS, ENEMY_TITANS
from vision import click_human, get_match_loc, is_icon_present, get_asset_path, find_and_click_bulletproof, imread_cyrillic
from analyzer import scan_enemy_team

ACTION_THRESHOLD = 0.75 

def combat_fast_click(target_x, target_y, safe_x, safe_y):
    pyautogui.moveTo(target_x, target_y, duration=0.0)
    pyautogui.mouseDown()
    time.sleep(0.03) 
    pyautogui.mouseUp()
    pyautogui.moveTo(safe_x, safe_y, duration=0.0)

def find_smart_door(window_rect, sct):
    screenshot = sct.grab(window_rect)
    img = np.array(screenshot)
    screenshot_cv = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    
    attack_template = imread_cyrillic(get_asset_path('btn_attack.png'))
    if attack_template is None: 
        return None, []
        
    res = cv2.matchTemplate(screenshot_cv, attack_template, cv2.TM_CCOEFF_NORMED)
    loc = np.where(res >= ACTION_THRESHOLD)
    
    attack_buttons = []
    h, w = attack_template.shape[:-1]
    
    for pt in zip(*loc[::-1]):
        center_x, center_y = pt[0] + w // 2, pt[1] + h // 2
        # Увеличена дистанция для фильтрации дублей кнопок на больших экранах
        if not any(abs(center_x - ax) < 40 for ax, ay in attack_buttons):
            attack_buttons.append((center_x, center_y))
            
    if not attack_buttons:
        return None, []
        
    # =====================================================================
    # НОВЫЙ АЛГОРИТМ: КОНКУРЕНТНОЕ ЗРЕНИЕ С ОГРАНИЧЕНИЕМ ЗОНЫ (ROI)
    # =====================================================================
    # Динамические рамки сканирования (зависят от размера окна)
    roi_w = int(screenshot_cv.shape[1] * 0.12)
    roi_h_up = int(screenshot_cv.shape[0] * 0.45)
    roi_h_down = int(screenshot_cv.shape[0] * 0.05)
    
    button_elements = []
    
    for bx, by in attack_buttons:
        # Вырезаем только зону строго вокруг/над кнопкой атаки
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
        
        # Примеряем все иконки и выбираем ту, у которой процент совпадения максимальный
        for elem, icon in elements_to_check:
            tpl = imread_cyrillic(get_asset_path(icon))
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
        
    # Выбираем приоритетную дверь (если их две)
    best_btn = None
    room_type = "unknown"
    
    if len(button_elements) == 1:
        best_btn = button_elements[0]["coords"]
        room_type = button_elements[0]["element"]
    else:
        # Приоритет: Вода -> Смешанная -> Земля -> Огонь
        priority_map = {"water": 1, "mix": 2, "earth": 3, "fire": 4, "unknown": 99}
        button_elements.sort(key=lambda b: priority_map[b["element"]])
        
        best_btn = button_elements[0]["coords"]
        room_type = button_elements[0]["element"]

    # =====================================================================
    # ЛОГИКА ВХОДА В КОМНАТУ
    # =====================================================================
    if best_btn:
        local_x = best_btn[0]
        enemies = scan_enemy_team(window_rect, sct, ENEMY_TITANS, local_x)
        start_time = time.time()
        
        while time.time() - start_time < 6.0:
            scr = np.array(sct.grab(window_rect))
            scr_cv = cv2.cvtColor(scr, cv2.COLOR_BGRA2BGR)
            res = cv2.matchTemplate(scr_cv, attack_template, cv2.TM_CCOEFF_NORMED)
            loc = np.where(res >= ACTION_THRESHOLD)
            
            dyn_buttons = []
            for pt in zip(*loc[::-1]):
                cx, cy = pt[0] + w // 2, pt[1] + h // 2
                if not any(abs(cx - ax) < 40 for ax, ay in dyn_buttons):
                    dyn_buttons.append((cx, cy))
            
            if dyn_buttons:
                target_btn = min(dyn_buttons, key=lambda b: abs(b[0] - local_x))
                click_human(window_rect["left"] + target_btn[0], window_rect["top"] + target_btn[1])
                local_x = target_btn[0] 
                
            pyautogui.moveTo(window_rect["left"] + 5, window_rect["top"] + 5, duration=0.0)
            time.sleep(0.15)
            
            if not get_match_loc('btn_attack.png', window_rect, sct, ACTION_THRESHOLD):
                print(f"[КОМБАТ] Комната идентифицирована: {room_type.upper()} | Враги: {enemies}")
                return room_type, enemies
                
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
        saved_coords = get_match_loc('btn_round_auto_off.png', roi_rect, sct, CONFIDENCE_THRESHOLD)
        if saved_coords: break
        time.sleep(0.01) 
        
    if not saved_coords: return False
        
    auto_x, auto_y = saved_coords
    print("[АНГУС] Бой начался! Включаю Auto (один точный клик)...")
    click_human(auto_x, auto_y)
    
    turned_on = False
    wait_start = time.time()
    while time.time() - wait_start < 1.5:
        if get_match_loc('btn_round_auto_on.png', roi_rect, sct, 0.7):
            turned_on = True
            break
        time.sleep(0.01) 
        
    if not turned_on: click_human(auto_x, auto_y)
        
    print("[АНГУС] УСПЕХ: Автобой ВКЛЮЧЕН. Жду 1.8 сек для ульты Ангуса...")
    time.sleep(1.8)
    
    print("[АНГУС] Время вышло! Выключаю Auto (один точный клик)...")
    click_human(auto_x, auto_y)
    
    turned_off = False
    wait_start = time.time()
    while time.time() - wait_start < 1.5:
        if get_match_loc('btn_round_auto_off.png', roi_rect, sct, 0.75):
            turned_off = True
            break
        time.sleep(0.01)
        
    if not turned_off: click_human(auto_x, auto_y)
        
    print("[АНГУС] УСПЕХ: Автобой ВЫКЛЮЧЕН.")
    return True


def execute_rollback(window_rect, sct):
    print("[ОТКАТ] Запускаю протокол отката боя...")
    
    if not find_and_click_bulletproof('btn_retry.png', window_rect, sct, ACTION_THRESHOLD):
        print("[ОТКАТ] Не найдена кнопка 'btn_retry.png'!")
        return False
        
    print("[ОТКАТ] 'Ещё раз' нажата. Начинаю перехват паузы (до 3 попыток)...")
    
    safe_x = window_rect["left"] + 5
    safe_y = window_rect["top"] + 5
    pause_found = False
    
    for attempt in range(1, 4):
        print(f"[ОТКАТ] Итерация {attempt}/3: Возвращаю фокус окну...")
        try:
            windows = gw.getWindowsWithTitle("HeroWarsBot_Arena")
            if windows:
                win = windows[0]
                if win.isMinimized: win.restore()
                win.activate()
                time.sleep(0.5)
        except Exception as e:
            print(f"[ОТКАТ] Ошибка фокуса: {e}")

        start_time = time.time()
        while time.time() - start_time < 15.0:
            coords = get_match_loc('btn_pause.png', window_rect, sct, 0.75) 
            if coords:
                print("[ОТКАТ] Перехват: спамлю сверхбыстрые клики по паузе...")
                for _ in range(3):
                    combat_fast_click(coords[0], coords[1], safe_x, safe_y)
                    time.sleep(0.05)
                pause_found = True
                break
            time.sleep(0.15)
            
        if pause_found:
            break
            
    if not pause_found:
        print("[ОТКАТ] ФАТАЛЬНАЯ ОШИБКА: Пауза не появилась за 3 попытки!")
        return False
        
    print("[ОТКАТ] Выдерживаю 1.5 сек для полной отрисовки меню паузы...")
    time.sleep(1.5) 
    
    if not find_and_click_bulletproof('btn_retreat.png', window_rect, sct, ACTION_THRESHOLD):
        print("[ОТКАТ] ОШИБКА: Не найдена кнопка 'btn_retreat.png' в меню паузы!")
        return False
        
    print("[ОТКАТ] Успешно нажато 'Отступить'. Жду интерфейс коридора...")
    
    hallway_start = time.time()
    while time.time() - hallway_start < 15.0:
        if get_match_loc('flag_enter.png', window_rect, sct, 0.75) or get_match_loc('btn_attack.png', window_rect, sct, 0.75):
            print("[ОТКАТ] Возврат в коридор подтвержден. Боевые флаги сброшены.")
            return True
        time.sleep(0.2)
        
    print("[ОТКАТ] ВНИМАНИЕ: Не увидели интерфейс коридора за 15 сек, но откат произведен.")
    return True