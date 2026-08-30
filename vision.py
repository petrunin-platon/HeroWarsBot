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

TEMPLATE_CACHE = {}

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

def get_asset_path(image_name):
    """
    Оставлено для обратной совместимости с combat.py и analyzer.py.
    """
    lang = CONFIG.get("game_language", "RU")
    lang_path = os.path.join(ASSETS_DIR, lang, image_name)
    if os.path.exists(lang_path):
        return lang_path
    return os.path.join(ASSETS_DIR, image_name)

def _calibrate_geometry(window_rect, sct):
    global GEOMETRY_CACHE
    if GEOMETRY_CACHE["is_calibrated"]:
        return

    screenshot = np.array(sct.grab(window_rect))
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

    # Новая базовая высота для сжатия под увеличенное окно
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

def get_clean_game_screen(window_rect, sct):
    if not GEOMETRY_CACHE["is_calibrated"] and window_rect["width"] > 800:
        _calibrate_geometry(window_rect, sct)

    screenshot = np.array(sct.grab(window_rect))
    screenshot_cv = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)

    if GEOMETRY_CACHE["is_calibrated"] and GEOMETRY_CACHE["game_h"] > 0:
        ox, oy = GEOMETRY_CACHE["offset_x"], GEOMETRY_CACHE["offset_y"]
        gw_rect, gh_rect = GEOMETRY_CACHE["game_w"], GEOMETRY_CACHE["game_h"]
        
        if window_rect["width"] > 800 and window_rect["height"] > 400:
            if oy+gh_rect <= screenshot_cv.shape[0] and ox+gw_rect <= screenshot_cv.shape[1]:
                clean_cv = screenshot_cv[oy:oy+gh_rect, ox:ox+gw_rect]
                clean_rect = {
                    "top": window_rect["top"] + oy,
                    "left": window_rect["left"] + ox,
                    "width": gw_rect,
                    "height": gh_rect
                }
                return clean_cv, clean_rect

    return screenshot_cv, window_rect

def get_image_data(image_name):
    lang = CONFIG.get("game_language", "RU")
    
    # Защита от старых вызовов: вытаскиваем имя файла из полного пути
    base_name = os.path.basename(image_name)
    
    if USE_DB:
        lang_key = f"{lang}/{base_name}"
        if lang_key in ASSETS:
            return base64.b64decode(ASSETS[lang_key])
        if base_name in ASSETS:
            return base64.b64decode(ASSETS[base_name])
            
    lang_path = os.path.join(ASSETS_DIR, lang, base_name)
    target_path = lang_path if os.path.exists(lang_path) else os.path.join(ASSETS_DIR, base_name)
    
    if os.path.exists(target_path):
        with open(target_path, "rb") as f:
            return f.read()
            
    return None

def get_scaled_template(image_name, scale):
    base_name = os.path.basename(image_name)
    cache_key = f"{base_name}_{scale:.3f}"
    
    if cache_key in TEMPLATE_CACHE:
        return TEMPLATE_CACHE[cache_key]

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
        TEMPLATE_CACHE[cache_key] = img
        
    return img

def imread_cyrillic(image_name):
    scale = GEOMETRY_CACHE.get("scale", 1.0)
    return get_scaled_template(image_name, scale)

def is_icon_present(image_name, screenshot_cv, threshold):
    """
    Восстановленная функция для определения комнат и врагов.
    Обеспечивает отказоустойчивость при проверке элементов UI.
    """
    template = imread_cyrillic(image_name)
    if template is None: 
        return False
        
    if template.shape[0] > screenshot_cv.shape[0] or template.shape[1] > screenshot_cv.shape[1]:
        return False
        
    res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    return max_val >= threshold

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
    if not GEOMETRY_CACHE["is_calibrated"] and window_rect["width"] > 800:
        _calibrate_geometry(window_rect, sct)

    screenshot = sct.grab(window_rect)
    screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGRA2BGR)
    
    if window_rect["width"] > 800 and GEOMETRY_CACHE["is_calibrated"]:
        ox, oy = GEOMETRY_CACHE["offset_x"], GEOMETRY_CACHE["offset_y"]
        gw_rect, gh_rect = GEOMETRY_CACHE["game_w"], GEOMETRY_CACHE["game_h"]
        if oy+gh_rect <= screenshot_cv.shape[0] and ox+gw_rect <= screenshot_cv.shape[1]:
            screenshot_cv = screenshot_cv[oy:oy+gh_rect, ox:ox+gw_rect]

    template = imread_cyrillic(image_name)
    if template is None: return None
    if template.shape[0] > screenshot_cv.shape[0] or template.shape[1] > screenshot_cv.shape[1]: return None

    res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    
    if max_val >= threshold:
        h, w = template.shape[:-1]
        if window_rect["width"] > 800:
            return (window_rect["left"] + GEOMETRY_CACHE["offset_x"] + max_loc[0] + w // 2,
                    window_rect["top"] + GEOMETRY_CACHE["offset_y"] + max_loc[1] + h // 2)
        else:
            return (window_rect["left"] + max_loc[0] + w // 2, window_rect["top"] + max_loc[1] + h // 2)
    return None

def find_and_click_bulletproof(image_name, window_rect, sct, threshold, timeout=6.0):
    coords = get_match_loc(image_name, window_rect, sct, threshold)
    if not coords: return False
        
    start_time = time.time()
    while time.time() - start_time < timeout:
        click_human(coords[0], coords[1])
        time.sleep(0.15) 
        if not get_match_loc(image_name, window_rect, sct, threshold): return True
    return False