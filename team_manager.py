# team_manager.py
import time
import os
from config import CONFIDENCE_THRESHOLD
import vision
from vision import click_human, get_match_loc, list_root_asset_names, click_point_from_info, match_many_on_frame, swipe_scrcpy, wait_for_ui_element, game_frame
from analyzer import read_bars_under_icon

# Оригинальный, проверенный порог совпадения
TITAN_THRESHOLD = 0.88 

GAME_ORDER = [
    "hyperion", "sigurd", "nova", "mairi", "tidus", "orm",
    "eden", "angus", "avalon", "silva", "verdok", "pallant",
    "araji", "moloch", "vulcan", "ignis", "acheron", "alecto",
    "solaris", "rigel", "iyari", "amon", "lumira",
    "tenebris", "brustar", "keros", "mor", "umbra"
]

def open_grid_if_needed(window_rect, sct):
    """Проверка и открытие сетки выбора титанов с динамическим ожиданием"""
    print("[КОМАНДА] Сканирую интерфейс окна (без слепых пауз)...")
    
    # Ждем либо 4 точки (открыто), либо 9 точек (закрыто)
    start_time = time.time()
    while time.time() - start_time < 8.0:
        if os.path.exists("pause.flag"): return False
        
        if get_match_loc('btn_4_dots.png', window_rect, sct, 0.7):
            print("[КОМАНДА] Сетка титанов открыта и готова к работе.")
            time.sleep(0.3) 
            return True
            
        coords_9 = get_match_loc('btn_9_dots.png', window_rect, sct, 0.7)
        if coords_9:
            print("[КОМАНДА] Сетка свернута. Нажимаю открыть...")
            click_human(coords_9[0], coords_9[1])
            
            # Динамически ждем пока анимация развертывания сетки закончится
            if wait_for_ui_element('btn_4_dots.png', window_rect, sct, 0.7, timeout=3.0, settle_time=0.3):
                print("[КОМАНДА] Сетка успешно развернута!")
                return True
                
        time.sleep(0.1)
            
    print("[ОШИБКА КОМАНДЫ] Не смог убедиться, что сетка открыта (не вижу 4 точки)!")
    return False

def precise_select_titan(x, y, seen_at=None):
    """Снайперский точный клик по титану (через ADB).
    seen_at — когда сделан снимок, на котором нашли титана: от него считается пауза реакции (задача 10).
    Паузы после нажатия нет: между нажатиями бот сам выдерживает не меньше 0,5 с (не больше 2 нажатий в секунду)."""
    click_human(x, y, exact=True, seen_at=seen_at)

# Картинки в корне assets/, которые не титаны (кнопки, враги, значки и т.п.)
NOT_TITAN_PREFIXES = ("btn_", "res_", "enemy_", "icon_", "flag_", "badge_")


def slot_titan_names(extra=()):
    """Все титаны, которых надо видеть в слотах: берутся из картинок (assets/ или assets_db.py), поэтому новый титан
    подхватывается сам. Сначала идут титаны из GAME_ORDER (порядок сборки), потом остальные по алфавиту."""
    found = {n for n in list_root_asset_names() if not n.startswith(NOT_TITAN_PREFIXES)}
    rest = sorted((found | set(extra)) - set(GAME_ORDER))
    return list(GAME_ORDER) + rest


# Какая часть игровой области по высоте — слоты состава (внизу) и сетка выбора (сверху)
SLOTS_AREA = (0.75, 1.0)
GRID_AREA = (0.0, 0.75)

SLOTS_SETTLE_TIMEOUT = 2.0  # сколько ждать, пока иконка долетит в слот
SLOTS_POLL_S = 0.1


def team_diff(target_pack, slots):
    """Что поменять в слотах. slots — {титан: x} (слева направо порядок по x).
    Возвращает (лишние справа налево, недостающие в порядке сборки). Без OpenCV, проверяется тестами."""
    sorted_pack = sort_pack(target_pack)
    unwanted = sorted((t for t in slots if t not in target_pack), key=lambda t: slots[t], reverse=True)
    missing = [t for t in sorted_pack if t not in slots]
    return unwanted, missing


def sort_pack(target_pack):
    """Порядок сборки: как в игре, а неизвестные имена в конце."""
    sorted_pack = [t for t in GAME_ORDER if t in target_pack]
    for t in target_pack:
        if t not in sorted_pack:
            sorted_pack.append(t)
    return sorted_pack


def read_slots(names, window_rect, sct, frame=None):
    """Один снимок экрана: кто стоит в нижних слотах. Возвращает ({титан: info}, {титан: x}).
    frame — готовый снимок (vision.game_frame), тогда новый не делается."""
    found = match_many_on_frame(names, window_rect, sct, TITAN_THRESHOLD, SLOTS_AREA, frame=frame)
    return found, {t: info["x"] for t, info in found.items()}


def slot_bars(found, frame):
    """ХП и энергия по полоскам под иконками в слотах (задача 9в). found — из read_slots на этом же снимке frame.
    Возвращает {титан: {"hp": %, "energy": %}}; не прочиталось — None вместо числа."""
    screenshot_cv, _, oy = frame
    scale = vision.GEOMETRY_CACHE.get("scale", 1.0)
    return {t: read_bars_under_icon(screenshot_cv, (info["x"], info["y"] + info["oy"] - oy, info["w"], info["h"]), scale)
            for t, info in found.items()}


def scan_slots(names, window_rect, sct):
    """Один снимок: кто стоит в слотах и сколько у них ХП и энергии (задача 9в).
    names — кого искать: если известно, кто там стоит, хватит этих титанов (так быстрее).
    Возвращает ({титан: info}, {титан: x}, {титан: {"hp", "energy"}})."""
    frame = game_frame(window_rect, sct)
    found, slots = read_slots(names, window_rect, sct, frame)
    return found, slots, slot_bars(found, frame)


BARS_RECHECK_S = 0.3     # через сколько перечитать полоски, если они не совпали с памятью
BARS_RECHECK_TRIES = 3   # не больше стольких перечитываний
BARS_SAME = 2            # два снимка «одинаковые», если цифры отличаются не больше чем на 2%


def _same_bars(a, b):
    return all(a.get(k) == b.get(k) or (a.get(k) is not None and b.get(k) is not None and abs(a[k] - b[k]) <= BARS_SAME)
               for k in ("hp", "energy"))


def recheck_bars(titans, bars, window_rect, sct, sleep=time.sleep):
    """Полоски этих титанов не совпали с памятью бота (задача 9в): вдруг они ещё не дорисовались.
    Перечитываем их (только этих титанов), пока два снимка подряд не покажут одно и то же (±BARS_SAME%),
    но не больше BARS_RECHECK_TRIES раз. Берётся последний снимок. Обновляет bars и возвращает его."""
    last = {t: bars[t] for t in titans if t in bars}
    for _ in range(BARS_RECHECK_TRIES):
        if not last:
            break
        sleep(BARS_RECHECK_S)
        _, _, now = scan_slots(sorted(last), window_rect, sct)
        stable = all(_same_bars(last[t], now[t]) for t in last if t in now)
        last.update({t: now[t] for t in last if t in now})
        if stable:
            break
    bars.update(last)
    return bars


def wait_slots_settled(target_pack, names, window_rect, sct, bars=None):
    """Ждёт, пока в слотах окажется ровно нужный состав (иконка летит в слот ~1 с). True — состав совпал.
    bars — словарь: в него пишутся полоски ХП и энергии с того снимка, где состав совпал."""
    deadline = time.time() + SLOTS_SETTLE_TIMEOUT
    while True:
        _, slots, readings = scan_slots(names, window_rect, sct)
        if not any(team_diff(target_pack, slots)):
            if bars is not None:
                bars.update(readings)
            return True
        if time.time() >= deadline:
            return False
        time.sleep(SLOTS_POLL_S)


def verify_and_set_team(target_pack, available_titans, window_rect, sct, seen=None, bars=None):
    """Ставит нужный состав в слоты. True — состав стоит.
    seen — кто уже виден в слотах ({титан: info} с того же экрана, задача 9в): тогда первый снимок не нужен.
    bars — словарь: после сборки в него пишутся ХП и энергия титанов с экрана (кого бот поставил сам)."""
    names = slot_titan_names(target_pack)
    sorted_pack = sort_pack(target_pack)

    # Быстрая проверка: один снимок нижних слотов. Игра сама помнит последний состав, чаще всего он уже стоит
    if seen is None:
        _, slots = read_slots(names, window_rect, sct)
    else:
        slots = {t: info["x"] for t, info in seen.items()}
    if not any(team_diff(target_pack, slots)):
        print(f"[КОМАНДА] Состав уже стоит в слотах: {sorted_pack}. Ничего не меняю.")
        return True

    if not open_grid_if_needed(window_rect, sct):
        return False

    print(f"\n[КОМАНДА] Состав не совпал. Начинаю сборку: {sorted_pack}")

    MAX_ATTEMPTS = 3
    scrolled = 0  # на сколько свайпов вниз сдвинута сетка (в обычном случае 0)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        if os.path.exists("pause.flag"): return False

        if attempt > 1:
            print(f"\n[КОМАНДА] --- ПОПЫТКА {attempt}/{MAX_ATTEMPTS}: Корректировка состава ---")
            while scrolled > 0:  # вернуть сетку на место, только если сами её сдвигали
                swipe_scrcpy(window_rect, direction="up")
                scrolled -= 1

        # 1. Убираем лишних. Одним снимком, справа налево: тогда остальные при сдвиге влево не меняют места
        seen_at = time.monotonic()
        found, slots = read_slots(names, window_rect, sct)
        unwanted, missing = team_diff(target_pack, slots)
        for titan in unwanted:
            if os.path.exists("pause.flag"): return False
            print(f"[КОМАНДА] Убираю: {titan}")
            x, y = click_point_from_info(f"{titan}.png", found[titan], window_rect)
            precise_select_titan(x, y, seen_at)

        # 2. Ставим недостающих. Сетка при выборе не двигается, поэтому ищем всех на одном снимке
        remaining = [t for t in sorted_pack if t in missing]
        for swipe_idx in range(3):
            if not remaining:
                break
            if os.path.exists("pause.flag"): return False
            seen_at = time.monotonic()
            in_grid = match_many_on_frame(remaining, window_rect, sct, TITAN_THRESHOLD, GRID_AREA)
            for titan in [t for t in remaining if t in in_grid]:
                print(f"[КОМАНДА] -> Ставлю {titan}")
                x, y = click_point_from_info(f"{titan}.png", in_grid[titan], window_rect)
                precise_select_titan(x, y, seen_at)
                remaining.remove(titan)
            if remaining and swipe_idx < 2:
                print(f"[КОМАНДА] -> Не вижу {remaining}. Делаю свайп ВНИЗ ({swipe_idx + 1}/2)...")
                swipe_scrcpy(window_rect, direction="down")
                scrolled += 1
                time.sleep(0.3)  # ждём прогрузки интерфейса после свайпа
        for titan in remaining:
            print(f"[ОШИБКА] Не нашел {titan} даже после 2 свайпов!")

        # 3. Контрольная проверка: ждём, пока последняя иконка долетит в слот
        if wait_slots_settled(target_pack, names, window_rect, sct, bars):
            print("[КОМАНДА] Состав ИДЕАЛЬНО укомплектован!")
            return True

        _, slots = read_slots(names, window_rect, sct)
        unwanted, missing = team_diff(target_pack, slots)
        for titan in missing:
            print(f"[ПРОВЕРКА] Провал: {titan} отсутствует в слотах!")
        for titan in unwanted:
            print(f"[ПРОВЕРКА] Провал: {titan} остался в слотах, хотя его там быть не должно!")
        print(f"[ПРЕДУПРЕЖДЕНИЕ] Сборка не прошла проверку. Перехожу к следующей попытке.")

    print("[ФАТАЛЬНАЯ ОШИБКА КОМАНДЫ] Не удалось собрать правильный состав за 3 попытки!")
    return False
