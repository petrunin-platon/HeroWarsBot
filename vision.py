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
import session_log
import click_logic
import stuck_guard
from contextlib import ExitStack
try:
    from mss.exception import ScreenShotError
except ImportError:  # в облачных тестах mss нет
    class ScreenShotError(Exception):
        pass

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


# Что делать, когда экран долго недоступен и когда он снова работает. Задаёт main.py (Telegram, сторож)
SCREEN_HOOKS = {"long_wait": None, "resumed": None}


def grab_frame(window_rect, sct):
    """Снимок окна игры (numpy-массив BGRA). Все снимки бота идут через эту функцию.
    Если ПК заблокирован (Win+L) и снимок не получается, бот не падает, а ждёт разблокировки.
    Время ожидания в замеры комнаты не идёт (отдельный счётчик «экран заблокирован»)."""
    excluded = ExitStack()

    def resumed(seconds):
        excluded.close()
        if SCREEN_HOOKS["resumed"]:
            SCREEN_HOOKS["resumed"](seconds)

    try:
        return np.array(stuck_guard.grab_or_wait(
            lambda: sct.grab(window_rect), ScreenShotError,
            on_blocked=lambda: excluded.enter_context(session_log.excluded("screen_lock")),
            on_long_wait=SCREEN_HOOKS["long_wait"],
            on_resumed=resumed))
    finally:
        excluded.close()


def _crop_screenshot_to_game_area(window_rect, sct):
    """Приватная функция для применения кэша геометрии и обрезки экрана."""
    # 1. Сначала делаем ЕДИНСТВЕННЫЙ захват экрана для всего такта!
    screenshot = grab_frame(window_rect, sct)
    
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

def list_root_asset_names():
    """Имена картинок (без .png) из корня assets/ — не из папок языков. Берёт и assets_db.py, и папку на диске,
    потому что в собранном .exe картинки лежат в assets_db.py, а при запуске из исходников — в assets/."""
    names = set()
    for key in ASSETS:
        if "/" not in key and "\\" not in key and key.lower().endswith(".png"):
            names.add(key[:-4])
    if os.path.isdir(ASSETS_DIR):
        for f in os.listdir(ASSETS_DIR):
            if f.lower().endswith(".png") and os.path.isfile(os.path.join(ASSETS_DIR, f)):
                names.add(f[:-4])
    return names

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

# Пауза перед нажатием (задача 10): реакция 0,3–0,8 с после появления кнопки и не больше 2 нажатий в секунду
TAP_PACER = click_logic.TapPacer()

def click_human(x, y, exact=False, jitter=4, seen_at=None):
    global LAST_WINDOW_RECT
    """Нажимает через adb. Возвращает процесс нажатия (по нему видно, когда команда дошла до телефона)
    или None, если нажать не удалось.
    seen_at — когда кнопка появилась на экране (time.monotonic()): от него считается пауза реакции.
    None — кнопка только что найдена, пауза реакции целиком."""
    if not LAST_WINDOW_RECT or not GEOMETRY_CACHE["is_calibrated"]:
        return None

    game_w = GEOMETRY_CACHE["game_w"]
    game_h = GEOMETRY_CACHE["game_h"]
    
    if game_w == 0 or game_h == 0: return None

    pct_x = (x - LAST_WINDOW_RECT["left"] - GEOMETRY_CACHE["offset_x"]) / game_w
    pct_y = (y - LAST_WINDOW_RECT["top"] - GEOMETRY_CACHE["offset_y"]) / game_h

    real_w, real_h = get_device_resolution()

    tap_x = int(pct_x * real_w)
    tap_y = int(pct_y * real_h)

    if not exact:
        phone_jitter = int(jitter * (real_w / game_w))
        tap_x += random.randint(-phone_jitter, phone_jitter)
        tap_y += random.randint(-phone_jitter, phone_jitter)
        
    # Одна осознанная пауза перед нажатием вместо паузы 0,1–0,2 с после каждого нажатия
    wait = TAP_PACER.wait_before(seen_at)
    if wait > 0:
        time.sleep(wait)
    session_log.track_reaction(wait)

    tap_started = time.monotonic()
    tap_proc = subprocess.Popen(["adb", "shell", "input", "tap", str(tap_x), str(tap_y)], creationflags=0x08000000)
    TAP_PACER.tapped()
    session_log.track_tap(tap_proc, tap_started)  # замер задержки в фоне, бота не задерживает
    return tap_proc

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

def _match_on_frame(screenshot_cv, ox, oy, image_name, threshold):
    template = imread_cyrillic(image_name)
    if template is None: return None
    if template.shape[0] > screenshot_cv.shape[0] or template.shape[1] > screenshot_cv.shape[1]: return None

    res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)

    if max_val < threshold:
        return None
    h, w = template.shape[:2]
    return {"x": max_loc[0], "y": max_loc[1], "w": w, "h": h, "score": float(max_val), "ox": ox, "oy": oy}

def get_match_info(image_name, window_rect, sct, threshold):
    """Ищет картинку на новом снимке. Возвращает словарь с положением (в игровой области), размером картинки
    и степенью совпадения или None. Случайности здесь нет — по нему можно следить, стоит ли предмет на месте."""
    screenshot_cv, ox, oy, _, _ = _crop_screenshot_to_game_area(window_rect, sct)
    return _match_on_frame(screenshot_cv, ox, oy, image_name, threshold)

def game_frame(window_rect, sct):
    """Один снимок игровой области: (картинка BGR, ox, oy). Его можно передать в match_many_on_frame(frame=...),
    чтобы искать картинки и читать полоски на одном снимке (задача 9в)."""
    screenshot_cv, ox, oy, _, _ = _crop_screenshot_to_game_area(window_rect, sct)
    return screenshot_cv, ox, oy

def match_many_on_frame(names, window_rect, sct, threshold, area=(0.0, 1.0), frame=None):
    """Один снимок экрана на много картинок сразу (например, все титаны в слотах).
    area — какая часть игровой области по высоте нужна: (от, до) в долях, например (0.75, 1.0) — нижняя четверть.
    frame — готовый снимок из game_frame (тогда новый снимок не делается).
    Возвращает {имя: info} только для найденных (info — как у get_match_info, но "y" считается от верха части area,
    а "oy" — сдвиг этой части; от верха игровой области иконка на info["y"] + info["oy"] - oy снимка).
    Точку нажатия берите через click_point_from_info."""
    screenshot_cv, ox, oy = frame if frame is not None else game_frame(window_rect, sct)
    top = int(screenshot_cv.shape[0] * area[0])
    bottom = int(screenshot_cv.shape[0] * area[1])
    part = screenshot_cv[top:bottom]
    found = {}
    for name in names:
        info = _match_on_frame(part, ox, oy + top, name + ".png", threshold)
        if info is not None:
            found[name] = info
    return found

def get_first_match(candidates, window_rect, sct):
    """Один снимок экрана на все картинки сразу (быстрее, чем снимок на каждую).
    candidates — список (ключ, [имена картинок], порог) в порядке важности.
    Возвращает (ключ, имя картинки, info) первой найденной или None."""
    screenshot_cv, ox, oy, _, _ = _crop_screenshot_to_game_area(window_rect, sct)
    for key, names, threshold in candidates:
        for name in names:
            info = _match_on_frame(screenshot_cv, ox, oy, name, threshold)
            if info is not None:
                return key, name, info
    return None

def click_point_from_info(image_name, info, window_rect):
    """Случайная точка нажатия внутри найденной картинки, в координатах экрана."""
    w, h = info["w"], info["h"]
    x, y = info["x"], info["y"]
    scale = GEOMETRY_CACHE.get("scale", 1.0)

    # =====================================================================
    # ИНТЕЛЛЕКТУАЛЬНАЯ РАНДОМИЗАЦИЯ КЛИКОВ (ЗАЩИТА ОТ ДЕТЕКТА)
    # =====================================================================
    if "flag_enter" in image_name:
        # ИСКЛЮЧЕНИЕ: Логика для дверей — случайная точка в центральной части зоны под флажком
        rand_x, rand_y = click_logic.door_click_point(x, y, w, h, scale)
    else:
        # СТАНДАРТНАЯ КНОПКА: Отсекаем по 20% с каждого края
        margin_x = max(1, int(w * 0.2))
        margin_y = max(1, int(h * 0.2))

        # Защита на случай крошечных кнопок (отключаем отступ, если кнопка слишком мала)
        if margin_x * 2 >= w: margin_x = 0
        if margin_y * 2 >= h: margin_y = 0

        rand_x = random.randint(x + margin_x, x + w - margin_x)
        rand_y = random.randint(y + margin_y, y + h - margin_y)
    # =====================================================================

    # Универсальный возврат (ox и oy будут нулевыми, если обрезка не применялась)
    return (window_rect["left"] + info["ox"] + rand_x,
            window_rect["top"] + info["oy"] + rand_y)

def get_match_loc(image_name, window_rect, sct, threshold):
    info = get_match_info(image_name, window_rect, sct, threshold)
    if info is None:
        return None
    return click_point_from_info(image_name, info, window_rect)

def find_and_click_bulletproof(image_name, window_rect, sct, threshold, timeout=6.0, seen_at=None):
    """
    Человечный и надежный клик с защитой от непрокликивания и от лишних нажатий.

    Нажимает один раз и ждёт, пока кнопка пропадёт с экрана. Повторно жмёт, только если через
    click_logic.RETRY_AFTER_S после того, как команда нажатия дошла до телефона, экран не отреагировал.
    Если окно уже закрывается (кнопка бледнеет или едет), ждёт дольше.
    timeout — сколько искать кнопку и сколько можно начинать новые нажатия.
    seen_at — когда кнопка появилась на экране (time.monotonic()), если бот увидел её раньше (например, «ОК»
    до чтения ХП). Тогда пауза реакции уже прошла. None — считаем от первого снимка, где кнопка найдена.
    """
    start_time = time.time()
    policy = None
    retried_at = None  # когда было повторное нажатие (для диагностики в логе)

    while True:
        elapsed = time.time() - start_time
        shot_at = time.monotonic()  # кнопка видна на экране не позже, чем сделан снимок
        info = get_match_info(image_name, window_rect, sct, threshold)

        if info is None:
            if policy is not None:
                # Мы уже нажимали, а кнопка пропала — это 100% успех
                if retried_at is not None:
                    print(f"[VISION] '{image_name}': после повтора кнопка пропала через {time.monotonic() - retried_at:.1f} с")
                else:
                    since = policy.seconds_since_tap()
                    if since is not None and since >= 1.5:
                        print(f"[VISION] '{image_name}': окно отреагировало медленно, через {since:.1f} с после нажатия")
                return True
            if elapsed >= timeout:
                break
            time.sleep(0.1)
            continue

        pos = (info["x"], info["y"])
        if seen_at is None:
            seen_at = shot_at
        if policy is not None:
            verdict = policy.observe(True, info["score"], pos)
            if verdict == click_logic.WAIT:
                time.sleep(0.1)
                continue
            if elapsed >= timeout:
                break
            waited = policy.seconds_since_tap()
            tap_s = policy.tap_duration()
            print(f"[VISION] Клик по '{image_name}' не зарегистрирован сервером "
                  f"(нажатие выполнялось {tap_s:.1f} с, после него экран не отреагировал {waited:.1f} с). Повторяю...")
            session_log.count("repeat_clicks")
            retried_at = time.monotonic()

        coords = click_point_from_info(image_name, info, window_rect)
        tap_proc = click_human(coords[0], coords[1], seen_at=seen_at)
        policy = click_logic.RetryPolicy(click_logic.TapWatch(tap_proc, clock=time.monotonic),
                                         info["score"], pos, clock=time.monotonic)

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

def wait_after_tap(template_name, window_rect, sct, tap_proc, threshold=0.75, react_s=click_logic.DOOR_REACT_S,
                   poll_rate=0.05):
    """
    Ждёт реакцию на нажатие: появление элемента. Время отсчитывается не от нажатия, а от момента,
    когда команда adb дошла до телефона (иначе медленный adb выглядит как промах).
    Паузы «дать окну успокоиться» здесь больше нет (задача 10): замерло ли окно, проверяет тот, кто дальше
    с ним работает (find_smart_door), на своих же снимках.

    :return: (когда снимок сделан — time.monotonic(), центр элемента в координатах окна) или None,
             если за react_s после нажатия экран не отреагировал.
    """
    watch = click_logic.TapWatch(tap_proc, clock=time.monotonic)

    while True:
        done = watch.done_time()
        if done is not None and time.monotonic() - done >= react_s:
            return None

        shot_at = time.monotonic()
        info = get_match_info(template_name, window_rect, sct, threshold)
        if info:
            return shot_at, (info["ox"] + info["x"] + info["w"] // 2, info["oy"] + info["y"] + info["h"] // 2)

        time.sleep(poll_rate)
