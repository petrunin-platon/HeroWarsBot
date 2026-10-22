"""Что показывает шапка и полоска нового окна (задача 15, шаг 2): подключён ли телефон и настроен ли Telegram.

Телефон подключён — есть окно scrcpy с заголовком HeroWarsBot_Arena (так же его ищут environment.py и старое окно).
Telegram настроен — включён и заполнен в profile.yml, по тому же правилу, что у бота (telegram_agent.read_telegram_settings).
Проверка раз в 2 с в фоновом потоке; в очередь events попадают только изменения: ("phone", True), ("telegram", False).
Окно забирает их через after (виджеты Tk из другого потока трогать нельзя).
Модуль без Tk: его проверяют тесты с поддельным поиском окна.
"""
import os
import threading

INTERVAL_S = 2.0


def game_window_exists(title):
    """Есть ли окно scrcpy (как environment.launch_scrcpy: заголовок содержит title)."""
    import pygetwindow as gw
    return any(title in w.title for w in gw.getAllWindows())


def telegram_ready(profile_path="profile.yml"):
    """Telegram включён и в нём есть токен и chat_id (без заглушек YOUR_...)."""
    from telegram_agent import read_telegram_settings
    token, _chat_id, _why = read_telegram_settings(profile_path)
    return bool(token)


class StatusWatcher:
    def __init__(self, events, game_title, window_exists=None, profile_path="profile.yml", interval=INTERVAL_S):
        self.events = events
        self.game_title = game_title
        self.window_exists = window_exists or game_window_exists
        self.profile_path = profile_path
        self.interval = interval
        self.state = {}
        self._profile_mtime = None
        self._stopped = threading.Event()

    def start(self):
        threading.Thread(target=self._run, name="ui-status", daemon=True).start()
        return self

    def stop(self):
        self._stopped.set()

    def check(self):
        """Одна проверка: новое состояние кладётся в очередь, только если оно поменялось."""
        try:
            self._report("phone", bool(self.window_exists(self.game_title)))
        except Exception:
            # Окна Windows не перечислились — не знаем. Прежнее состояние оставляем: с шага 3 «телефона нет» во время
            # фарма останавливает бота (как старое окно), а случайный сбой поиска окон фарм прерывать не должен
            if "phone" not in self.state:
                self._report("phone", False)
        try:
            mtime = os.path.getmtime(self.profile_path)
        except OSError:
            mtime = None
        if mtime != self._profile_mtime or "telegram" not in self.state:
            self._profile_mtime = mtime    # profile.yml перечитываем, только когда он поменялся
            self._report("telegram", mtime is not None and telegram_ready(self.profile_path))

    def _report(self, key, value):
        if self.state.get(key) != value:
            self.state[key] = value
            self.events.put((key, value))

    def _run(self):
        while not self._stopped.is_set():
            self.check()
            self._stopped.wait(self.interval)
