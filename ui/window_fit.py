"""Размер нового окна программы под экран (задача 15, шаг 2).

Обычно окно 1100×720, можно растянуть, меньше 1000×620 не сжимается (design/README.md, «Размер окна»).
Если экран меньше (ноутбук, масштаб Windows 125–150%, панель задач), окно уменьшается под свободную часть экрана;
если не влезает даже 1000×620 — минимум тоже уменьшается, иначе окно вылезло бы за экран.

Размеры здесь — в пикселях макета: CustomTkinter сам умножает их на масштаб Windows (при 150% окно 1100×720
занимает 1650×1080 настоящих пикселей). Свободная часть экрана и место окна (x, y) — в настоящих пикселях.
Модуль без Tk: расчёт проверяют тесты.
"""
import sys

DEFAULT_SIZE = (1100, 720)
MIN_SIZE = (1000, 620)
# Рамка окна Windows вокруг содержимого, в пикселях макета: слева и справа вместе; заголовок окна и рамка снизу
FRAME_W = 16
FRAME_H = 40


def fit_window(work, scale, size=DEFAULT_SIZE, minimum=MIN_SIZE):
    """work — свободная часть экрана (x, y, ширина, высота) без панели задач, в настоящих пикселях;
    scale — масштаб Windows (1.25 при 125%).
    Возвращает (ширина, высота, мин. ширина, мин. высота, x, y): окно по центру свободной части экрана."""
    wx, wy, ww, wh = work
    scale = scale or 1.0
    room_w = int(ww / scale) - FRAME_W
    room_h = int(wh / scale) - FRAME_H
    width = max(1, min(size[0], room_w))
    height = max(1, min(size[1], room_h))
    min_w, min_h = min(minimum[0], width), min(minimum[1], height)
    x = wx + max(0, (ww - round((width + FRAME_W) * scale)) // 2)
    y = wy + max(0, (wh - round((height + FRAME_H) * scale)) // 2)
    return width, height, min_w, min_h, x, y


def work_area(root):
    """Свободная часть основного экрана (без панели задач) в настоящих пикселях: (x, y, ширина, высота).
    В Windows — SystemParametersInfo(SPI_GETWORKAREA); иначе (и при ошибке) — весь экран."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            rect = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
                return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
        except Exception:
            pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()
