import time
import pyautogui
from config import CONFIDENCE_THRESHOLD
from vision import click_human, get_match_loc, find_and_click_bulletproof

TITAN_THRESHOLD = 0.88 

# ПОЛНЫЙ список всех титанов в игре
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

def smart_swipe(window_rect, direction="down"):
    left = window_rect["left"]
    top = window_rect["top"]
    w = window_rect["width"]
    h = window_rect["height"]

    start_x = left + int(w * 0.25) 
    
    if direction == "down":
        start_y = top + int(h * 0.7)
        end_y = top + int(h * 0.4)
    else:
        start_y = top + int(h * 0.4)
        end_y = top + int(h * 0.7)

    pyautogui.moveTo(start_x, start_y, duration=0.1) 
    pyautogui.mouseDown() 
    time.sleep(0.4) 
    
    pyautogui.moveTo(start_x, end_y, duration=0.8) 
    
    time.sleep(0.2) 
    pyautogui.mouseUp() 
    time.sleep(0.5) 

def open_grid_if_needed(window_rect, sct):
    print("[КОМАНДА] Ожидаю окончания анимации окна (1.5 сек)...")
    time.sleep(1.5) 
    
    start_time = time.time()
    while time.time() - start_time < 8.0:
        if get_match_loc('btn_4_dots.png', window_rect, sct, CONFIDENCE_THRESHOLD):
            print("[КОМАНДА] Сетка титанов открыта и готова к работе.")
            time.sleep(0.5) 
            return True
            
        coords_9 = get_match_loc('btn_9_dots.png', window_rect, sct, CONFIDENCE_THRESHOLD)
        if coords_9:
            print("[КОМАНДА] Сетка свернута. Нажимаю открыть...")
            click_human(coords_9[0], coords_9[1])
            pyautogui.moveTo(window_rect["left"] + 5, window_rect["top"] + 5, duration=0.1)
            time.sleep(1.5) 
        else:
            time.sleep(0.2)
            
    print("[ОШИБКА КОМАНДЫ] Не смог убедиться, что сетка открыта (не вижу 4 точки)!")
    return False

def precise_select_titan(x, y, safe_x, safe_y):
    """Супер-надежный клик для выбора титанов с долгими паузами (обход лагов scrcpy)"""
    pyautogui.moveTo(x, y, duration=0.2)
    time.sleep(0.3) # Подвели и ждем, чтобы Android зафиксировал курсор
    pyautogui.mouseDown()
    time.sleep(0.15)
    pyautogui.mouseUp()
    time.sleep(0.3) # Кликнули и ждем анимации
    pyautogui.moveTo(safe_x, safe_y, duration=0.2) # Отводим в сейф-зону
    time.sleep(0.5) # Ждем перед следующим действием

def verify_and_set_team(target_pack, available_titans, window_rect, sct):
    top_roi, bottom_roi = get_rois(window_rect)
    open_grid_if_needed(window_rect, sct)
    
    safe_mouse_x = window_rect["left"] + 5
    safe_mouse_y = window_rect["top"] + 5

    sorted_pack = [t for t in GAME_ORDER if t in target_pack]
    for t in target_pack: 
        if t not in sorted_pack: sorted_pack.append(t)

    for attempt in range(1, 4):
        print(f"\n[КОМАНДА] --- Попытка сборки {attempt}/3 ---")
        
        smart_swipe(window_rect, direction="up") 
        time.sleep(0.5)
        smart_swipe(window_rect, direction="up") 
        
        # 1. УДАЛЕНИЕ ЛИШНИХ
        print("[КОМАНДА] Очищаю слоты от нежелательных титанов...")
        for titan in GAME_ORDER:
            if titan not in sorted_pack:
                coords = get_match_loc(f"{titan}.png", bottom_roi, sct, TITAN_THRESHOLD)
                if coords:
                    print(f"[КОМАНДА] Убираю: {titan}")
                    precise_select_titan(coords[0], coords[1], safe_mouse_x, safe_mouse_y)
                    
        # 2. ДОБАВЛЕНИЕ НУЖНЫХ
        print(f"[КОМАНДА] Добавляю состав: {sorted_pack}")
        for titan in sorted_pack:
            if get_match_loc(f"{titan}.png", bottom_roi, sct, TITAN_THRESHOLD):
                print(f"[КОМАНДА] -> {titan} уже на месте.")
                continue
                
            print(f"[КОМАНДА] -> Ищу {titan} в текущей видимой зоне...")
            coords = get_match_loc(f"{titan}.png", top_roi, sct, TITAN_THRESHOLD)
            if coords:
                precise_select_titan(coords[0], coords[1], safe_mouse_x, safe_mouse_y)
                continue
                
            print(f"[КОМАНДА] -> Не вижу. Скроллю список ВНИЗ...")
            smart_swipe(window_rect, direction="down")
            
            coords = get_match_loc(f"{titan}.png", top_roi, sct, TITAN_THRESHOLD)
            if coords:
                precise_select_titan(coords[0], coords[1], safe_mouse_x, safe_mouse_y)
            else:
                print(f"[ОШИБКА] Не нашел {titan} в этой зоне. Соберу на следующем проходе.")

        # 3. ФИНАЛЬНЫЙ КОНТРОЛЬ
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
        else:
            print("[КОМАНДА] Обнаружены ошибки состава. Запускаю корректировку...")
            
    print("[ФАТАЛЬНАЯ ОШИБКА КОМАНДЫ] Не удалось собрать правильный состав за 3 попытки!")
    return False