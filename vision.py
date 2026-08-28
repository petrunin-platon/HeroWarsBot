# vision.py
import cv2
import numpy as np
import pyautogui
import time
import pygetwindow as gw
import os
import random
from config import CONFIG 

pyautogui.PAUSE = 0 

# ==============================================================================
# ИНТЕЛЛЕКТУАЛЬНЫЙ ПОИСК ПУТЕЙ (ДЛЯ ПОДДЕРЖКИ NUITKA .EXE)
# В режиме exe файл vision.py и папка assets лежат во временной директории ОС.
# os.path.abspath(__file__) всегда укажет точный путь к распакованным ассетам,
# не ломая при этом чтение rules/ и логов рядом с exe файлом.
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

# Кэш для шаблонов OpenCV (паттерн Singleton)
TEMPLATE_CACHE = {}

def get_asset_path(image_name):
    """
    Умный роутинг ассетов (паттерн Fallback).
    Сначала ищет картинку в папке текущего языка, затем в корне.
    """
    lang = CONFIG.get("game_language", "RU")
    lang_path = os.path.join(ASSETS_DIR, lang, image_name)
    
    if os.path.exists(lang_path):
        return lang_path
        
    return os.path.join(ASSETS_DIR, image_name)

def imread_cyrillic(path):
    """
    Безопасное чтение изображений по путям с кириллицей.
    Шаблоны кэшируются в оперативной памяти для ускорения RPA.
    """
    if path in TEMPLATE_CACHE:
        return TEMPLATE_CACHE[path]

    if not os.path.exists(path):
        return None
        
    with open(path, "rb") as f:
        chunk = f.read()
        
    chunk_arr = np.frombuffer(chunk, dtype=np.uint8)
    img = cv2.imdecode(chunk_arr, cv2.IMREAD_COLOR)
    
    if img is not None:
        TEMPLATE_CACHE[path] = img
        
    return img

def click_human(x, y, exact=False, jitter=4):
    """
    Плавный и уверенный клик с долгой фиксацией нажатия.
    exact=True - мгновенный точный клик (без смещений).
    jitter - радиус разброса пикселей от центра.
    """
    if exact:
        pyautogui.moveTo(x, y, duration=0.0)
        pyautogui.mouseDown()
        time.sleep(0.02)
        pyautogui.mouseUp()
        return

    # Динамический разброс, который можно менять для разных кнопок
    jitter_x = random.randint(-jitter, jitter)
    jitter_y = random.randint(-jitter, jitter)
    
    move_dur = random.uniform(0.15, 0.3)
    
    pyautogui.moveTo(x + jitter_x, y + jitter_y, duration=move_dur, tween=pyautogui.easeOutQuad)
    time.sleep(random.uniform(0.05, 0.1)) 
    
    pyautogui.mouseDown()
    time.sleep(random.uniform(0.1, 0.18)) 
    pyautogui.mouseUp()
    
    time.sleep(random.uniform(0.1, 0.2)) 

def swipe_scrcpy(window_rect, direction="down"):
    """Свайп (прокрутка) для Android через scrcpy"""
    center_x = window_rect["left"] + window_rect["width"] // 2
    top_y = window_rect["top"] + int(window_rect["height"] * 0.4)
    bottom_y = window_rect["top"] + int(window_rect["height"] * 0.6)
    
    start_y, end_y = (bottom_y, top_y) if direction == "down" else (top_y, bottom_y)
        
    pyautogui.moveTo(center_x, start_y)
    time.sleep(0.1)
    pyautogui.mouseDown()
    time.sleep(0.3) 
    pyautogui.moveTo(center_x, end_y, duration=0.6) 
    time.sleep(0.2) 
    pyautogui.mouseUp()
    time.sleep(0.5)

def get_window_rect(title):
    windows = gw.getWindowsWithTitle(title)
    if not windows:
        return None
    win = windows[0]
    if win.width < 100 or win.height < 100:
        return None
    return {"top": win.top, "left": win.left, "width": win.width, "height": win.height}

def get_match_loc(image_name, window_rect, sct, threshold):
    screenshot = sct.grab(window_rect)
    img = np.array(screenshot)
    screenshot_cv = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    
    path = get_asset_path(image_name)
    template = imread_cyrillic(path)
    if template is None: 
        print(f"[ОШИБКА АССЕТА] Не найден файл: {path}")
        return None
    
    res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    
    if max_val >= threshold:
        h, w = template.shape[:-1]
        return (window_rect["left"] + max_loc[0] + w // 2, window_rect["top"] + max_loc[1] + h // 2)
    return None

def is_icon_present(image_name, screenshot_cv, threshold):
    path = get_asset_path(image_name)
    template = imread_cyrillic(path)
    if template is None: 
        return False
        
    res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    return max_val >= threshold

def find_and_click_bulletproof(image_name, window_rect, sct, threshold, timeout=6.0):
    coords = get_match_loc(image_name, window_rect, sct, threshold)
    if not coords:
        return False
        
    global_x, global_y = coords
    print(f"[ДЕЙСТВИЕ] Вижу {image_name}. Начинаю прожатие...")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        click_human(global_x, global_y)
        
        pyautogui.moveTo(window_rect["left"] + 5, window_rect["top"] + 5, duration=0.1)
        time.sleep(0.15) 
        
        if not get_match_loc(image_name, window_rect, sct, threshold):
            print(f"[УСПЕХ] Кнопка {image_name} успешно прожата (исчезла).")
            return True
            
        print(f"[ПОВТОР] Клик не прошел. Жму {image_name} еще раз...")
        
    print(f"[ОШИБКА] Не удалось прожать {image_name} за {timeout} секунд.")
    return False