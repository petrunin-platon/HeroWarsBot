# team_manager.py
import time
import os
import cv2
import numpy as np
from config import CONFIDENCE_THRESHOLD
import vision
import click_logic
from vision import click_human, get_match_loc, list_root_asset_names, click_point_from_info, match_many_on_frame, swipe_scrcpy, wait_for_ui_element, game_frame
from analyzer import read_bars_under_icon

# Оригинальный, проверенный порог совпадения
TITAN_THRESHOLD = 0.88

GAME_ORDER = [
    "hyperion", "sigurd", "nova", "mairi", "tidus", "orm",
    "eden", "angus", "avalon", "silva", "verdok", "pallant",
    "araji", "moloch", "vulcan", "ignis", "acheron", "alecto",
    "solaris", "rigel", "iyari", "amon", "lumira",
    "tenebris", "brustar", "keros", "mor", "umbra", "metida"
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
    """Снайперский точный клик по титану (через ADB). Возвращает процесс нажатия (по нему видно, когда оно дошло).
    seen_at — когда сделан снимок, на котором нашли титана: от него считается пауза реакции (задача 10).
    Паузы после нажатия нет: между нажатиями бот сам выдерживает не меньше 0,5 с (не больше 2 нажатий в секунду)."""
    return click_human(x, y, exact=True, seen_at=seen_at)

# Картинки в корне assets/, которые не титаны (кнопки, враги, значки и т.п.)
NOT_TITAN_PREFIXES = ("btn_", "res_", "enemy_", "icon_", "flag_", "badge_")


def slot_titan_names(extra=()):
    """Все титаны, которых надо видеть в слотах: берутся из картинок (assets/ или assets_db.py), поэтому новый титан
    подхватывается сам. Сначала идут титаны из GAME_ORDER (порядок сборки), потом остальные по алфавиту."""
    found = {n for n in list_root_asset_names() if not n.startswith(NOT_TITAN_PREFIXES)}
    rest = sorted((found | set(extra)) - set(GAME_ORDER))
    return list(GAME_ORDER) + rest


# Какая часть игровой области — слоты состава (внизу) и сетка выбора (сверху). По ширине — только панель слева
# (задача 11: искать в нужной части экрана). Панель привязана к левому краю, её ширина — примерно высота игры
SLOTS_AREA = vision.Area(0.75, 1.0, right=1.05)
GRID_AREA = vision.Area(0.0, 0.75, right=1.05)

SLOTS_SETTLE_TIMEOUT = 3.0  # сколько ждать, пока иконки долетят в слоты и слоты сдвинутся (после того, как нажатие дошло)
SLOTS_POLL_S = 0.1
SLOTS_SAME_PX = 3           # снимки слотов «одинаковые», если каждый титан сдвинулся не больше чем на столько пикселей

# Сетка «стоит», если два снимка отличаются по яркости в среднем меньше (0–255). На скриншотах: неподвижная сетка — 0,5,
# сдвиг на 1 пиксель — 1,8–4, на 3 пикселя — 5–10
GRID_STILL_DIFF = 2.0


def team_diff(target_pack, slots):
    """Что поменять в слотах. slots — {титан: x} (слева направо порядок по x).
    Возвращает (лишние слева направо, недостающие в порядке сборки). Без OpenCV, проверяется тестами.

    Слоты в игре прижаты вправо: когда титана убирают, все, кто стоит ЛЕВЕЕ, сдвигаются на слот вправо,
    а кто правее — остаются на месте. Поэтому лишних убираем слева направо: следующий лишний стоит правее и не сдвинулся.
    Раньше убирали справа налево, и второе нажатие попадало в соседа (сессии 07 и 09: вместо Вулкана убирался Араджи)."""
    sorted_pack = sort_pack(target_pack)
    unwanted = sorted((t for t in slots if t not in target_pack), key=lambda t: slots[t])
    missing = [t for t in sorted_pack if t not in slots]
    return unwanted, missing


def sort_pack(target_pack):
    """Порядок сборки: как в игре, а неизвестные имена в конце."""
    sorted_pack = [t for t in GAME_ORDER if t in target_pack]
    for t in target_pack:
        if t not in sorted_pack:
            sorted_pack.append(t)
    return sorted_pack


def _same_spot(a, b):
    """Две найденные иконки (info) стоят в одной точке: сдвиг меньше половины иконки."""
    return (abs(a["x"] - b["x"]) < min(a["w"], b["w"]) / 2 and
            abs(a["y"] - b["y"]) < min(a["h"], b["h"]) / 2)


def best_per_spot(found):
    """В одной точке экрана может «найтись» несколько похожих титанов (Алекто и Умбра, Араджи и Вулкан).
    Оставляем того, у кого совпадение лучше (задача 11). found — {титан: info} с одного снимка."""
    kept = {}
    for name, info in sorted(found.items(), key=lambda kv: -kv[1]["score"]):
        if not any(_same_spot(info, other) for other in kept.values()):
            kept[name] = info
    return kept


def better_titan_here(name, info, frame, names):
    """Нет ли в этой точке сетки другого титана, который совпадает лучше (задача 11, Алекто и Умбра).
    Проверяем остальных только вокруг найденной иконки — это быстро. Возвращает имя такого титана или None."""
    screenshot_cv, _, _ = frame
    pad_x, pad_y = info["w"] // 2, info["h"] // 2
    x1, y1 = max(0, info["x"] - pad_x), max(0, info["y"] - pad_y)
    roi = screenshot_cv[y1:info["y"] + info["h"] + pad_y, x1:info["x"] + info["w"] + pad_x]
    for other in names:
        if other == name:
            continue
        template = vision.imread_cyrillic(other + ".png")
        if template is None or template.shape[0] > roi.shape[0] or template.shape[1] > roi.shape[1]:
            continue
        score = float(cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED).max())
        if score > info["score"]:
            return other
    return None


def read_slots(names, window_rect, sct, frame=None):
    """Один снимок экрана: кто стоит в нижних слотах. Возвращает ({титан: info}, {титан: x}).
    frame — готовый снимок (vision.game_frame), тогда новый не делается."""
    found = best_per_spot(match_many_on_frame(names, window_rect, sct, TITAN_THRESHOLD, SLOTS_AREA, frame=frame))
    return found, {t: info["x"] for t, info in found.items()}


def slot_bars(found, frame):
    """ХП и энергия по полоскам под иконками в слотах (задача 9в). found — из read_slots на этом же снимке frame.
    Возвращает {титан: {"hp": %, "energy": %}}; не прочиталось — None вместо числа."""
    screenshot_cv, _, _ = frame
    scale = vision.GEOMETRY_CACHE.get("scale", 1.0)
    return {t: read_bars_under_icon(screenshot_cv, (info["x"], info["y"], info["w"], info["h"]), scale)
            for t, info in found.items()}


def scan_slots(names, window_rect, sct, frame=None):
    """Один снимок: кто стоит в слотах и сколько у них ХП и энергии (задача 9в).
    names — кого искать: если известно, кто там стоит, хватит этих титанов (так быстрее).
    Возвращает ({титан: info}, {титан: x}, {титан: {"hp", "energy"}})."""
    frame = frame if frame is not None else game_frame(window_rect, sct)
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


def same_slots(a, b, tol=SLOTS_SAME_PX):
    """Два снимка слотов показывают одно и то же: те же титаны, каждый на том же месте (±tol пикселей)."""
    return set(a) == set(b) and all(abs(a[t] - b[t]) <= tol for t in a)


def wait_slots_settled(target_pack, names, window_rect, sct, bars=None, last_tap=None):
    """Ждёт, пока в слотах окажется ровно нужный состав. Возвращает (совпал ли, {титан: x} с последнего снимка).
    bars — словарь: в него пишутся полоски ХП и энергии с того снимка, где состав совпал.

    Иконка летит в слот ~1 с, а когда титана убирают, слоты сдвигаются. Снимок посреди этого может «показать»
    не то (сессия 09: бот увидел Араджи, которого уже убрал, и решил, что состав собран). Поэтому:
    - первый снимок — только после того, как последнее нажатие (last_tap — его процесс) дошло до телефона;
    - состав принимается, только если два снимка подряд (через STILL_INTERVAL_S) показали одно и то же."""
    watch = click_logic.TapWatch(last_tap, clock=time.monotonic)
    while watch.done_time() is None:
        time.sleep(0.05)
    tol = SLOTS_SAME_PX * vision.GEOMETRY_CACHE.get("scale", 1.0)
    deadline = time.monotonic() + SLOTS_SETTLE_TIMEOUT
    prev = None
    while True:
        shot_t = time.monotonic()
        _, slots, readings = scan_slots(names, window_rect, sct)
        if prev is not None and same_slots(prev[1], slots, tol) and not any(team_diff(target_pack, slots)):
            if bars is not None:
                bars.update(readings)
            return True, slots
        if time.monotonic() >= deadline:
            return False, slots
        prev = (shot_t, slots)
        rest = max(SLOTS_POLL_S, click_logic.STILL_INTERVAL_S - (time.monotonic() - shot_t))
        time.sleep(rest)


def _grid_thumb(frame):
    """Уменьшенный чёрно-белый снимок сетки: по нему видно, едет ли сетка."""
    screenshot_cv, _, _ = frame
    x1, y1, x2, y2 = vision.area_box(screenshot_cv.shape, GRID_AREA)
    gray = cv2.cvtColor(screenshot_cv[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA).astype(np.float32)


def grid_still(a, b):
    """Два уменьшенных снимка сетки одинаковые: сетка стоит."""
    return a.shape == b.shape and float(np.mean(np.abs(a - b))) < GRID_STILL_DIFF


def swipe_grid(window_rect, sct, direction):
    """Свайп сетки и ожидание, пока она остановится (задача 11). После свайпа сетка ещё едет по инерции, и если
    нажать в это время, попадёшь в соседа: в сессиях 08 и 09 бот «ставил Алекто», а вставала Умбра — она на ряд ниже.
    Возвращает (когда сделан снимок, снимок) — по нему искать титанов, нового снимка не нужно."""
    swipe_scrcpy(window_rect, direction=direction)

    def read():
        frame = game_frame(window_rect, sct)
        return time.monotonic(), frame, _grid_thumb(frame)

    last, still, _ = click_logic.wait_until_still(read, lambda a, b: grid_still(a[2], b[2]))
    if not still:
        print(f"[КОМАНДА] Сетка не остановилась за {click_logic.STILL_TIMEOUT_S:.0f} с после свайпа — ищу как есть.")
    return last[0], last[1]


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

        shot = None
        if attempt > 1:
            print(f"\n[КОМАНДА] --- ПОПЫТКА {attempt}/{MAX_ATTEMPTS}: Корректировка состава ---")
            while scrolled > 0:  # вернуть сетку на место, только если сами её сдвигали
                shot = swipe_grid(window_rect, sct, "up")
                scrolled -= 1

        # Один снимок на слоты и сетку: убранный титан в сетке не двигается (только пропадает галочка)
        if shot is None:
            shot = (time.monotonic(), game_frame(window_rect, sct))
        seen_at, frame = shot
        found, slots = read_slots(names, window_rect, sct, frame)
        unwanted, missing = team_diff(target_pack, slots)
        last_tap = None

        # 1. Убираем лишних слева направо: слоты прижаты вправо, и правее убранного никто не сдвигается
        for titan in unwanted:
            if os.path.exists("pause.flag"): return False
            print(f"[КОМАНДА] Убираю: {titan}")
            x, y = click_point_from_info(f"{titan}.png", found[titan], window_rect)
            last_tap = precise_select_titan(x, y, seen_at)

        # 2. Ставим недостающих. Сетка при выборе не двигается, поэтому ищем всех на одном снимке
        remaining = [t for t in sorted_pack if t in missing]
        for swipe_idx in range(3):
            if not remaining:
                break
            if os.path.exists("pause.flag"): return False
            in_grid = best_per_spot(match_many_on_frame(remaining, window_rect, sct, TITAN_THRESHOLD, GRID_AREA, frame=frame))
            for titan in [t for t in remaining if t in in_grid]:
                other = better_titan_here(titan, in_grid[titan], frame, names)
                if other:
                    print(f"[КОМАНДА] -> Там, где нашёлся {titan}, лучше совпадает {other}. Не нажимаю.")
                    continue
                print(f"[КОМАНДА] -> Ставлю {titan}")
                x, y = click_point_from_info(f"{titan}.png", in_grid[titan], window_rect)
                last_tap = precise_select_titan(x, y, seen_at)
                remaining.remove(titan)
            if remaining and swipe_idx < 2:
                print(f"[КОМАНДА] -> Не вижу {remaining}. Делаю свайп ВНИЗ ({swipe_idx + 1}/2)...")
                seen_at, frame = swipe_grid(window_rect, sct, "down")
                scrolled += 1
        for titan in remaining:
            print(f"[ОШИБКА] Не нашел {titan} даже после 2 свайпов!")

        # 3. Контрольная проверка: два одинаковых снимка после того, как последнее нажатие дошло до телефона
        settled, slots = wait_slots_settled(target_pack, names, window_rect, sct, bars, last_tap)
        if settled:
            print("[КОМАНДА] Состав ИДЕАЛЬНО укомплектован!")
            return True

        unwanted, missing = team_diff(target_pack, slots)
        for titan in missing:
            print(f"[ПРОВЕРКА] Провал: {titan} отсутствует в слотах!")
        for titan in unwanted:
            print(f"[ПРОВЕРКА] Провал: {titan} остался в слотах, хотя его там быть не должно!")
        if not unwanted and not missing:
            print("[ПРОВЕРКА] Состав совпал только на последнем снимке — проверю ещё раз.")
        print(f"[ПРЕДУПРЕЖДЕНИЕ] Сборка не прошла проверку. Перехожу к следующей попытке.")

    print("[ФАТАЛЬНАЯ ОШИБКА КОМАНДЫ] Не удалось собрать правильный состав за 3 попытки!")
    return False
