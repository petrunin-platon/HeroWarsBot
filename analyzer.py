import cv2
import numpy as np
import os
# ИСПРАВЛЕНИЕ: Импортируем кэшированную версию imread_cyrillic из vision.py
from vision import get_asset_path, imread_cyrillic

def scan_enemy_team(window_rect, sct, all_titans, btn_local_x):
    """
    Сканирует маленькие иконки врагов (enemy_*.png) в точных рамках 
    над кнопкой выбора комнаты.
    """
    screenshot = sct.grab(window_rect)
    img = np.array(screenshot)
    screenshot_cv = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    
    w = window_rect["width"]
    h = window_rect["height"]
    
    roi_y_start = int(h * (140 / 449))  
    roi_y_end = int(h * ((140 + 85) / 449)) 
    
    if btn_local_x < w * 0.4:
        roi_x_start = int(w * (140 / 939))
        roi_x_end = int(w * ((140 + 310) / 939))
        print("[АНАЛИЗАТОР] Сканирую ЛЕВУЮ комнату врагов...")
    elif btn_local_x > w * 0.6:
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
            
        res = cv2.matchTemplate(roi_img, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        
        if max_val >= 0.72:  
            enemies_found.append(titan)
            
    print(f"[АНАЛИЗАТОР] Обнаружены враги: {enemies_found}")
    return enemies_found

def scan_team_health(window_rect, sct, current_pack):
    """
    Сканирование здоровья и энергии титанов.
    """
    screenshot = sct.grab(window_rect)
    img = np.array(screenshot)
    screenshot_cv = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    hsv = cv2.cvtColor(screenshot_cv, cv2.COLOR_BGR2HSV)
    
    # 1. МАСКА ЗДОРОВЬЯ (Зеленая) 
    lower_green = np.array([45, 100, 100])
    upper_green = np.array([75, 255, 255])
    mask_green = cv2.inRange(hsv, lower_green, upper_green)
    
    # 2. МАСКА ЭНЕРГИИ (Желтая + Белое свечение)
    lower_yellow = np.array([12, 80, 150])
    upper_yellow = np.array([40, 255, 255])
    mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)
    
    # Ловим чистое белое свечение от 100% заряда
    lower_white = np.array([0, 0, 220])
    upper_white = np.array([180, 45, 255])
    mask_white = cv2.inRange(hsv, lower_white, upper_white)
    
    # Объединяем желтый и белый для поиска энергии
    mask_energy = cv2.bitwise_or(mask_yellow, mask_white)
    
    team_status = {}
    w = window_rect["width"]
    base_window_width = 939
    base_bar_width = 50.0
    max_bar_width = max(1, int(base_bar_width * (w / base_window_width)))
    
    print(f"\n[АНАЛИЗАТОР] Текущее окно: {window_rect['width']}x{window_rect['height']}")
    print("[АНАЛИЗАТОР] Сканирую здоровье и энергию...")
    
    for titan in current_pack:
        path = get_asset_path(f"{titan}.png")
        template = imread_cyrillic(path)
        if template is None:
            continue
            
        res = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        
        if max_val >= 0.7:
            avatar_h, avatar_w = template.shape[:-1]
            x_center = max_loc[0] + (avatar_w // 2)
            y_start = max_loc[1]
            
            roi_x_start = max(0, x_center - 35)
            roi_x_end = min(screenshot_cv.shape[1], x_center + 35)
            
            # Оригинальные точные рамки высоты
            roi_y_start = y_start + avatar_h - 2
            roi_y_end = roi_y_start + 35 
            
            # --- СКАНИРОВАНИЕ ХП ---
            roi_green = mask_green[roi_y_start:roi_y_end, roi_x_start:roi_x_end]
            green_row_sums = np.sum(roi_green == 255, axis=1)
            
            hp_w, hp_y = 0, -1 
            if len(green_row_sums) > 0:
                max_green_pixels = np.max(green_row_sums)
                if max_green_pixels >= 3:
                    hp_y = np.argmax(green_row_sums)
                    hp_w = max_green_pixels

            # --- СКАНИРОВАНИЕ ЭНЕРГИИ ---
            ep_w = 0
            if hp_y != -1:
                # Отступаем от ХП на 2-15 пикселей вниз
                search_start = hp_y + 2
                search_end = min(roi_y_end - roi_y_start, hp_y + 15)
                if search_start < search_end:
                    roi_energy = mask_energy[roi_y_start + search_start : roi_y_start + search_end, roi_x_start:roi_x_end]
                    energy_row_sums = np.sum(roi_energy == 255, axis=1)
                    if len(energy_row_sums) > 0:
                        max_energy_pixels = np.max(energy_row_sums)
                        if max_energy_pixels >= 3:
                            ep_w = max_energy_pixels

            # --- РАСЧЕТ ПРОЦЕНТОВ ---
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