# team_manager.py
import time
import os
from config import CONFIDENCE_THRESHOLD
from vision import click_human, get_match_loc, list_root_asset_names, click_point_from_info, match_many_on_frame, swipe_scrcpy, wait_for_ui_element

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

def precise_select_titan(x, y):
    """Снайперский точный клик по титану (через ADB)"""
    click_human(x, y, exact=True)
    time.sleep(0.15) 

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


def read_slots(names, window_rect, sct):
    """Один снимок экрана: кто стоит в нижних слотах. Возвращает ({титан: info}, {титан: x})."""
    found = match_many_on_frame(names, window_rect, sct, TITAN_THRESHOLD, SLOTS_AREA)
    return found, {t: info["x"] for t, info in found.items()}


def wait_slots_settled(target_pack, names, window_rect, sct):
    """Ждёт, пока в слотах окажется ровно нужный состав (иконка летит в слот ~1 с). True — состав совпал."""
    deadline = time.time() + SLOTS_SETTLE_TIMEOUT
    while True:
        _, slots = read_slots(names, window_rect, sct)
        if not any(team_diff(target_pack, slots)):
            return True
        if time.time() >= deadline:
            return False
        time.sleep(SLOTS_POLL_S)


def verify_and_set_team(target_pack, available_titans, window_rect, sct):
    names = slot_titan_names(target_pack)
    sorted_pack = sort_pack(target_pack)

    # Быстрая проверка: один снимок нижних слотов. Игра сама помнит последний состав, чаще всего он уже стоит
    _, slots = read_slots(names, window_rect, sct)
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
        found, slots = read_slots(names, window_rect, sct)
        unwanted, missing = team_diff(target_pack, slots)
        for titan in unwanted:
            if os.path.exists("pause.flag"): return False
            print(f"[КОМАНДА] Убираю: {titan}")
            x, y = click_point_from_info(f"{titan}.png", found[titan], window_rect)
            precise_select_titan(x, y)
            time.sleep(0.2)

        # 2. Ставим недостающих. Сетка при выборе не двигается, поэтому ищем всех на одном снимке
        remaining = [t for t in sorted_pack if t in missing]
        for swipe_idx in range(3):
            if not remaining:
                break
            if os.path.exists("pause.flag"): return False
            in_grid = match_many_on_frame(remaining, window_rect, sct, TITAN_THRESHOLD, GRID_AREA)
            for titan in [t for t in remaining if t in in_grid]:
                print(f"[КОМАНДА] -> Ставлю {titan}")
                x, y = click_point_from_info(f"{titan}.png", in_grid[titan], window_rect)
                precise_select_titan(x, y)
                remaining.remove(titan)
            if remaining and swipe_idx < 2:
                print(f"[КОМАНДА] -> Не вижу {remaining}. Делаю свайп ВНИЗ ({swipe_idx + 1}/2)...")
                swipe_scrcpy(window_rect, direction="down")
                scrolled += 1
                time.sleep(0.3)  # ждём прогрузки интерфейса после свайпа
        for titan in remaining:
            print(f"[ОШИБКА] Не нашел {titan} даже после 2 свайпов!")

        # 3. Контрольная проверка: ждём, пока последняя иконка долетит в слот
        if wait_slots_settled(target_pack, names, window_rect, sct):
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
