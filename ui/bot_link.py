"""Связь нового окна с ботом (задача 15, шаг 3): запуск, строки бота, окна SOS, ответы боту, пауза и остановка.

Перенос из старой главной (ui/dashboard.py: start_bot, monitor_bot_output, _send_answer, toggle_pause, stop_bot)
без изменений протокола (CLAUDE.md, «Связь GUI и бота»; docs/ui_inventory.md, раздел 0):
- бот запускается той же командой: python -X utf8 -u main.py (в собранном .exe — <exe> --bot-mode), язык — HEROWARS_LANG;
  перед запуском окно игры встаёт в размер 1606×748;
- бот → окно: строки [SOS_TRIGGER] (окна SOS), [SOS_CLOSE] (бот решил сам), [ПАУЗА ОТЛАДКИ] — метки ищутся через in,
  время в начале строки допустимо; строки [SOS_TRIGGER] в журнал не идут, как раньше;
- окно → бот: одна строка в stdin (IGNORE, MANUAL, STOP, ROLLBACK:..., ROLLBACK_TG:..., CONFIRM, NEW_PACK:..., пустая
  строка после паузы отладки); ответ из окна, которое устарело (бот уже решил сам, [SOS_CLOSE]), не отправляется;
- мягкая пауза — файл pause.flag.

Отличия от старого окна (ошибки, которые чинит шаг 3):
- калибровка окна игры и запуск — в фоновом потоке: старое окно замирало на них на 1–2 с;
- строки бота читаются до конца, а не пока процесс жив: последние строки ([ИТОГ]) больше не теряются;
- «Остановить бота» в окнах SOS шлёт STOP (ваш ответ 22.10.2026): бот сам пишет итог и шлёт его в Telegram.
  Не отозвался за STOP_GRACE_S — окно останавливает процесс само. Кнопка «СТОП» (F10) по-прежнему мгновенная.

Строки и события фоновый поток кладёт в очередь окна (events), окно разбирает её раз в 100 мс:
("bot_line", строка), ("bot_event", (вид, данные, когда)), ("bot_exit", номер запуска), ("log", строка самого окна).
epoch (номер «поколения» окон SOS) меняет только главный поток, когда разбирает [SOS_CLOSE] из очереди: так окно SOS,
открытое по строке из той же очереди, получает правильный номер.
Модуль без Tk: проверяется тестами на поддельном боте (tests/test_bot_link.py).
"""
import json
import os
import subprocess
import sys
import threading
import time

from config import GAME_WINDOW_TITLE, PAUSE_FLAG_FILE
from ui.log_lines import ENDED_KILLED

SOS, NO_TEAM, TEST_OK, SOS_CLOSE, DEBUG_PAUSE = "sos", "no_team", "test_ok", "sos_close", "debug_pause"
GAME_SIZE = (1606, 748)
CREATE_NO_WINDOW = 0x08000000   # бот без чёрного окна консоли (только Windows)
STOP_GRACE_S = 10               # столько ждём, что бот откликнется на STOP (начнёт писать итог)
STOP_FINISH_S = 180             # столько даём ему дописать итог и отправить его в Telegram (повторы при обрыве связи)
KILL_WAIT_S = 2                 # после terminate — столько ждём выхода, потом kill (как старое окно)


def parse_line(line):
    """Строка бота → (вид, данные) для окна или None. Разбор — как ui/dashboard.py:monitor_bot_output."""
    if "[SOS_TRIGGER]" in line:
        if "TEST_SUCCESS:" in line:
            try:
                data = json.loads(line.split("TEST_SUCCESS:", 1)[1].strip())
            except ValueError:
                data = {}
            if isinstance(data, dict) and "source" in data:
                return TEST_OK, {"titans": data.get("titans") or {}, "source": data["source"]}
            return TEST_OK, {"titans": data if isinstance(data, dict) else {}, "source": "gui"}
        try:
            data = json.loads(line.split("[SOS_TRIGGER]", 1)[1].strip())
        except ValueError:
            data = None
        if not isinstance(data, dict):
            return SOS, {"titans": {"Неизвестно": 0}, "is_manual": False}
        if data.get("type") == "NO_VALID_TEAM":
            return NO_TEAM, data
        if "titans" in data:
            return SOS, {"titans": data["titans"] or {}, "is_manual": bool(data.get("is_manual", False))}
        return SOS, {"titans": data, "is_manual": False}
    if "[SOS_CLOSE]" in line:
        return SOS_CLOSE, line.split("[SOS_CLOSE]", 1)[1].strip()
    if "[ПАУЗА ОТЛАДКИ]" in line:
        return DEBUG_PAUSE, None
    return None


def bot_command():
    """Команда запуска бота, как в старом окне: из исходников — python main.py, в собранном .exe — <exe> --bot-mode."""
    compiled = getattr(sys, "frozen", False) or getattr(sys, "compiled", False) or \
        (sys.platform == "win32" and not sys.executable.lower().endswith("python.exe"))
    if compiled:
        return [sys.executable, "--bot-mode"]
    return [sys.executable, "-X", "utf8", "-u", "main.py"]


def calibrate_game_window():
    from environment import calibrate_window
    return calibrate_window(GAME_WINDOW_TITLE, *GAME_SIZE)


class BotLink:
    def __init__(self, events, command=None, calibrate=calibrate_game_window, pause_file=PAUSE_FLAG_FILE,
                 clock=time.monotonic):
        self.events = events
        self.command = command          # None — bot_command(); тесты подставляют поддельного бота
        self.calibrate = calibrate
        self.pause_file = pause_file
        self.clock = clock
        self.process = None
        self.run_id = 0                 # номер запуска: событие «бот завершился» от прошлого запуска не путаем с новым
        self.starting = False
        self.stopping = False           # отправлен STOP, ждём, пока бот допишет итог
        self.debug_wait = False         # бот ждёт «Продолжить» после [ПАУЗА ОТЛАДКИ]
        self.epoch = 0
        self.ended_by = None            # почему процесс закончился, если его остановило окно (log_lines.ENDED_*)
        self._lock = threading.Lock()
        self._closed = False
        self._killed = set()            # запуски, которые остановило окно: их ошибку чтения не показываем
        self._exiting = False           # бот начал писать итог ([ИТОГ]) — он выходит сам
        self._stop_timer = None

    # ── Состояние ───────────────────────────────────────────────────────────
    def running(self):
        """Бот запущен (или запускается: идёт калибровка окна игры)."""
        if self.starting:
            return True
        proc = self.process
        return proc is not None and proc.poll() is None

    def paused(self):
        return os.path.exists(self.pause_file)

    def _post(self, kind, value=None):
        self.events.put((kind, value))

    def _log(self, text):
        self._post("log", text)

    # ── Запуск ──────────────────────────────────────────────────────────────
    def start(self, lang):
        """Запустить бота (в фоне: калибровка окна игры, потом процесс). False — бот уже запущен."""
        with self._lock:
            if self._closed or self.running():
                return False
            self.starting = True
            self.stopping = self.debug_wait = self._exiting = False
            self.ended_by = None
            self.run_id += 1
            run_id = self.run_id
        threading.Thread(target=self._start, args=(lang, run_id), name="bot-start", daemon=True).start()
        return True

    def _start(self, lang, run_id):
        self._log("[СИСТЕМА] Калибровка окна игры...\n")
        try:
            self.calibrate()
        except Exception as e:
            self._log(f"[ОШИБКА] Не удалось подогнать окно игры: {e}\n")
        env = os.environ.copy()
        env["HEROWARS_LANG"] = lang
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        with self._lock:
            if self._closed or run_id != self.run_id or not self.starting:
                self.starting = False   # пока шла калибровка, нажали «СТОП» или закрыли окно — бота не запускаем
                self._post("bot_exit", run_id)
                return
            try:
                self.process = subprocess.Popen(
                    self.command or bot_command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, bufsize=1, encoding="utf-8", errors="replace", env=env,
                    creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            except OSError as e:
                self.process = None
                self.starting = False
                self._log(f"[ОШИБКА] Не удалось запустить бота: {e}\n")
                self._post("bot_exit", run_id)
                return
            proc = self.process
            self.starting = False
        self._post("bot_started", run_id)
        self._read(proc, run_id)

    def _read(self, proc, run_id):
        """Строки бота — до конца вывода (и после выхода процесса: последние строки — итог сессии)."""
        try:
            for line in iter(proc.stdout.readline, ""):
                if "[ИТОГ]" in line:
                    self._exiting = True
                event = parse_line(line)
                if event:
                    self._post("bot_event", (event[0], event[1], self.clock()))
                    if event[0] in (SOS, NO_TEAM, TEST_OK):
                        continue  # строка [SOS_TRIGGER] — служебная, в журнал не идёт (как в старом окне)
                self._post("bot_line", line)
        except Exception as e:
            if run_id not in self._killed:
                self._log(f"\n[ОШИБКА КРИТИЧЕСКАЯ] Сбой чтения консоли бота: {e}\nПринудительная остановка процесса...\n")
                self.kill(log=False)
        finally:
            try:
                proc.wait(timeout=KILL_WAIT_S)
            except Exception:
                pass
            self._post("bot_exit", run_id)

    def exited(self, run_id):
        """Главный поток разобрал «бот завершился». True — это нынешний запуск (кнопки — в начальное состояние)."""
        if run_id != self.run_id or self.running():
            return False
        self._cancel_stop_timer()
        self.stopping = self.debug_wait = False
        return True

    # ── Ответы боту ─────────────────────────────────────────────────────────
    def write(self, command):
        """Одна строка в stdin бота. False — бот не запущен."""
        proc = self.process
        if proc is None or proc.poll() is not None:
            return False
        try:
            proc.stdin.write(command + "\n")
            proc.stdin.flush()
        except (OSError, ValueError) as e:
            self._log(f"[ОШИБКА] Не удалось отправить боту «{command}»: {e}\n")
            return False
        return True

    def answer(self, command, epoch):
        """Ответ на окно SOS. Окно устарело (бот уже решил сам) — не отправляем, как старое окно."""
        if epoch != self.epoch:
            self._log(f"[GUI] Ответ «{command}» не отправлен: бот уже решил сам.\n")
            return False
        return self.write(command)

    def sos_closed(self):
        """[SOS_CLOSE]: бот решил сам. Ответы из окон, открытых раньше, больше не отправляются. Только главный поток."""
        self.epoch += 1

    def continue_debug(self):
        """«Продолжить» после [ПАУЗА ОТЛАДКИ]: пустая строка, как кнопка «Продолжить фарм» старого окна."""
        self.debug_wait = False
        return self.write("")

    # ── Пауза ───────────────────────────────────────────────────────────────
    def toggle_pause(self):
        """Мягкая пауза (pause.flag), как в старом окне. Возвращает True, если теперь пауза."""
        if self.paused():
            try:
                os.remove(self.pause_file)
            except OSError:
                pass
            self._log("[GUI] Сигнал 'Снять паузу' отправлен боту.\n")
            return False
        with open(self.pause_file, "w") as f:
            f.write("1")
        self._log("[GUI] Сигнал 'Мягкая пауза' отправлен. Бот остановится перед следующей дверью.\n")
        return True

    # ── Остановка ───────────────────────────────────────────────────────────
    def request_stop(self, epoch, why=""):
        """«Остановить бота» в окне SOS: команда STOP — бот остановится сам, напишет [ИТОГ] и пришлёт итог в Telegram.
        Не отозвался за STOP_GRACE_S (или пишет итог дольше STOP_FINISH_S) — окно останавливает процесс само."""
        if not self.answer("STOP", epoch):
            return False
        self.stopping = True
        self._log(f"[GUI] Команда STOP отправлена боту{why}. Он остановится сам и пришлёт итог сессии в Telegram.\n")
        self._arm_stop_timer(self.run_id, self.clock())
        return True

    def _arm_stop_timer(self, run_id, since):
        self._cancel_stop_timer()
        self._stop_timer = threading.Timer(1.0, self._check_stop, args=(run_id, since))
        self._stop_timer.daemon = True
        self._stop_timer.start()

    def _check_stop(self, run_id, since):
        if run_id != self.run_id or not self.stopping or self.process is None or self.process.poll() is not None:
            return
        waited = self.clock() - since
        if (not self._exiting and waited >= STOP_GRACE_S) or waited >= STOP_FINISH_S:
            self._log(f"[GUI] Бот не остановился за {waited:.0f} с после STOP. Останавливаю процесс.\n")
            self.kill(log=False)
            return
        self._arm_stop_timer(run_id, since)

    def _cancel_stop_timer(self):
        if self._stop_timer:
            self._stop_timer.cancel()
            self._stop_timer = None

    def kill(self, log=True, ended_by=ENDED_KILLED):
        """Экстренный стоп (кнопка «СТОП», F10): процесс останавливается сразу, как в старом окне.
        Итог сессии в Telegram при этом не уходит. Возвращает True, если было что останавливать."""
        with self._lock:
            was_starting = self.starting
            self.starting = False          # бот ещё не запущен (идёт калибровка) — его и не запустят
            proc = self.process
            alive = proc is not None and proc.poll() is None
            if alive or was_starting:
                self._killed.add(self.run_id)
                self.ended_by = ended_by
        self._cancel_stop_timer()
        self.stopping = self.debug_wait = False
        if (alive or was_starting) and log:
            self._log("[GUI] ЭКСТРЕННЫЙ СТОП. Процесс убит.\n")  # раньше строки «Процесс бота завершен»
        if alive:
            cleanup_process(proc)
        if alive or was_starting:
            if self.paused():
                try:
                    os.remove(self.pause_file)
                except OSError:
                    pass
        return alive or was_starting

    def close(self):
        """Окно программы закрывается: бот останавливается, новый уже не запустится."""
        with self._lock:
            self._closed = True
        self.kill(log=False)


def cleanup_process(proc):
    """Безопасно завершить процесс (как ui/dashboard.py:_cleanup_process): terminate, закрыть каналы, ждать 2 с, потом kill."""
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    for stream in (proc.stdin, proc.stdout):
        if stream:
            try:
                stream.close()
            except Exception:
                pass
    try:
        proc.wait(timeout=KILL_WAIT_S)
    except subprocess.TimeoutExpired:
        proc.kill()
