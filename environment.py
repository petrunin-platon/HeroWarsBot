import subprocess
import time
import pygetwindow as gw

def launch_scrcpy(target_title="HeroWarsBot_Arena"):
    # Используем гибкий поиск по части имени
    existing = [w for w in gw.getAllWindows() if target_title in w.title]
    
    if not existing:
        print("[СИСТЕМА] Запускаю подключение к телефону (scrcpy)...")
        try:
            subprocess.Popen([
                "scrcpy", 
                "--window-title", target_title,
                "--stay-awake",         
                # Флаг "--turn-screen-off" удален, чтобы дисплей физически загорался
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            print("[ФАТАЛЬНАЯ ОШИБКА] Программа scrcpy не установлена или не добавлена в PATH!")
            return False
            
        print("[СИСТЕМА] Ожидаю появления окна (до 20 секунд)...")
        
        timeout = 20
        start_wait = time.time()
        while time.time() - start_wait < timeout:
            time.sleep(1.0)
            windows = [w for w in gw.getAllWindows() if target_title in w.title]
            if windows:
                time.sleep(2.0) # Даем ОС время на отрисовку интерфейса
                return True
                
        print("[ФАТАЛЬНАЯ ОШИБКА] Окно так и не появилось. Возможно, телефон заблокирован.")
        return False
        
    return True

def calibrate_window(target_title="HeroWarsBot_Arena", base_width=956, base_height=457):
    windows = [w for w in gw.getAllWindows() if target_title in w.title]
    if not windows:
        return False
        
    win = windows[0]
    
    if win.isMaximized:
        win.restore()
        time.sleep(0.5)
        
    print(f"[СИСТЕМА] Калибровка окна до {base_width}x{base_height}...")
    
    if win.width != base_width or win.height != base_height:
        win.resizeTo(base_width, base_height)
        
    win.moveTo(50, 50)
    
    try:
        win.activate()
    except Exception:
        pass 
        
    time.sleep(1) 
    return True