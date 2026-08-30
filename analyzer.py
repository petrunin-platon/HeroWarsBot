# analyzer.py
import cv2
import numpy as np
import os
from vision import get_asset_path, imread_cyrillic, get_clean_game_screen

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
        path = get_asset_path(f"enemy_{titan}.png")
        template = imread_cyrillic(path)
        if template is None:
            print(f"[ОШИБКА АССЕТА] Не найден шаблон врага: {path}")
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
    Сканирование здоровья и энергии титанов.
    Полностью динамическое масштабирование ROI.
    """
    screenshot_cv, clean_rect = get_clean_game_screen(window_rect, sct)
    hsv = cv2.cvtColor(screenshot_cv, cv2.COLOR_BGR2HSV)
    
    # Цветовые маски
    lower_green = np.array([45, 100, 100])
    upper_green = np.array([75, 255, 255])
    mask_green = cv2.inRange(hsv, lower_green, upper_green)
    
    lower_yellow = np.array([12, 80, 150])
    upper_yellow = np.array([40, 255, 255])
    mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)
    
    lower_white = np.array([0, 0, 220])
    upper_white = np.array([180, 45, 255])
    mask_white = cv2.inRange(hsv, lower_white, upper_white)
    
    mask_energy = cv2.bitwise_or(mask_yellow, mask_white)
    
    team_status = {}
    
    w = clean_rect["width"]
    base_window_width = 939
    scale_ratio = w / base_window_width
    
    base_bar_width = 50.0
    max_bar_width = max(1, int(base_bar_width * scale_ratio))
    
    # =====================================================================
    # ИСПРАВЛЕНИЕ: ДИНАМИЧЕСКИЕ РАМКИ (ROI)
    # Масштабируем область поиска пропорционально размеру экрана
    # =====================================================================
    roi_offset_x = int(45 * scale_ratio) # Динамическая ширина поиска (было жестко 35)
    roi_offset_y = int(50 * scale_ratio) # Динамическая высота поиска вниз (было жестко 35)
    noise_threshold = max(2, int(3 * scale_ratio)) # Адаптивный фильтр шума
    
    print(f"\n[АНАЛИЗАТОР] Чистая зона игры: {clean_rect['width']}x{clean_rect['height']}")
    print(f"[АНАЛИЗАТОР] Масштаб UI: {scale_ratio:.2f}x | Зона сканирования (ROI): ±{roi_offset_x}px X, +{roi_offset_y}px Y")
    print("[АНАЛИЗАТОР] Сканирую здоровье и энергии...")
    
    for titan in current_pack:
        path = get_asset_path(f"{titan}.png")
        template = imread_cyrillic(path)
        if template is None:
            continue
            
        if template.shape[0] > screenshot_cv.shape[0] or template.shape[1] > screenshot_cv.shape[1]:
            continue

        res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        
        if max_val >= 0.7:
            avatar_h, avatar_w = template.shape[:-1]
            x_center = max_loc[0] + (avatar_w // 2)
            y_start = max_loc[1]
            
            # 1. Формируем динамические координаты прямоугольника поиска (ROI)
            roi_x_start = max(0, x_center - roi_offset_x)
            roi_x_end = min(screenshot_cv.shape[1], x_center + roi_offset_x)
            
            roi_y_start = y_start + avatar_h - int(2 * scale_ratio)
            roi_y_end = roi_y_start + roi_offset_y
            
            # Защита от вылета за пределы экрана при обрезке OpenCV
            roi_y_end = min(screenshot_cv.shape[0], roi_y_end)
            roi_y_start = max(0, min(roi_y_start, roi_y_end - 1))
            
            # 2. Ищем зеленое ХП
            roi_green = mask_green[roi_y_start:roi_y_end, roi_x_start:roi_x_end]
            green_row_sums = np.sum(roi_green == 255, axis=1)
            
            hp_w, hp_y = 0, -1 
            if len(green_row_sums) > 0:
                max_green_pixels = np.max(green_row_sums)
                if max_green_pixels >= noise_threshold:
                    hp_y = np.argmax(green_row_sums)
                    hp_w = max_green_pixels

            # 3. Ищем Энергию СТРОГО под линией ХП
            ep_w = 0
            if hp_y != -1:
                search_start = hp_y + int(2 * scale_ratio)
                search_end = min(roi_y_end - roi_y_start, hp_y + int(15 * scale_ratio))
                
                if search_start < search_end:
                    roi_energy = mask_energy[roi_y_start + search_start : roi_y_start + search_end, roi_x_start:roi_x_end]
                    energy_row_sums = np.sum(roi_energy == 255, axis=1)
                    if len(energy_row_sums) > 0:
                        max_energy_pixels = np.max(energy_row_sums)
                        if max_energy_pixels >= noise_threshold:
                            ep_w = max_energy_pixels

            # 4. Вычисляем проценты
            hp_perc = min(int((hp_w / max_bar_width) * 100), 100)
            ep_perc = min(int((ep_w / max_bar_width) * 100), 100)
            
            if ep_perc < 3: ep_perc = 0
            
            if hp_perc == 0:
                team_status[titan] = {"hp": 0, "energy": 0, "status": "МЕРТВ"}
                print(f" ---> {titan.upper()}: [МЕРТВ]")
            else:
                team_status[titan] = {"hp": hp_perc, "energy": ep_perc, "status": "ЖИВ"}
                print(f" ---> {titan.upper()}: ХП {hp_perc}%, Энергия {ep_perc}%")
            
    print("[АНАЛИЗАТОР] Сканирование завершено.\n")
    return team_status