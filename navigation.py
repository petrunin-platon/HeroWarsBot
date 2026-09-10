# navigation.py
import time
from config import CONFIDENCE_THRESHOLD
from vision import click_human, get_match_loc, find_and_click_bulletproof, wait_for_ui_element

def smart_navigate_hallway(window_rect, sct):
    print("[НАВИГАЦИЯ] Сканирую коридор (динамическое ожидание)...")
    wait_start = time.time()
    
    while time.time() - wait_start < 10.0:
        # 1. Приоритет 1: Кнопка атаки (уже стоим у открытой двери)
        if get_match_loc('btn_attack.png', window_rect, sct, 0.68):
            return "ROOM_SELECTION"
            
        # 2. Приоритет 2: Флаг двери (перехватывает фокус до чекпоинта)
        flag_coords = get_match_loc('flag_enter.png', window_rect, sct, CONFIDENCE_THRESHOLD)
        if flag_coords:
            print("[НАВИГАЦИЯ] Дверь зафиксирована. Начинаю вход...")
            click_human(flag_coords[0], flag_coords[1])
            
            # Ждем окно выбора комнат
            if wait_for_ui_element('btn_attack.png', window_rect, sct, 0.68, timeout=4.0, settle_time=0.2):
                print("[УСПЕХ] Окно выбора комнат открылось.")
                time.sleep(0.2)
                return "ROOM_SELECTION"
            else:
                print("[ОШИБКА] Окно атаки не появилось после клика в дверь (лаги?).")
                return "HALLWAY" # Возвращаемся в цикл
                
        # 3. Приоритет 3: Точка сохранения (сработает ТОЛЬКО если нет флага двери)
        checkpoint_coords = get_match_loc('btn_activate.png', window_rect, sct, CONFIDENCE_THRESHOLD)
        if checkpoint_coords:
            print("[НАВИГАЦИЯ] Этаж пройден! Активируем точку сохранения...")
            click_human(checkpoint_coords[0], checkpoint_coords[1])
            
            print("[НАВИГАЦИЯ] Жду окно с наградой...")
            claim_coords = wait_for_ui_element('btn_claim.png', window_rect, sct, CONFIDENCE_THRESHOLD, timeout=8.0, settle_time=0.2)
            
            if claim_coords:
                click_human(claim_coords[0], claim_coords[1])
                print("[НАВИГАЦИЯ] Награда забрана. Спускаемся на следующий этаж...")
                time.sleep(4.0) 
                return "HALLWAY"
            else:
                print("[ОШИБКА НАВИГАЦИИ] Окно с наградой так и не появилось.")
                return "HALLWAY"
                
        time.sleep(0.1) # Сверхбыстрый поллинг экрана
        
    print("[НАВИГАЦИЯ] Таймаут в коридоре (10 сек). Перезапуск цикла...")
    return "HALLWAY"