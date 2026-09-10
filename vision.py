# vision.py
import cv2
import numpy as np
import time
import pygetwindow as gw
import os
import random
import sys
import subprocess
import re
import base64
from functools import lru_cache
from config import CONFIG

# Пытаемся импортировать упакованные ассеты
try:
    from assets_db import ASSETS
    USE_DB = True
except ImportError:
    USE_DB = False
    ASSETS = {}
    print("[СИСТЕМА CV] Файл assets_db.py не найден. Использую чтение с диска.")

def get_base_dir():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

GEOMETRY_CACHE = {
    "is_calibrated": False,
    "offset_x": 0,
    "offset_y": 0,
    "game_w": 0,
    "game_h": 0,
    "scale": 1.0
}

LAST_WINDOW_RECT = None
DEVICE_RES = {"w": 0, "h": 0}

def get_device_resolution():
    if DEVICE_RES["w"] > 0:
        return DEVICE_RES["w"], DEVICE_RES["h"]
    try:
        out = subprocess.check_output(["adb", "shell", "wm", "size"], text=True, creationflags=0x08000000)
        match = re.search(r"(\d+)x(\d+)", out)
        if match:
            w, h = int(match.group(1)), int(match.group(2))
            DEVICE_RES["w"] = max(w, h)
            DEVICE_RES["h"] = min(w, h)
            return DEVICE_RES["w"], DEVICE_RES["h"]
    except Exception:
        pass
    return 1920, 1080 

def _calibrate_geometry(screenshot):
    global GEOMETRY_CACHE
    if GEOMETRY_CACHE["is_calibrated"]:
        return

    # Захват экрана удален. Используем ГОТОВЫЙ переданный массив пикселей!
    gray = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2GRAY)

    title_bar_h = 36 
    border_w = 8
    h, w = gray.shape

    crop_y1, crop_y2 = title_bar_h, h - border_w
    crop_x1, crop_x2 = border_w, w - border_w

    if crop_y1 >= crop_y2 or crop_x1 >= crop_x2:
        return 

    safe_roi = gray[crop_y1:crop_y2, crop_x1:crop_x2]
    _, thresh = cv2.threshold(safe_roi, 15, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours or len(contours) == 0:
        return

    c = max(contours, key=cv2.contourArea)
    x, y, gw_rect, gh_rect = cv2.boundingRect(c)

    if gw_rect < 200 or gh_rect < 200:
        return

    BASE_GAME_HEIGHT = 720.0
    scale_factor = gh_rect / BASE_GAME_HEIGHT

    GEOMETRY_CACHE = {
        "is_calibrated": True,
        "offset_x": crop_x1 + x,
        "offset_y": crop_y1 + y,
        "game_w": gw_rect,
        "game_h": gh_rect,
        "scale": scale_factor
    }
    print(f"\n[СИСТЕМА CV] Геометрия откалибрована (Масштаб: {scale_factor:.3f}x)")
    print(f" ---> Истинный размер игры: {gw_rect}x{gh_rect}\n")


def _crop_screenshot_to_game_area(window_rect, sct):
    """Приватная функция для применения кэша геометрии и обрезки экрана."""
    # 1. Сначала делаем ЕДИНСТВЕННЫЙ захват экрана для всего такта!
    screenshot = np.array(sct.grab(window_rect))
    
    # 2. Передаем ГОТОВЫЙ скриншот в калибратор (если он еще не откалиброван)
    if not GEOMETRY_CACHE["is_calibrated"] and window_rect["width"] > 800:
        _calibrate_geometry(screenshot)

    # 3. Продолжаем обычную работу с уже имеющимся кадром
    screenshot_cv = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)

    ox, oy = 0, 0
    gw_rect, gh_rect = window_rect["width"], window_rect["height"]

    if GEOMETRY_CACHE["is_calibrated"] and GEOMETRY_CACHE["game_h"] > 0 and window_rect["width"] > 800:
        cache_ox, cache_oy = GEOMETRY_CACHE["offset_x"], GEOMETRY_CACHE["offset_y"]
        cache_gw, cache_gh = GEOMETRY_CACHE["game_w"], GEOMETRY_CACHE["game_h"]
        
        # Проверяем, не выходят ли границы за пределы скриншота
        if cache_oy + cache_gh <= screenshot_cv.shape[0] and cache_ox + cache_gw <= screenshot_cv.shape[1]:
            screenshot_cv = screenshot_cv[cache_oy:cache_oy + cache_gh, cache_ox:cache_ox + cache_gw]
            ox, oy = cache_ox, cache_oy
            gw_rect, gh_rect = cache_gw, cache_gh

    return screenshot_cv, ox, oy, gw_rect, gh_rect

def get_clean_game_screen(window_rect, sct):
    screenshot_cv, ox, oy, gw_rect, gh_rect = _crop_screenshot_to_game_area(window_rect, sct)

    if ox > 0 or oy > 0:
        clean_rect = {
            "top": window_rect["top"] + oy,
            "left": window_rect["left"] + ox,
            "width": gw_rect,
            "height": gh_rect
        }
        return screenshot_cv, clean_rect

    return screenshot_cv, window_rect

def get_image_data(image_name):
    lang = CONFIG.get("game_language", "RU")
    
    if USE_DB:
        lang_key = f"{lang}/{image_name}"
        if lang_key in ASSETS:
            return base64.b64decode(ASSETS[lang_key])
        if image_name in ASSETS:
            return base64.b64decode(ASSETS[image_name])
            
    lang_path = os.path.join(ASSETS_DIR, lang, image_name)
    target_path = lang_path if os.path.exists(lang_path) else os.path.join(ASSETS_DIR, image_name)
    
    if os.path.exists(target_path):
        with open(target_path, "rb") as f:
            return f.read()
            
    return None

@lru_cache(maxsize=256)
def get_scaled_template(image_name, scale):
    img_bytes = get_image_data(image_name)
    if not img_bytes:
        return None
        
    chunk_arr = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(chunk_arr, cv2.IMREAD_COLOR)
    
    if img is not None:
        if scale != 1.0 and 0.5 < scale < 2.0:
            new_w = max(1, int(img.shape[1] * scale))
            new_h = max(1, int(img.shape[0] * scale))
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
            
    return img

def imread_cyrillic(image_name):
    scale = GEOMETRY_CACHE.get("scale", 1.0)
    return get_scaled_template(image_name, scale)

def click_human(x, y, exact=False, jitter=4):
    global LAST_WINDOW_RECT
    if not LAST_WINDOW_RECT or not GEOMETRY_CACHE["is_calibrated"]:
        return

    game_w = GEOMETRY_CACHE["game_w"]
    game_h = GEOMETRY_CACHE["game_h"]
    
    if game_w == 0 or game_h == 0: return

    pct_x = (x - LAST_WINDOW_RECT["left"] - GEOMETRY_CACHE["offset_x"]) / game_w
    pct_y = (y - LAST_WINDOW_RECT["top"] - GEOMETRY_CACHE["offset_y"]) / game_h

    real_w, real_h = get_device_resolution()

    tap_x = int(pct_x * real_w)
    tap_y = int(pct_y * real_h)

    if not exact:
        phone_jitter = int(jitter * (real_w / game_w))
        tap_x += random.randint(-phone_jitter, phone_jitter)
        tap_y += random.randint(-phone_jitter, phone_jitter)
        
    subprocess.Popen(["adb", "shell", "input", "tap", str(tap_x), str(tap_y)], creationflags=0x08000000)
    time.sleep(0.1 if exact else random.uniform(0.1, 0.2))

def swipe_scrcpy(window_rect, direction="down"):
    real_w, real_h = get_device_resolution()
    start_x = int(0.3 * real_w) 
    
    if direction == "down":
        start_y, end_y = int(0.7 * real_h), int(0.3 * real_h)
    else:
        start_y, end_y = int(0.3 * real_h), int(0.7 * real_h)
        
    subprocess.Popen(["adb", "shell", "input", "swipe", str(start_x), str(start_y), str(start_x), str(end_y), "400"], creationflags=0x08000000)
    time.sleep(0.6) 

def get_window_rect(title):
    global LAST_WINDOW_RECT
    windows = gw.getWindowsWithTitle(title)
    if not windows: return None
    win = windows[0]
    if win.width < 100: return None
    LAST_WINDOW_RECT = {"top": win.top, "left": win.left, "width": win.width, "height": win.height}
    return LAST_WINDOW_RECT

def get_match_loc(image_name, window_rect, sct, threshold):
    screenshot_cv, ox, oy, _, _ = _crop_screenshot_to_game_area(window_rect, sct)

    template = imread_cyrillic(image_name)
    if template is None: return None
    if template.shape[0] > screenshot_cv.shape[0] or template.shape[1] > screenshot_cv.shape[1]: return None

    res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    
    if max_val >= threshold:
        h, w = template.shape[:-1]
        scale = GEOMETRY_CACHE.get("scale", 1.0)
        
        # =====================================================================
        # ИНТЕЛЛЕКТУАЛЬНАЯ РАНДОМИЗАЦИЯ КЛИКОВ (ЗАЩИТА ОТ ДЕТЕКТА)
        # =====================================================================
        if "flag_enter" in image_name:
            # ИСКЛЮЧЕНИЕ: Логика для дверей 
            door_w = int(165 * scale)
            door_h = int(245 * scale)
            
            # Центр флага по оси X
            center_x = max_loc[0] + w // 2
            
            # Границы красной зоны
            start_x = center_x - door_w // 2
            end_x = center_x + door_w // 2
            start_y = max_loc[1] + h 
            end_y = start_y + door_h
            
            # 10% отступа внутрь от границ красной зоны для безопасности
            margin_x = int(door_w * 0.1)
            margin_y = int(door_h * 0.1)
            
            rand_x = random.randint(start_x + margin_x, end_x - margin_x)
            rand_y = random.randint(start_y + margin_y, end_y - margin_y)
            
        else:
            # СТАНДАРТНАЯ КНОПКА: Отсекаем по 20% с каждого края
            margin_x = max(1, int(w * 0.2))
            margin_y = max(1, int(h * 0.2))
            
            # Защита на случай крошечных кнопок (отключаем отступ, если кнопка слишком мала)
            if margin_x * 2 >= w: margin_x = 0
            if margin_y * 2 >= h: margin_y = 0
            
            rand_x = random.randint(max_loc[0] + margin_x, max_loc[0] + w - margin_x)
            rand_y = random.randint(max_loc[1] + margin_y, max_loc[1] + h - margin_y)
        # =====================================================================
        
        # Универсальный возврат (ox и oy будут нулевыми, если обрезка не применялась)
        return (window_rect["left"] + ox + rand_x,
                window_rect["top"] + oy + rand_y)
            
    return None

def find_and_click_bulletproof(image_name, window_rect, sct, threshold, timeout=6.0):
    """
    Человечный и надежный клик с защитой от непрокликивания.
    """
    start_time = time.time()
    clicked = False
    
    while time.time() - start_time < timeout:
        coords = get_match_loc(image_name, window_rect, sct, threshold)
        if not coords:
            if clicked:
                # Если мы уже кликали, а кнопка пропала - это 100% успех
                return True
            time.sleep(0.1)
            continue
            
        # Доверяем твоей родной математике из get_match_loc (обрезание 20% краев)
        click_human(coords[0], coords[1])
        clicked = True
        
        # Задержка рандомизирована, глобальный модуль random загружен в начале файла
        time.sleep(random.uniform(0.5, 0.8))
        
        if not get_match_loc(image_name, window_rect, sct, threshold):
            return True 
            
        print(f"[VISION] Клик по '{image_name}' не зарегистрирован сервером. Повторяю...")
        
    print(f"[VISION] Ошибка: Не удалось прожать '{image_name}' за {timeout} сек.")
    return False

def wait_for_ui_element(template_name, window_rect, sct, threshold=0.75, timeout=10.0, poll_rate=0.05, settle_time=0.0):
    """
    Умное ожидание элемента интерфейса с защитой от анимаций.
    
    :param settle_time: Время (в секундах), которое нужно подождать ПОСЛЕ первого 
                        обнаружения элемента, чтобы дать анимации (выезд кнопки/окна) завершиться.
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # Первичное обнаружение
        coords = get_match_loc(template_name, window_rect, sct, threshold)
        
        if coords:
            if settle_time > 0:
                # Даем интерфейсу "успокоиться" и доехать до конца
                time.sleep(settle_time)
                # Делаем контрольный выстрел - пересчитываем координаты после остановки!
                coords_final = get_match_loc(template_name, window_rect, sct, threshold)
                if coords_final:
                    return coords_final
                else:
                    # Если после паузы кнопка исчезла (например, это был блик) - продолжаем искать
                    continue 
            
            return coords # Если settle_time == 0, возвращаем мгновенно
            
        time.sleep(poll_rate)
        
    # Если вышли из цикла, значит время вышло
    print(f"[VISION] Таймаут: элемент '{template_name}' не появился за {timeout} сек.")
    return None