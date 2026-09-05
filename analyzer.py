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
    # ЧИСТАЯ МАТЕМАТИКА ОТ ШИРИНЫ (Твой оригинальный паттерн)
    # =====================================================================
    w = clean_rect["width"]
    scale_x = w / 939.0
    
    # Длина эталонной полоски растягивается вместе с игрой
    max_bar_width = 50.0 * scale_x
    # =====================================================================
    
    print(f"\n[АНАЛИЗАТОР] Чистая зона игры: {clean_rect['width']}x{clean_rect['height']}")
    print(f"[АНАЛИЗАТОР] Масштаб: {scale_x:.3f}x | Эталон полоски: {max_bar_width:.2f}px")
    
    for titan in current_pack:
        icon_name = f"res_{titan}.png"
        template = imread_cyrillic(icon_name)
        
        if template is None:
            template = imread_cyrillic(f"res_{titan}")
            
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
            
            # =====================================================================
            # ВОЗВРАТ ТВОЕЙ ШИРОКОЙ РАМКИ ПОИСКА (Масштабируемой)
            # =====================================================================
            SHIFT_DOWN = int(icon_h * 1.6) 
            BOX_HEIGHT = int(icon_h * 0.70) 
            
            # Твой оригинальный отступ 15, но растянутый под DPI/разрешение
            EXPAND_WIDTH = int(15 * scale_x) 
            
            crop_y1 = min(y_start + SHIFT_DOWN, screenshot_cv.shape[0])
            crop_y2 = min(crop_y1 + BOX_HEIGHT, screenshot_cv.shape[0])
            
            crop_x1 = max(x_start - EXPAND_WIDTH, 0)
            crop_x2 = min(x_start + icon_w + EXPAND_WIDTH, screenshot_cv.shape[1]) 
            # =====================================================================
            
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

            # ЧИСТЫЙ процент, никаких "магнитов" и накруток.
            hp_perc = min(int((hp_w / max_bar_width) * 100), 100)
            ep_perc = min(int((ep_w / max_bar_width) * 100), 100)
            
            # =====================================================================
            # ФИКС ЛОГИКИ СМЕРТИ: Нет зеленой полоски = Титан мертв!
            # =====================================================================
            if hp_perc == 0:
                team_status[titan] = {"hp": 0, "energy": 0, "status": "МЕРТВ"}
                print(f" ---> {titan.upper()}: [МЕРТВ] (ХП = 0%)")
            else:
                team_status[titan] = {"hp": hp_perc, "energy": ep_perc, "status": "ЖИВ"}
                print(f" ---> {titan.upper()}: ХП {hp_perc}%, Энергия {ep_perc}%")
            # =====================================================================
                
        else:
            team_status[titan] = {"hp": 0, "energy": 0, "status": "МЕРТВ"}
            print(f" ---> {titan.upper()}: [МЕРТВ] (Иконка не найдена. Совпадение: {max_val:.2f})")
            
    print("[АНАЛИЗАТОР] Сканирование завершено.\n")
    return team_status