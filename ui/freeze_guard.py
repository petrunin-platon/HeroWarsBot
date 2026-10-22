"""Сторож окна программы (задача 15): окно перестало отвечать — записать, где застрял код.

Окно раз в полсекунды ставит «отметку жизни» (root.after). Отдельный поток только смотрит на эту отметку и окно не трогает
(виджеты Tk из другого потока трогать нельзя). Отметки нет 5 с — значит, главный поток чем-то занят и Windows вот-вот
напишет «Не отвечает». Тогда поток записывает в bot_data/debug/ui_freeze_<время>.txt, на какой строке сейчас каждый поток
(faulthandler), и одну строку в консоль. Пока окно снова не ожило, второй раз не пишет.

Поток фоновый (daemon): закрыть программу он не мешает. stop() — при закрытии окна (и само по событию <Destroy> окна).
Модуль не импортирует tkinter (ошибки окна ловятся как Exception) — его можно проверить тестом без экрана.
"""
import datetime
import faulthandler
import os
import sys
import threading
import time

import data_paths

HEARTBEAT_MS = 500   # как часто окно ставит отметку
FREEZE_S = 5.0       # столько без отметки — считаем, что окно зависло
CHECK_S = 1.0        # как часто поток смотрит на отметку


class FreezeGuard:
    def __init__(self, root, folder=None, freeze_s=FREEZE_S, clock=time.monotonic):
        self.root = root
        self.folder = folder
        self.freeze_s = freeze_s
        self.clock = clock
        self.last_beat = clock()
        self.reported = False
        self.reports = []
        self._stopped = threading.Event()
        self._after_id = None

    def start(self):
        """Начать отметки и запустить поток-наблюдатель. Вызывать из главного потока после создания окна."""
        self._beat()
        try:
            self.root.bind("<Destroy>", self._on_destroy, add="+")
        except Exception:  # окно уже закрыто
            pass
        threading.Thread(target=self._watch, name="ui-freeze-guard", daemon=True).start()
        return self

    def stop(self):
        self._stopped.set()
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _on_destroy(self, event):
        if event.widget is self.root:
            self.stop()

    def _beat(self):
        """Отметка жизни (в главном потоке)."""
        if self._stopped.is_set():
            return
        self.last_beat = self.clock()
        self.reported = False
        try:
            self._after_id = self.root.after(HEARTBEAT_MS, self._beat)
        except Exception:  # окно уже закрыто
            self._stopped.set()

    def _watch(self):
        while not self._stopped.wait(CHECK_S):
            self.check()

    def check(self):
        """Одна проверка (в потоке-наблюдателе). Возвращает путь к записанному файлу или None."""
        if self._stopped.is_set() or self.reported:
            return None
        stuck = self.clock() - self.last_beat
        if stuck < self.freeze_s:
            return None
        self.reported = True
        return self._report(stuck)

    def _report(self, stuck):
        folder = self.folder or data_paths.debug_dir()
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"ui_freeze_{datetime.datetime.now():%Y%m%d_%H%M%S}.txt")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"Окно программы не отвечает {stuck:.0f} с. Где сейчас код "
                        f"(в каждом потоке последняя строка — сверху):\n\n")
                f.flush()
                faulthandler.dump_traceback(file=f, all_threads=True)
        except OSError as e:
            print(f"[GUI] Окно не отвечает {stuck:.0f} с, но записать отчёт не удалось: {e}", file=sys.__stderr__)
            return None
        self.reports.append(path)
        print(f"[GUI] Окно не отвечает {stuck:.0f} с. Где застрял код — в файле {path}", file=sys.__stderr__,
              flush=True)
        return path
