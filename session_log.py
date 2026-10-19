# session_log.py
# Журнал сессии: время в строках лога, автосохранение лога, замер этапов комнаты и итог сессии.
# При импорте ничего не делает (файлы не создаёт, print не меняет) — всё включается вызовом install().
import builtins
import csv
import os
import sys
import threading
import time
import traceback
from contextlib import contextmanager
from datetime import datetime

# Всё, что бот пишет на ПК, лежит в bot_data/ (папка в .gitignore)
BOT_DATA_DIR = "bot_data"
LOGS_SUBDIR = "logs"

# Этапы комнаты. Их сумма — «всего» в строке [ВРЕМЯ]
STAGES = ("hallway", "team", "battle", "result", "rollback")
STAGE_NAMES = {
    "hallway": "коридор",
    "team": "сборка",
    "battle": "бой",
    "result": "результат",
    "rollback": "откат",
}
# Время, которое в этапы не входит и считается отдельно
EXTRA_NAMES = {
    "checkpoint": "точка сохранения",
    "sos_wait": "ожидание решения",
    "screen_lock": "экран заблокирован",
}
COUNT_NAMES = {
    "door_misses": "промахи по двери",
    "repeat_clicks": "повторные нажатия",
    "sos": "окна SOS",
    "rollbacks": "откаты",
    "auto_rollbacks": "из них без вас",
    "stuck": "зависания",
}

CSV_COLUMNS = [
    "time", "room_no", "room_type",
    "hallway_s", "team_s", "battle_s", "result_s", "rollback_s",
    "total_s", "checkpoint_s", "sos_wait_s",
    "door_misses", "repeat_clicks", "sos", "rollbacks", "auto_rollbacks", "stuck",
    "screen_lock_s",
]


# ---------------------------------------------------------------------------
# Время в строках лога
# ---------------------------------------------------------------------------
def format_stamp(now):
    """14:03:21.457"""
    return now.strftime("%H:%M:%S.") + f"{now.microsecond // 1000:03d}"


class Stamper:
    """Ставит время в начало каждой непустой строки. Помнит, закончилась ли прошлая строка."""

    def __init__(self):
        self.at_line_start = True

    def process(self, text, now):
        stamp = format_stamp(now)
        parts = text.split("\n")
        out = []
        for i, part in enumerate(parts):
            if part:
                if self.at_line_start:
                    out.append(stamp + " ")
                out.append(part)
                self.at_line_start = False
            if i < len(parts) - 1:
                out.append("\n")
                self.at_line_start = True
        return "".join(out)


class LogFile:
    """Файл лога сессии. Пишем построчно и сразу сбрасываем на диск, чтобы при аварии ничего не пропало."""

    def __init__(self, directory, started):
        os.makedirs(directory, exist_ok=True)
        self.path = os.path.join(directory, f"bot_log_{started:%Y-%m-%d_%H-%M-%S}.txt")
        self._file = open(self.path, "a", encoding="utf-8")

    def write(self, text):
        self._file.write(text)
        self._file.flush()


# ---------------------------------------------------------------------------
# Форматирование
# ---------------------------------------------------------------------------
def fmt_s(seconds):
    return f"{seconds:.1f} с"


def fmt_duration(seconds):
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours} ч {minutes} мин {secs} с"
    if minutes:
        return f"{minutes} мин {secs} с"
    return f"{secs} с"


def format_room_line(record):
    """[ВРЕМЯ] Комната 37 (mix): коридор 7.9 с | сборка 0.0 с | бой 12.4 с | результат 4.1 с | всего 24.4 с
    Откат, точка сохранения, ожидание решения и счётчики добавляются, только если они были."""
    st = record["stages"]
    parts = [f"{STAGE_NAMES[s]} {fmt_s(st[s])}" for s in ("hallway", "team", "battle", "result")]
    if round(st["rollback"], 1) > 0:
        parts.append(f"{STAGE_NAMES['rollback']} {fmt_s(st['rollback'])}")
    parts.append(f"всего {fmt_s(record['total'])}")
    for key in EXTRA_NAMES:
        if round(st.get(key, 0.0), 1) > 0:
            parts.append(f"{EXTRA_NAMES[key]} {fmt_s(st[key])}")
    for key, name in COUNT_NAMES.items():
        if record["counts"].get(key):
            parts.append(f"{name} {record['counts'][key]}")
    return f"[ВРЕМЯ] Комната {record['room_no']} ({record['room_type']}): " + " | ".join(parts)


# ---------------------------------------------------------------------------
# Таймер этапов одной комнаты
# ---------------------------------------------------------------------------
class RoomTimer:
    """Считает, сколько секунд ушло на каждый этап комнаты.

    begin(этап) — переключиться на другой этап.
    excluded(имя) — отрезок времени (точка сохранения, ожидание вашего решения),
    который уходит в отдельный счётчик и в текущий этап не входит.
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._phase = None
        self._stack = []
        self._since = None
        self._seconds = {}
        self._counts = {}

    def restart(self, phase):
        """Начать комнату заново: накопленное выбрасываем (старт бота, конец паузы)."""
        self._seconds = {}
        self._counts = {}
        self._stack = []
        self._phase = phase
        self._since = self._clock()

    def _current(self):
        return self._stack[-1] if self._stack else self._phase

    def _flush(self):
        now = self._clock()
        current = self._current()
        if current is not None and self._since is not None:
            self._seconds[current] = self._seconds.get(current, 0.0) + (now - self._since)
        self._since = now

    def begin(self, phase):
        if phase == self._phase:
            return
        self._flush()
        self._phase = phase

    @contextmanager
    def excluded(self, name):
        self._flush()
        self._stack.append(name)
        try:
            yield
        finally:
            self._flush()
            self._stack.pop()

    def count(self, name):
        self._counts[name] = self._counts.get(name, 0) + 1

    def finish(self, room_no, room_type, when=None):
        """Закрыть комнату: вернуть запись и начать отсчёт следующей с коридора."""
        self._flush()
        stages = {name: self._seconds.get(name, 0.0) for name in (*STAGES, *EXTRA_NAMES)}
        record = {
            "time": (when or datetime.now()).strftime("%H:%M:%S"),
            "room_no": room_no,
            "room_type": room_type,
            "stages": stages,
            "total": sum(stages[s] for s in STAGES),
            "counts": dict(self._counts),
        }
        self.restart("hallway")
        return record


# ---------------------------------------------------------------------------
# Сессия целиком
# ---------------------------------------------------------------------------
class SessionLog:
    def __init__(self, clock=time.monotonic, directory=None, started=None):
        self._clock = clock
        self.timer = RoomTimer(clock)
        self.records = []
        self.totals = {}
        self.tap_delays = []
        self.stop_reason = None
        self.started = clock()
        self.started_at = started or datetime.now()
        self.directory = directory
        self._csv_path = None
        self._csv_failed = False
        self._summary_printed = False

    # --- события ---
    def count(self, name):
        self.totals[name] = self.totals.get(name, 0) + 1
        self.timer.count(name)

    def track_tap(self, proc, started=None):
        """Замеряет в фоне, сколько секунд выполнялась команда adb tap. Бота не задерживает."""
        started = self._clock() if started is None else started

        def watch():
            try:
                proc.wait()
            except Exception:
                return
            self.tap_delays.append(self._clock() - started)

        thread = threading.Thread(target=watch, daemon=True)
        thread.start()
        return thread

    def set_stop_reason(self, reason, force=False):
        if force or not self.stop_reason:
            self.stop_reason = reason

    def finish_room(self, room_no, room_type):
        """Закрывает комнату, пишет строку в CSV и возвращает строку для лога."""
        record = self.timer.finish(room_no, room_type)
        self.records.append(record)
        self._write_csv(record)
        return format_room_line(record)

    # --- CSV ---
    def _write_csv(self, record):
        if not self.directory or self._csv_failed:
            return
        try:
            if self._csv_path is None:
                os.makedirs(self.directory, exist_ok=True)
                self._csv_path = os.path.join(self.directory, f"timings_{self.started_at:%Y-%m-%d_%H-%M-%S}.csv")
            is_new = not os.path.exists(self._csv_path)
            st, counts = record["stages"], record["counts"]
            row = [
                record["time"], record["room_no"], record["room_type"],
                *(round(st[s], 2) for s in ("hallway", "team", "battle", "result", "rollback")),
                round(record["total"], 2), round(st["checkpoint"], 2), round(st["sos_wait"], 2),
                *(counts.get(k, 0) for k in COUNT_NAMES),
                round(st.get("screen_lock", 0.0), 2),
            ]
            with open(self._csv_path, "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                if is_new:
                    writer.writerow(CSV_COLUMNS)
                writer.writerow(row)
        except OSError as e:
            self._csv_failed = True
            print(f"[ВРЕМЯ] Не удалось записать замеры в CSV: {e}")

    # --- итог ---
    def summary_lines(self, rooms, titanite):
        """Строки блока [ИТОГ]."""
        lines = ["[ИТОГ] ========== Итог сессии =========="]
        lines.append(f"[ИТОГ] Причина остановки: {self.stop_reason or 'не указана'}")
        lines.append(
            f"[ИТОГ] Длительность: {fmt_duration(self._clock() - self.started)} | "
            f"Комнат: {rooms} | Титанит: {titanite}"
        )

        recs = self.records
        if recs:
            n = len(recs)
            avg = {s: sum(r["stages"][s] for r in recs) / n for s in STAGES}
            avg_total = sum(r["total"] for r in recs) / n
            stage_text = " | ".join(f"{STAGE_NAMES[s]} {fmt_s(avg[s])}" for s in ("hallway", "team", "battle", "result"))
            lines.append(f"[ИТОГ] Среднее время комнаты ({n} зам.): {fmt_s(avg_total)}")
            lines.append(f"[ИТОГ] Средние этапы: {stage_text}")

            by_type = {}
            for r in recs:
                by_type.setdefault(r["room_type"], []).append(r["total"])
            type_text = " | ".join(
                f"{t} {fmt_s(sum(v) / len(v))} ({len(v)})" for t, v in sorted(by_type.items())
            )
            lines.append(f"[ИТОГ] По стихиям: {type_text}")

            lines.append("[ИТОГ] Самые долгие комнаты:")
            for r in sorted(recs, key=lambda r: r["total"], reverse=True)[:3]:
                worst = max(STAGES, key=lambda s: r["stages"][s])
                lines.append(
                    f"[ИТОГ]   Комната {r['room_no']} ({r['room_type']}): {fmt_s(r['total'])} "
                    f"(дольше всего — {STAGE_NAMES[worst]} {fmt_s(r['stages'][worst])})"
                )
        else:
            lines.append("[ИТОГ] Замеров комнат нет — не пройдено ни одной комнаты.")

        waits = []
        for key in EXTRA_NAMES:
            total = sum(r["stages"].get(key, 0.0) for r in recs)
            if round(total, 1) > 0:
                waits.append(f"{EXTRA_NAMES[key]} {fmt_s(total)}")
        if waits:
            lines.append("[ИТОГ] Отдельно (в комнаты не входит): " + " | ".join(waits))

        counts_text = " | ".join(f"{name} {self.totals.get(key, 0)}" for key, name in COUNT_NAMES.items())
        lines.append(f"[ИТОГ] {counts_text}")

        if self.tap_delays:
            delays = self.tap_delays
            lines.append(
                f"[ИТОГ] Нажатия adb tap: {len(delays)} шт. | "
                f"задержка среднее {sum(delays) / len(delays):.2f} с, максимум {max(delays):.2f} с"
            )
        else:
            lines.append("[ИТОГ] Нажатия adb tap: замеров нет")
        lines.append("[ИТОГ] ==================================")
        return lines

    def print_summary(self, rooms, titanite):
        """Печатает итог один раз, сколько бы раз ни вызвали."""
        if self._summary_printed:
            return
        self._summary_printed = True
        for line in self.summary_lines(rooms, titanite):
            print(line)


# ---------------------------------------------------------------------------
# Включение: время в print, файл лога, ошибки
# ---------------------------------------------------------------------------
SESSION = SessionLog()


def install(base_dir=BOT_DATA_DIR):
    """Заменяет print: время в начале строк, копия в файл. Перехватывает необработанные ошибки.
    Вызывать один раз, в самом начале main.py (до остальных импортов, чтобы их строки тоже попали в лог)."""
    original_print = builtins.print
    logs_dir = os.path.join(base_dir, LOGS_SUBDIR)
    started = datetime.now()
    SESSION.started_at = started
    SESSION.directory = logs_dir

    log_file = None
    log_error = None
    try:
        log_file = LogFile(logs_dir, started)
    except OSError as e:
        log_error = e

    stamper = Stamper()
    lock = threading.Lock()

    def stamped_print(*args, **kwargs):
        # print в другой поток вывода (stderr, файл) не трогаем
        if kwargs.get("file") not in (None, sys.stdout):
            return original_print(*args, **kwargs)
        sep = kwargs.get("sep")
        end = kwargs.get("end")
        sep = " " if sep is None else sep
        end = "\n" if end is None else end
        text = sep.join(str(a) for a in args) + end
        with lock:
            stamped = stamper.process(text, datetime.now())
            if log_file:
                try:
                    log_file.write(stamped)
                except OSError:
                    pass
            original_print(stamped, end="", flush=True)

    builtins.print = stamped_print

    def excepthook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            return sys.__excepthook__(exc_type, exc, tb)
        SESSION.set_stop_reason(f"Ошибка: {exc_type.__name__}: {exc}", force=True)
        print("[ОШИБКА] Бот остановился из-за ошибки:")
        print("".join(traceback.format_exception(exc_type, exc, tb)).rstrip())

    sys.excepthook = excepthook

    if log_file:
        print(f"[ЛОГ] Лог сессии сохраняется в: {log_file.path}")
    else:
        print(f"[ЛОГ] Не удалось создать файл лога в '{logs_dir}': {log_error}. Лог пойдёт только в окно программы.")
    return log_file


# --- короткие вызовы для других модулей (vision.py, navigation.py) ---
def count(name):
    SESSION.count(name)


def track_tap(proc, started=None):
    return SESSION.track_tap(proc, started)


def excluded(name):
    return SESSION.timer.excluded(name)
