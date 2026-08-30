# team_manager.py
import time
from config import CONFIDENCE_THRESHOLD
from vision import click_human, get_match_loc, find_and_click_bulletproof, swipe_scrcpy

TITAN_THRESHOLD = 0.88 

GAME_ORDER = [
    "hyperion", "sigurd", "nova", "mairi", "tidus", "orm",
    "eden", "angus", "avalon", "silva", "verdok", "pallant",
    "araji", "moloch", "vulcan", "ignis", "acheron", "alecto",
    "solaris", "rigel", "iyari", "amon", "lumira",
    "tenebris", "brustar", "keros", "mor", "umbra"
]

def get_rois(window_rect):
    h = window_rect["height"]
    top_h = int(h * 0.75) 
    
    top_roi = {
        "top": window_rect["top"], 
        "left": window_rect["left"], 
        "width": window_rect["width"], 
        "height": top_h
    }
    bottom_roi = {
        "top": window_rect["top"] + top_h, 
        "left": window_rect["left"], 
        "width": window_rect["width"], 
        "height": h - top_h
    }
    return top_roi, bottom_roi

def open_grid_if_needed(window_rect, sct):
    print("[КОМАНДА] Ожидаю окончания анимации окна (1.5 сек)...")
    time.sleep(1.5) 
    
    start_time = time.time()
    while time.time() - start_time < 8.0:
        if get_match_loc('btn_4_dots.png', window_rect, sct, 0.7):
            print("[КОМАНДА] Сетка титанов открыта и готова к работе.")
            time.sleep(0.3) 
            return True
            
        coords_9 = get_match_loc('btn_9_dots.png', window_rect, sct, 0.7)
        if coords_9:
            print("[КОМАНДА] Сетка свернута. Нажимаю открыть (через ADB)...")
            click_human(coords_9[0], coords_9[1], exact=True)
            time.sleep(1.2) 
        else:
            time.sleep(0.2)
            
    print("[ОШИБКА КОМАНДЫ] Не смог убедиться, что сетка открыта (не вижу 4 точки)!")
    return False

def precise_select_titan(x, y):
    """Снайперский точный клик по титану (через ADB)"""
    click_human(x, y, exact=True)
    time.sleep(0.15) # Ускорено 

def verify_and_set_team(target_pack, available_titans, window_rect, sct):
    top_roi, bottom_roi = get_rois(window_rect)
    open_grid_if_needed(window_rect, sct)

    sorted_pack = [t for t in GAME_ORDER if t in target_pack]
    for t in target_pack: 
        if t not in sorted_pack: sorted_pack.append(t)

    print(f"\n[КОМАНДА] Начинаю сборку состава: {sorted_pack}")
    
    # ВОЗВРАТ В НАЧАЛО СЕТКИ: Делаем 2 свайпа аппаратно через ADB
    swipe_scrcpy(window_rect, direction="up") 
    time.sleep(0.1)
    swipe_scrcpy(window_rect, direction="up") 
    
    # 1. МЕХАНИКА ОЧИСТКИ (Максимум 3 прохода)
    print("[КОМАНДА] Очищаю слоты от нежелательных титанов...")
    for cleanup_pass in range(1, 4):
        cleared_all = True
        for titan in GAME_ORDER:
            if titan not in sorted_pack:
                coords = get_match_loc(f"{titan}.png", bottom_roi, sct, TITAN_THRESHOLD)
                if coords:
                    print(f"[КОМАНДА] Убираю: {titan} (проход {cleanup_pass}/3)")
                    precise_select_titan(coords[0], coords[1])
                    cleared_all = False
        if cleared_all:
            break
        time.sleep(0.3)

    # 2. МЕХАНИКА ПОИСКА (Ровно 2 свайпа, как ты и просил)
    for titan in sorted_pack:
        if get_match_loc(f"{titan}.png", bottom_roi, sct, TITAN_THRESHOLD):
            print(f"[КОМАНДА] -> {titan} уже на месте.")
            continue
            
        print(f"[КОМАНДА] -> Ищу {titan}...")
        
        found = False
        for swipe_idx in range(3): # 0 = без свайпа, 1 = первый свайп, 2 = второй свайп
            coords = get_match_loc(f"{titan}.png", top_roi, sct, TITAN_THRESHOLD)
            if coords:
                precise_select_titan(coords[0], coords[1])
                found = True
                break
            
            if swipe_idx < 2:
                print(f"[КОМАНДА] -> Не вижу. Делаю свайп ВНИЗ ({swipe_idx + 1}/2)...")
                swipe_scrcpy(window_rect, direction="down")
                
        if not found:
            print(f"[ОШИБКА] Не нашел {titan} даже после 2 свайпов!")

    # 3. КОНТРОЛЬНАЯ ПРОВЕРКА
    print("[КОМАНДА] Выполняю контрольную проверку состава...")
    all_perfect = True
    
    for titan in sorted_pack:
        if not get_match_loc(f"{titan}.png", bottom_roi, sct, TITAN_THRESHOLD):
            print(f"[ПРОВЕРКА] Провал: {titan} отсутствует в слотах!")
            all_perfect = False
            
    for titan in GAME_ORDER:
        if titan not in sorted_pack and get_match_loc(f"{titan}.png", bottom_roi, sct, TITAN_THRESHOLD):
            print(f"[ПРОВЕРКА] Провал: {titan} остался в слотах, хотя его там быть не должно!")
            all_perfect = False
            
    if all_perfect:
        print("[КОМАНДА] Состав ИДЕАЛЬНО укомплектован!")
        return True
        
    print("[ФАТАЛЬНАЯ ОШИБКА КОМАНДЫ] Не удалось собрать правильный состав!")
    return False