# navigation.py
import time
from config import CONFIDENCE_THRESHOLD
from vision import click_human, get_match_loc, find_and_click_bulletproof

def enter_dungeon_room(window_rect, sct):
    coords = get_match_loc('flag_enter.png', window_rect, sct, CONFIDENCE_THRESHOLD)
    if not coords:
        return False
        
    print("[НАВИГАЦИЯ] Вижу дверь на этаже. Начинаю вход...")
    
    for attempt in range(4):
        current_coords = get_match_loc('flag_enter.png', window_rect, sct, CONFIDENCE_THRESHOLD)
        if current_coords:
            global_x, global_y = current_coords
            click_human(global_x, global_y, exact=True) 
            
            wait_start = time.time()
            flag_disappeared = False
            while time.time() - wait_start < 1.5:
                if not get_match_loc('flag_enter.png', window_rect, sct, CONFIDENCE_THRESHOLD):
                    flag_disappeared = True
                    break
                time.sleep(0.1)
            
            if flag_disappeared:
                print("[НАВИГАЦИЯ] Флаг входа исчез, ожидаю кнопку 'btn_attack.png'...")
                start_time = time.time()
                while time.time() - start_time < 6.0:
                    if get_match_loc('btn_attack.png', window_rect, sct, 0.68):
                        print("[УСПЕХ] Окно выбора комнат открылось.")
                        time.sleep(0.2)
                        return True
                    time.sleep(0.15)
                
                print("[ОШИБКА] Флаг исчез, но окно атаки не появилось (лаги?).")
                return False 
            else:
                print(f"[ПОВТОР] Клик не прошел (попытка {attempt + 1}/4). Жму еще раз...")
        else:
            print("[ПОВТОР] Флаг потерян из виду, перепроверяю...")
            time.sleep(0.5)
            
    print("[ОШИБКА] Не удалось зайти в дверь.")
    return False

def check_and_activate_checkpoint(window_rect, sct):
    # ЖЕСТКАЯ ЗАЩИТА: Если на экране есть дверь, значит этаж ЕЩЕ НЕ ПРОЙДЕН!
    # Игнорируем кнопку чекпоинта, даже если она отрендерилась на заднем фоне.
    if get_match_loc('flag_enter.png', window_rect, sct, 0.75):
        return False

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