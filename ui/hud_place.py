"""Где стоит мини-бар (задача 15, шаг 4): вплотную под картинкой игры в окне scrcpy, не заходя на неё ни на пиксель.

Почему не по рамке окна: у Windows 10/11 вокруг окна невидимая рамка ~7 px, поэтому место берётся по клиентской
области окна (GetClientRect + ClientToScreen) — это и есть картинка игры. Ширина мини-бара — ширина этой области.

Как бот снимает экран (vision.py): снимок всего прямоугольника окна (pygetwindow, вместе с невидимой рамкой), а при
первом снимке ищет в нём игру, отрезав снизу 8 px (vision._calibrate_geometry: border_w = 8). Мини-бар под клиентской
областью попадает в невидимую рамку снизу — её бот отрезает. Если рамка толще 8 px (крупный масштаб Windows), мини-бар
опускается ровно до отрезанной части: тогда он не попадёт в игру, даже когда бот ищет её в первый раз.

Не влезает под окно (низ экрана, панель задач) — встаёт над заголовком окна (это вне снимка бота); не влезает
и туда — не показывается (окно программы остаётся свёрнутым, кнопка на панели задач).

Всё про Windows (поиск окна, координаты, «не делать активным») — в функциях win_*; вне Windows их нет,
а расчёт места (place) проверяют тесты на поддельных прямоугольниках. Модуль без Tk.
"""
import sys

BOT_BOTTOM_CROP = 8      # столько пикселей снизу бот отрезает от снимка окна, когда ищет игру (vision.py)


class Rect:
    """Прямоугольник на экране в настоящих пикселях: left, top, right, bottom (right и bottom — не включая)."""

    __slots__ = ("left", "top", "right", "bottom")

    def __init__(self, left, top, right, bottom):
        self.left, self.top, self.right, self.bottom = int(left), int(top), int(right), int(bottom)

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.bottom - self.top

    def as_tuple(self):
        return self.left, self.top, self.right, self.bottom

    def __eq__(self, other):
        return isinstance(other, Rect) and self.as_tuple() == other.as_tuple()

    def __repr__(self):
        return f"Rect{self.as_tuple()}"


class GameWindow:
    """Окно игры глазами мини-бара: client — картинка игры, frame — прямоугольник окна (как его снимает бот),
    work — свободная часть экрана, на котором окно (без панели задач)."""

    __slots__ = ("client", "frame", "work", "hwnd")

    def __init__(self, client, frame, work, hwnd=None):
        self.client, self.frame, self.work, self.hwnd = client, frame, work, hwnd


def place(game, height):
    """(x, y, ширина, высота, «снизу» или «сверху») для мини-бара высотой height или None, если ему нет места.
    Мини-бар никогда не заходит на картинку игры и на ту часть окна, где бот ищет игру."""
    client, frame, work = game.client, game.frame, game.work
    if client.width < 100 or client.height < 100:
        return None
    x, width = client.left, client.width
    # Ниже картинки игры и ниже той части окна, где бот при первом снимке ищет игру
    below = max(client.bottom, frame.bottom - BOT_BOTTOM_CROP)
    if below + height <= work.bottom:
        return x, below, width, height, "below"
    above = frame.top - height                # над заголовком окна: это вне снимка бота
    if above >= work.top:
        return x, above, width, height, "above"
    return None


# ── Windows ────────────────────────────────────────────────────────────────
_USER32 = None


def _user32():
    """Своя копия user32 с правильными типами (номер окна 64-битный), как в ui/hotkeys.py: ctypes.windll.user32
    не трогаем — им пользуется pygetwindow."""
    global _USER32
    if _USER32 is None:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32")
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.FindWindowW.restype = wintypes.HWND
        user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.IsIconic.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromWindow.restype = wintypes.HMONITOR
        user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.c_void_p]
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
        user32.GetAncestor.restype = wintypes.HWND
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
            user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
            user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        else:  # 32-битный Python: в user32 есть только GetWindowLongW / SetWindowLongW
            user32.GetWindowLongPtrW = user32.GetWindowLongW
            user32.SetWindowLongPtrW = user32.SetWindowLongW
        _USER32 = user32
    return _USER32


def win_find_game(title):
    """Окно игры (scrcpy, заголовок title — scrcpy ставит его ровно таким) или None: нет окна, оно свёрнуто или скрыто.
    Вызывается из окна программы раз в 0,5 с: FindWindow и координаты — доли миллисекунды, окно не замирает."""
    import ctypes
    from ctypes import wintypes
    user32 = _user32()
    hwnd = user32.FindWindowW(None, title)
    if not hwnd or not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
        return None
    rect = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return None
    corner = wintypes.POINT(0, 0)
    if not user32.ClientToScreen(hwnd, ctypes.byref(corner)):
        return None
    client = Rect(corner.x, corner.y, corner.x + rect.right, corner.y + rect.bottom)
    outer = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(outer)):
        return None
    frame = Rect(outer.left, outer.top, outer.right, outer.bottom)
    return GameWindow(client, frame, _work_area(user32, hwnd) or frame, hwnd)


def _work_area(user32, hwnd):
    """Свободная часть того экрана, где окно игры (без панели задач)."""
    import ctypes
    from ctypes import wintypes

    class MonitorInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD)]

    monitor = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
    info = MonitorInfo()
    info.cbSize = ctypes.sizeof(MonitorInfo)
    if not monitor or not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return None
    work = info.rcWork
    return Rect(work.left, work.top, work.right, work.bottom)


GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000


def win_no_activate(frame_id):
    """Мини-бар не становится активным окном, даже когда по нему щёлкают: активным остаётся окно игры.
    Иначе бот решил бы, что игру перекрыли, и встал ждать (main.py:wait_for_focus). frame_id — wm frame окна Tk."""
    user32 = _user32()
    style = user32.GetWindowLongPtrW(frame_id, GWL_EXSTYLE)
    user32.SetWindowLongPtrW(frame_id, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)


def win_give_back_focus(own_ids, game_hwnd):
    """Если активным всё же стал мини-бар (Windows делает активным только что показанное окно) — вернуть игре."""
    user32 = _user32()
    active = user32.GetForegroundWindow()
    if active and game_hwnd and int(user32.GetAncestor(active, 2) or active) in own_ids:  # GA_ROOT
        user32.SetForegroundWindow(game_hwnd)
        return True
    return False


def windows_available():
    return sys.platform == "win32"
