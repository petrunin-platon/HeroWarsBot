"""Кнопки шапки нового окна (задача 15, шаг 2): выключить экран телефона и сбросить размер окна игры.

Делают то же, что кнопки «ВЫКЛ экран» и «Сброс размера» старой главной (ui/dashboard.py: sleep_phone, reset_window_size),
с теми же строками в журнале. Разница одна: работа идёт в фоновом потоке. В старом окне пауза time.sleep (0,3 и 1 с)
шла прямо в окне, и оно на это время замирало. Строки журнала поток не пишет сам, а передаёт в log — окно кладёт их
в очередь и показывает через after.
Модуль без Tk.
"""
import threading
import time

from config import GAME_WINDOW_TITLE

# Эталонный размер окна scrcpy, под который настроены картинки бота (как в старом окне)
GAME_SIZE = (1606, 748)


def in_background(func, *args):
    threading.Thread(target=func, args=args, daemon=True).start()


def sleep_screen(log, title=GAME_WINDOW_TITLE):
    """Погасить экран телефона: scrcpy делает это по Alt+O в своём окне (игра продолжает работать)."""
    log("[СИСТЕМА] Выключаю физический дисплей (игра продолжит работать)...\n")
    try:
        import pyautogui
        import pygetwindow as gw
        windows = gw.getWindowsWithTitle(title)
        if not windows:
            log("[ОШИБКА] Окно трансляции не найдено.\n")
            return
        win = windows[0]
        if win.isMinimized:
            win.restore()
        win.activate()
        time.sleep(0.3)
        pyautogui.hotkey("alt", "o")
        log("[ИНФО] Экран телефона погашен для экономии батареи!\n")
    except Exception as e:
        log(f"[ОШИБКА] Не удалось отправить команду: {e}\n")


def reset_window_size(log, title=GAME_WINDOW_TITLE):
    """Вернуть окну scrcpy эталонный размер 1606×748 и место (50, 50), как перед стартом фарма."""
    log(f"[GUI] Сброс размеров окна к эталонным ({GAME_SIZE[0]}x{GAME_SIZE[1]})...\n")
    try:
        from environment import calibrate_window
        if not calibrate_window(title, *GAME_SIZE):
            log("[ОШИБКА] Окно трансляции не найдено.\n")
    except Exception as e:
        log(f"[ОШИБКА] Не удалось изменить размер окна: {e}\n")
