# analyzer.py
import cv2
import numpy as np
import os
import time
from vision import imread_cyrillic, get_clean_game_screen, best_match, Area, area_box

def scan_enemy_team(window_rect, sct, all_titans, btn_local_x, screen=None):
    """
    Сканирует маленькие иконки врагов в точных рамках.
    Использует чистую геометрию игры без черных полос.
    screen — готовый снимок (картинка игровой области, clean_rect), например тот, где окно выбора комнат
    уже замерло (задача 11): тогда новый снимок не делается.
    """
    screenshot_cv, clean_rect = screen if screen is not None else get_clean_game_screen(window_rect, sct)

    w = clean_rect["width"]
    h = clean_rect["height"]
    
    roi_y_start = int(h * (140 / 449))  
    roi_y_end = int(h * ((140 + 85) / 449)) 
    
    if btn_local_x < window_rect["width"] * 0.4:
        roi_x_start = int(w * (140 / 939))
        roi_x_end = int(w * ((140 + 310) / 939))
        print("[АНАЛИЗАТОР] Сканирую ЛЕВУЮ комнату врагов...")
    elif btn_local_x > window_rect["width"] * 0.6:
        roi_x_start = int(w * (490 / 939))
        roi_x_end = int(w * ((490 + 310) / 939))
        print("[АНАЛИЗАТОР] Сканирую ПРАВУЮ комнату врагов...")
    else:
        roi_x_start = int(w * (315 / 939))
        roi_x_end = int(w * ((315 + 310) / 939))
        print("[АНАЛИЗАТОР] Сканирую ЦЕНТРАЛЬНУЮ комнату врагов...")
        
    roi_img = screenshot_cv[roi_y_start:roi_y_end, roi_x_start:roi_x_end]
    enemies_found = []
    
    for titan in all_titans:
        icon_name = f"enemy_{titan}.png"
        template = imread_cyrillic(icon_name)
        
        if template is None:
            print(f"[ОШИБКА АССЕТА] Не найден шаблон врага: {icon_name}")
            continue
            
        if template.shape[0] > roi_img.shape[0] or template.shape[1] > roi_img.shape[1]:
            continue
            
        max_val, _ = best_match(roi_img, template, ENEMY_THRESHOLD)

        if max_val >= ENEMY_THRESHOLD:
            enemies_found.append(titan)
            
    print(f"[АНАЛИЗАТОР] Обнаружены враги: {enemies_found}")
    return enemies_found

ENEMY_THRESHOLD = 0.72
RESULT_ICON_THRESHOLD = 0.62  # иконка титана на окне результата
RESULT_RECHECK_MARGIN = 20    # при перечитывании иконку ищем на столько пикселей вокруг прежнего места (при ширине 939)
# Где на окне результата искать иконки титанов (задача 11): ряд иконок посередине, с большим запасом
# (на 54.png и 111.png иконки на 0,28–0,41 высоты и ±0,43 высоты от середины; паки из 3–4 титанов — уже)
RESULT_AREA = Area(0.05, 0.75, -0.75, 0.75, "center")


def _result_masks(screenshot_cv):
    """Зелёная (ХП) и жёлтая (энергия) маски окна результата."""
    hsv = cv2.cvtColor(screenshot_cv, cv2.COLOR_BGR2HSV)
    
    # Зеленая маска для ХП
    lower_green = np.array([45, 100, 100])
    upper_green = np.array([75, 255, 255])
    mask_green = cv2.inRange(hsv, lower_green, upper_green)
    
    # Маска энергии
    lower_yellow = np.array([18, 150, 170])
    upper_yellow = np.array([32, 255, 255])
    mask_energy = cv2.inRange(hsv, lower_yellow, upper_yellow)
    return mask_green, mask_energy


def _result_template(titan):
    """Иконка титана для окна результата (края срезаны) или None."""
    template = imread_cyrillic(f"res_{titan}.png")
    if template is None:
        return None
    CROP_SIDES = 4 
    if template.shape[1] > CROP_SIDES * 3:
        template = template[:, CROP_SIDES:-CROP_SIDES]
    return template


def _result_bars(masks, x_start, y_start, icon_w, icon_h, scale_x, marks=None):
    """ХП и энергия (%) по полоскам под иконкой окна результата, иконка найдена в (x_start, y_start).
    marks — словарь: в него пишется, где бот мерил (для картинки отладки, result_debug_image). На цифры не влияет."""
    mask_green, mask_energy = masks
    max_bar_width = 50.0 * scale_x

    SHIFT_DOWN = int(icon_h * 1.6) 
    BOX_HEIGHT = int(icon_h * 0.70) 
    EXPAND_WIDTH = int(15 * scale_x) 
    
    crop_y1 = min(y_start + SHIFT_DOWN, mask_green.shape[0])
    crop_y2 = min(crop_y1 + BOX_HEIGHT, mask_green.shape[0])
    
    crop_x1 = max(x_start - EXPAND_WIDTH, 0)
    crop_x2 = min(x_start + icon_w + EXPAND_WIDTH, mask_green.shape[1]) 
    
    roi_green = mask_green[crop_y1:crop_y2, crop_x1:crop_x2]
    roi_energy = mask_energy[crop_y1:crop_y2, crop_x1:crop_x2]
    
    hp_w, hp_y = 0, -1 
    
    if roi_green.size > 0:
        green_row_sums = np.sum(roi_green == 255, axis=1)
        if len(green_row_sums) > 0:
            max_green_pixels = np.max(green_row_sums)
            if max_green_pixels >= 3:
                hp_y = np.argmax(green_row_sums)
                hp_w = max_green_pixels

    ep_w = 0
    if hp_y != -1 and roi_energy.size > 0:
        search_start = hp_y + 4
        search_end = min(roi_energy.shape[0], hp_y + 14)
        if search_start < search_end:
            energy_slice = roi_energy[search_start:search_end, :]
            energy_row_sums = np.sum(energy_slice == 255, axis=1)
            if len(energy_row_sums) > 0:
                max_energy_pixels = np.max(energy_row_sums)
                if max_energy_pixels >= 5:
                    ep_w = max_energy_pixels

    hp_perc = min(int((hp_w / max_bar_width) * 100), 100)
    ep_perc = min(int((ep_w / max_bar_width) * 100), 100)
    if marks is not None:
        marks.update({"box": (crop_x1, crop_y1, crop_x2, crop_y2), "full": max_bar_width,
                      "hp": _bar_mark(roi_green, hp_y, hp_w, crop_x1, crop_y1),
                      "energy": _bar_mark(roi_energy, hp_y + 4 + int(np.argmax(energy_row_sums)), ep_w, crop_x1, crop_y1)
                      if ep_w else None})
    return hp_perc, ep_perc


def _bar_mark(roi, row, width, x0, y0):
    """Где на снимке полоска, которую бот померил: (x начала, y строки, сколько пикселей залито) или None."""
    if row < 0 or width <= 0:
        return None
    cols = np.flatnonzero(roi[row] == 255)
    return (x0 + int(cols[0]), y0 + int(row), int(width)) if cols.size else None


def result_debug_image(screenshot_cv, icons, team_status, scale_x):
    """Картинка для отладки (debug_mode): окно результата, на нём рамки найденных иконок, зона, где бот искал полоски,
    и линии, сколько пикселей полоски он посчитал залитыми (ХП — зелёная, энергия — жёлтая) против полной длины (белая
    рамка = 100%). Подпись — итоговые цифры. icons — {титан: (x, y, w, h)} с этого же снимка."""
    img = screenshot_cv.copy()
    masks = _result_masks(screenshot_cv)
    for titan, (x, y, w, h) in icons.items():
        marks = {}
        _result_bars(masks, x, y, w, h, scale_x, marks)
        cv2.rectangle(img, (x, y), (x + w, y + h), (255, 0, 255), 2)
        bx1, by1, bx2, by2 = marks["box"]
        cv2.rectangle(img, (bx1, by1), (bx2, by2), (255, 255, 0), 1)
        for key, color in (("hp", (0, 255, 0)), ("energy", (0, 215, 255))):
            mark = marks.get(key)
            if mark:
                mx, my, width = mark
                cv2.rectangle(img, (mx, my - 3), (mx + int(round(marks["full"])), my + 3), (255, 255, 255), 1)
                cv2.line(img, (mx, my), (mx + width, my), color, 2)
                cv2.line(img, (mx + width, my - 6), (mx + width, my + 6), (0, 0, 255), 2)
        entry = team_status.get(titan, {})
        for i, text in enumerate((titan.upper(), f"HP {entry.get('hp', '?')}% EN {entry.get('energy', '?')}%")):
            org = (bx1, by2 + 16 + 16 * i)
            cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
            cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    return img


def _result_entry(hp_perc, ep_perc, score):
    if hp_perc == 0:
        return {"hp": 0, "energy": 0, "status": "МЕРТВ", "score": float(score)}
    return {"hp": hp_perc, "energy": ep_perc, "status": "ЖИВ", "score": float(score)}


def team_status_lines(pack, team_status):
    """Строки лога с ХП и энергией титанов пака (как их печатает scan_team_health)."""
    lines = []
    for titan in pack:
        entry = team_status.get(titan)
        if entry is None:
            continue
        if entry["status"] == "ОТСУТСТВУЕТ":
            lines.append(f" ---> {titan.upper()}: [ОТСУТСТВУЕТ] (иконка не найдена: сходство {entry['score']:.2f}, "
                         f"порог {RESULT_ICON_THRESHOLD})")
        elif entry["hp"] == 0:
            lines.append(f" ---> {titan.upper()}: [МЕРТВ] (ХП = 0%, сходство иконки {entry['score']:.2f})")
        else:
            lines.append(f" ---> {titan.upper()}: ХП {entry['hp']}%, Энергия {entry['energy']}%")
    return lines


def scan_team_health(window_rect, sct, current_pack, found=None, frames=None, quiet=False):
    """
    Сканирование здоровья и энергии титанов на окне результатов.
    Абсолютная адаптивность: зона поиска и формула меняются вместе с разрешением.
    found — словарь: в него пишется, где нашлась иконка каждого титана {титан: (x, y, w, h)}.
    По нему reread_team_health быстро перечитывает полоски (задача 10).
    frames — список: в него добавляется (когда снят — time.monotonic(), картинка BGR, clean_rect).
    На этом же снимке main.py ищет значок «x2» (задача 11).
    quiet — ничего не печатать: main.py печатает цифры, только когда полоски замерли (задача 11, сессия после 09:
    первый снимок попадал на анимацию окна, и в логе было «Араджи 8%», хотя решение принималось по 100%).
    """
    if found is not None:
        found.clear()
    shot_at = time.monotonic()
    screenshot_cv, clean_rect = get_clean_game_screen(window_rect, sct)
    if frames is not None:
        frames.append((shot_at, screenshot_cv, clean_rect))
    masks = _result_masks(screenshot_cv)
    ax1, ay1, ax2, ay2 = area_box(screenshot_cv.shape, RESULT_AREA)
    icons_area = screenshot_cv[ay1:ay2, ax1:ax2]
    
    team_status = {}
    
    # =====================================================================
    # ЧИСТАЯ МАТЕМАТИКА ОТ ШИРИНЫ 
    # =====================================================================
    w = clean_rect["width"]
    scale_x = w / 939.0
    
    max_bar_width = 50.0 * scale_x
    
    if not quiet:
        print(f"\n[АНАЛИЗАТОР] Чистая зона игры: {clean_rect['width']}x{clean_rect['height']}")
        print(f"[АНАЛИЗАТОР] Масштаб: {scale_x:.3f}x | Эталон полоски: {max_bar_width:.2f}px")

    for titan in current_pack:
        template = _result_template(titan)
        if template is None:
            print(f"[ОШИБКА] Не найдена иконка в RAM/диске: res_{titan}.png")
            continue

        if template.shape[0] > icons_area.shape[0] or template.shape[1] > icons_area.shape[1]:
            continue

        max_val, max_loc = best_match(icons_area, template, RESULT_ICON_THRESHOLD)

        if max_loc is not None:
            max_loc = (ax1 + max_loc[0], ay1 + max_loc[1])
            icon_h, icon_w = template.shape[:-1]
            if found is not None:
                found[titan] = (max_loc[0], max_loc[1], icon_w, icon_h)
            hp_perc, ep_perc = _result_bars(masks, max_loc[0], max_loc[1], icon_w, icon_h, scale_x)
            team_status[titan] = _result_entry(hp_perc, ep_perc, max_val)
        else:
            team_status[titan] = {"hp": 0, "energy": 0, "status": "ОТСУТСТВУЕТ", "score": float(max_val)}

    if not quiet:
        for line in team_status_lines(current_pack, team_status):
            print(line)
        print("[АНАЛИЗАТОР] Сканирование завершено.\n")
    return team_status


def reread_team_health(window_rect, sct, found, frames=None):
    """Перечитать полоски ХП и энергии на окне результата (задача 10): «замерли» ли они.
    Иконку каждого титана ищем только рядом с местом, где её нашёл scan_team_health (found), поэтому быстро.
    В лог не пишет. Возвращает {титан: {"hp", "energy", "status", "score"}} для найденных; found обновляется.
    frames — список: в него добавляется снимок (как у scan_team_health)."""
    shot_at = time.monotonic()
    screenshot_cv, clean_rect = get_clean_game_screen(window_rect, sct)
    if frames is not None:
        frames.append((shot_at, screenshot_cv, clean_rect))
    masks = _result_masks(screenshot_cv)
    scale_x = clean_rect["width"] / 939.0
    margin = max(4, int(RESULT_RECHECK_MARGIN * scale_x))
    team_status = {}
    for titan, (x, y, icon_w, icon_h) in list(found.items()):
        template = _result_template(titan)
        if template is None:
            continue
        x1, y1 = max(0, x - margin), max(0, y - margin)
        roi = screenshot_cv[y1:y + icon_h + margin, x1:x + icon_w + margin]
        if template.shape[0] > roi.shape[0] or template.shape[1] > roi.shape[1]:
            continue
        res = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val < RESULT_ICON_THRESHOLD:
            continue
        nx, ny = x1 + max_loc[0], y1 + max_loc[1]
        found[titan] = (nx, ny, icon_w, icon_h)
        team_status[titan] = _result_entry(*_result_bars(masks, nx, ny, icon_w, icon_h, scale_x), max_val)
    return team_status


# =====================================================================
# ПОЛОСКИ ХП И ЭНЕРГИИ НА ЭКРАНЕ ВЫБОРА КОМАНДЫ (задача 9в)
# Под иконкой титана (в слотах и в сетке) две полоски: зелёная — ХП, под ней жёлтая — энергия.
# Пустая часть полоски почти чёрная. Длину полоски бот меряет сам (заливка + чёрная часть до рамки),
# поэтому размер окна не важен. Настроено по logs/session_01-02/screens/pered_boem.png.
# =====================================================================
BAR_GREEN = (np.array([45, 100, 100]), np.array([75, 255, 255]))   # как на окне результата
BAR_YELLOW = (np.array([18, 150, 170]), np.array([32, 255, 255]))
BAR_DARK_V = 45        # пустая часть полоски: яркость (V в HSV) не больше этой; рамка и фон светлее
BAR_DARK_S = 180       # и насыщенность меньше этой: тёмный край заливки — тень того же цвета, это не пустая часть
BAR_LENGTH = 65        # длина полоски в пикселях при высоте игры 720 (на pered_boem.png 64–65)
BAR_MIN_LENGTH = 0.6   # полоска короче 60% этой длины — не полоска
BAR_AREA_Y = (15, 65)  # где искать полоску ХП: на столько пикселей ниже иконки (при высоте 720)
BAR_AREA_X = (30, 10)  # и на столько левее и правее иконки (полоска сдвинута влево от шаблона)
ENERGY_BELOW = (8, 24)  # полоска энергии — на столько пикселей ниже полоски ХП


def _bar_percent(fill_row, dark_row, min_length):
    """Сколько процентов полоски залито. fill_row и dark_row — строки масок (True — заливка / пустая часть).
    Полоска начинается с самого длинного куска заливки (или, если заливки нет, с самого длинного чёрного куска)
    и идёт вправо, пока не начнётся рамка. Разрыв в 1–2 пикселя (сглаженный край заливки) допустим.
    None — полоски нет."""
    fill = np.asarray(fill_row, dtype=bool)
    dark = np.asarray(dark_row, dtype=bool)
    start = _longest_run_start(fill)
    if start is None:
        start = _longest_run_start(dark)
        if start is None:
            return None
    last_good, gap = start, 0
    for x in range(start, len(fill)):
        if fill[x] or dark[x]:
            last_good, gap = x, 0
        else:
            gap += 1
            if gap > 2:
                break
    length = last_good - start + 1
    if length < min_length:
        return None
    filled = np.flatnonzero(fill[start:last_good + 1])
    return min(100, round(100 * (filled.max() + 1) / length)) if filled.size else 0


def _longest_run_start(mask):
    """Начало самого длинного куска True подряд (None — нет ни одного)."""
    best_start, best_len, start = None, 0, None
    for x, value in enumerate(list(mask) + [False]):
        if value and start is None:
            start = x
        elif not value and start is not None:
            if x - start > best_len:
                best_start, best_len = start, x - start
            start = None
    return best_start


def read_bars_under_icon(screenshot_cv, box, scale=1.0):
    """ХП и энергия титана по полоскам под его иконкой. box — (x, y, w, h) иконки на снимке screenshot_cv (BGR).
    Возвращает {"hp": %, "energy": %}; не прочиталось — None вместо числа."""
    x, y, w, h = box
    img_h, img_w = screenshot_cv.shape[:2]
    x1 = max(0, int(x - BAR_AREA_X[0] * scale))
    x2 = min(img_w, int(x + w + BAR_AREA_X[1] * scale))
    y1 = min(img_h, int(y + h + BAR_AREA_Y[0] * scale))
    y2 = min(img_h, int(y + h + BAR_AREA_Y[1] * scale + ENERGY_BELOW[1] * scale))
    result = {"hp": None, "energy": None}
    if x2 - x1 < 5 or y2 - y1 < 5:
        return result

    hsv = cv2.cvtColor(screenshot_cv[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, *BAR_GREEN) > 0
    yellow = cv2.inRange(hsv, *BAR_YELLOW) > 0
    dark = (hsv[:, :, 2] <= BAR_DARK_V) & (hsv[:, :, 1] < BAR_DARK_S)
    min_length = BAR_MIN_LENGTH * BAR_LENGTH * scale

    # ХП: строка с самой длинной зелёной заливкой в верхней части окна (ниже — уже энергия)
    hp_rows = green[:int((BAR_AREA_Y[1] - BAR_AREA_Y[0]) * scale)].sum(axis=1)
    if hp_rows.size == 0 or hp_rows.max() < 3:
        return result  # зелёной полоски нет: титан мёртв, слот пуст или окно ещё не дорисовано
    hp_row = int(np.argmax(hp_rows))
    result["hp"] = _bar_percent(green[hp_row], dark[hp_row], min_length)

    # Энергия: ниже ХП. Жёлтой заливки нет — значит энергия 0: берём строку с самой длинной чёрной полоской
    top = hp_row + int(ENERGY_BELOW[0] * scale)
    bottom = min(green.shape[0], hp_row + int(ENERGY_BELOW[1] * scale) + 1)
    if top >= bottom:
        return result
    yellow_rows = yellow[top:bottom].sum(axis=1)
    if yellow_rows.max() >= 3:
        row = top + int(np.argmax(yellow_rows))
    else:
        row = top + int(np.argmax(dark[top:bottom].sum(axis=1)))
    result["energy"] = _bar_percent(yellow[row], dark[row], min_length)
    return result