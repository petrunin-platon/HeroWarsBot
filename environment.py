import subprocess
import time
import pygetwindow as gw

def launch_scrcpy(target_title="HeroWarsBot_Arena"):
    # Используем гибкий поиск по части имени
    existing = [w for w in gw.getAllWindows() if target_title in w.title]
    
    if not existing:
        print("[СИСТЕМА] Запускаю подключение к телефону (scrcpy)...")
        try:
            # Сохраняем объект процесса в переменную proc
            proc = subprocess.Popen([
                "scrcpy", 
                "--window-title", target_title,
                "--stay-awake",         
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
        except FileNotFoundError:
            print("[ФАТАЛЬНАЯ ОШИБКА] Программа scrcpy не установлена или не добавлена в PATH!")
            return None
            
        print("[СИСТЕМА] Ожидаю появления окна (до 20 секунд)...")
        
        timeout = 20
        start_wait = time.time()
        while time.time() - start_wait < timeout:
            time.sleep(1.0)
            windows = [w for w in gw.getAllWindows() if target_title in w.title]
            if windows:
                time.sleep(2.0) # Даем ОС время на отрисовку интерфейса
                return proc # ВОЗВРАЩАЕМ ОБЪЕКТ ПРОЦЕССА В ИНТЕРФЕЙС
                
        print("[ФАТАЛЬНАЯ ОШИБКА] Окно так и не появилось. Возможно, телефон заблокирован.")
        proc.terminate() # Убиваем зависший процесс, если окно не прогрузилось
        return None
        
    # Если окно уже было запущено
    return "ALREADY_RUNNING"

def calibrate_window(target_title="HeroWarsBot_Arena", base_width=1606, base_height=748):
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
    except Exception as e:
        print(f"[ОКРУЖЕНИЕ] Ошибка активации окна (фокус отклонен ОС): {e}") 
        
    time.sleep(1) 
    return True