# navigation.py
import time
from config import CONFIDENCE_THRESHOLD
from vision import click_human, get_match_loc, find_and_click_bulletproof

def enter_dungeon_room(window_rect, sct):
    # Первичное сканирование (чтобы не спамить логи, если мы вообще не в коридоре)
    coords = get_match_loc('flag_enter.png', window_rect, sct, CONFIDENCE_THRESHOLD)
    if not coords:
        return False
        
    print("[НАВИГАЦИЯ] Вижу дверь на этаже. Начинаю вход...")
    
    for attempt in range(3):
        # ДИНАМИЧЕСКОЕ СКАНИРОВАНИЕ: берем актуальные координаты, так как комната может ехать
        current_coords = get_match_loc('flag_enter.png', window_rect, sct, CONFIDENCE_THRESHOLD)
        if current_coords:
            global_x, global_y = current_coords
            click_human(global_x, global_y)
            time.sleep(0.4) # Микропауза для реакции игры
        
        # Сразу проверяем: если флаг исчез, значит комната центрировалась и открывается
        if not get_match_loc('flag_enter.png', window_rect, sct, CONFIDENCE_THRESHOLD):
            print("[НАВИГАЦИЯ] Флаг входа исчез, ожидаю кнопку 'btn_attack.png'...")
            start_time = time.time()
            # Увеличен таймаут загрузки окна боя (было 3.0, стало 5.0 для загруженных ПК)
            while time.time() - start_time < 5.0:
                if get_match_loc('btn_attack.png', window_rect, sct, CONFIDENCE_THRESHOLD):
                    print("[УСПЕХ] Окно выбора комнат открылось.")
                    time.sleep(0.2)
                    return True
                time.sleep(0.15)
        else:
            print("[ПОВТОР] Комната в движении или клик не прошел. Жму еще раз...")
            
    print("[ОШИБКА] Не удалось зайти в дверь.")
    return False

def check_and_activate_checkpoint(window_rect, sct):
    # Увеличен таймаут клика с 3.0 до 6.0 секунд (компенсирует просадки FPS и лаги процессора)
    if find_and_click_bulletproof('btn_activate.png', window_rect, sct, CONFIDENCE_THRESHOLD, timeout=6.0):
        print("[НАВИГАЦИЯ] Этаж пройден! Активируем точку сохранения...")
        print("[НАВИГАЦИЯ] Жду появления окна с наградой...")
        
        start_wait = time.time()
        claimed = False
        while time.time() - start_wait < 15.0:
            if find_and_click_bulletproof('btn_claim.png', window_rect, sct, CONFIDENCE_THRESHOLD, timeout=8.0):
                claimed = True
                break
            time.sleep(0.5)
            
        if claimed:
            print("[НАВИГАЦИЯ] Награда забрана. Спускаемся на следующий этаж...")
            time.sleep(4.0) 
            return True
        else:
            print("[ОШИБКА НАВИГАЦИИ] Окно с наградой так и не появилось.")
            return False
            
    return False