# analyzer.py
import cv2
import numpy as np
import os
from vision import imread_cyrillic, get_clean_game_screen

def scan_enemy_team(window_rect, sct, all_titans, btn_local_x):
    """
    Сканирует маленькие иконки врагов в точных рамках.
    Использует чистую геометрию игры без черных полос.
    """
    screenshot_cv, clean_rect = get_clean_game_screen(window_rect, sct)
    
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
            
        res = cv2.matchTemplate(roi_img, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        
        if max_val >= 0.72:  
            enemies_found.append(titan)
            
    print(f"[АНАЛИЗАТОР] Обнаружены враги: {enemies_found}")
    return enemies_found

def scan_team_health(window_rect, sct, current_pack):
    """
    Сканирование здоровья и энергии титанов на окне результатов.
    Абсолютная адаптивность: зона поиска и формула меняются вместе с разрешением.
    """
    screenshot_cv, clean_rect = get_clean_game_screen(window_rect, sct)
    hsv = cv2.cvtColor(screenshot_cv, cv2.COLOR_BGR2HSV)
    
    # Зеленая маска для ХП
    lower_green = np.array([45, 100, 100])
    upper_green = np.array([75, 255, 255])
    mask_green = cv2.inRange(hsv, lower_green, upper_green)
    
    # Маска энергии
    lower_yellow = np.array([18, 150, 170])
    upper_yellow = np.array([32, 255, 255])
    mask_energy = cv2.inRange(hsv, lower_yellow, upper_yellow)
    
    team_status = {}
    
    # =====================================================================
    # ЧИСТАЯ МАТЕМАТИКА ОТ ШИРИНЫ 
    # =====================================================================
    w = clean_rect["width"]
    scale_x = w / 939.0
    
    max_bar_width = 50.0 * scale_x
    
    print(f"\n[АНАЛИЗАТОР] Чистая зона игры: {clean_rect['width']}x{clean_rect['height']}")
    print(f"[АНАЛИЗАТОР] Масштаб: {scale_x:.3f}x | Эталон полоски: {max_bar_width:.2f}px")
    
    for titan in current_pack:
        icon_name = f"res_{titan}.png"
        template = imread_cyrillic(icon_name)
        
        if template is None:
            # ИСПРАВЛЕН БАГ: Добавлено расширение .png в строку фолбэка
            template = imread_cyrillic(f"res_{titan}.png")
            
        if template is None:
            print(f"[ОШИБКА] Не найдена иконка в RAM/диске: {icon_name}")
            continue
            
        CROP_SIDES = 4 
        if template.shape[1] > CROP_SIDES * 3:
            template = template[:, CROP_SIDES:-CROP_SIDES]

        if template.shape[0] > screenshot_cv.shape[0] or template.shape[1] > screenshot_cv.shape[1]:
            continue

        res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        
        if max_val >= 0.62:
            icon_h, icon_w = template.shape[:-1]
            x_start = max_loc[0]
            y_start = max_loc[1]
            
            SHIFT_DOWN = int(icon_h * 1.6) 
            BOX_HEIGHT = int(icon_h * 0.70) 
            EXPAND_WIDTH = int(15 * scale_x) 
            
            crop_y1 = min(y_start + SHIFT_DOWN, screenshot_cv.shape[0])
            crop_y2 = min(crop_y1 + BOX_HEIGHT, screenshot_cv.shape[0])
            
            crop_x1 = max(x_start - EXPAND_WIDTH, 0)
            crop_x2 = min(x_start + icon_w + EXPAND_WIDTH, screenshot_cv.shape[1]) 
            
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
            
            if hp_perc == 0:
                team_status[titan] = {"hp": 0, "energy": 0, "status": "МЕРТВ", "score": float(max_val)}
                print(f" ---> {titan.upper()}: [МЕРТВ] (ХП = 0%, сходство иконки {max_val:.2f})")
            else:
                team_status[titan] = {"hp": hp_perc, "energy": ep_perc, "status": "ЖИВ", "score": float(max_val)}
                print(f" ---> {titan.upper()}: ХП {hp_perc}%, Энергия {ep_perc}%")
                
        else:
            team_status[titan] = {"hp": 0, "energy": 0, "status": "ОТСУТСТВУЕТ", "score": float(max_val)}
            print(f" ---> {titan.upper()}: [ОТСУТСТВУЕТ] (иконка не найдена: сходство {max_val:.2f}, порог 0.62)")
            
    print("[АНАЛИЗАТОР] Сканирование завершено.\n")
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