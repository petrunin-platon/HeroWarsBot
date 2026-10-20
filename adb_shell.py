# adb_shell.py
# Одно постоянное соединение с телефоном (adb shell) для нажатий и свайпов (задача 11).
# Раньше на каждое нажатие запускался новый процесс adb: в среднем 0,42 с (замер сессии 05).
# Теперь adb запускается один раз, а команды «input tap ...» идут в уже открытое соединение.
# После каждой команды телефон печатает метку — по ней бот знает, что нажатие дошло (click_logic.TapWatch).
# Если соединение оборвалось (телефон отключили, adb перезапустился), бот переподключается сам,
# а пока соединения нет, нажимает по-старому — новым процессом adb.
# Без OpenCV и игры: проверяется тестами на поддельном adb (tests/test_adb_shell.py).
import itertools
import os
import subprocess
import threading
import time

NO_WINDOW = {"creationflags": 0x08000000} if os.name == "nt" else {}  # в Windows не открывать окно консоли
MARK = "__HWB_DONE__"        # метка после каждой команды
COMMAND_TIMEOUT_S = 5.0      # команда не выполнилась за это время — соединение считаем зависшим
RECONNECT_PAUSE_S = 5.0      # переподключаться не чаще, чем раз в столько секунд
SHELL_COMMAND = ["adb", "shell", "sh"]


class ShellCommand:
    """Команда, отправленная в постоянное соединение. Для TapWatch и замеров ведёт себя как процесс Popen:
    poll() — None, пока телефон не ответил меткой; потом 0 (выполнена) или 1 (соединение оборвалось)."""

    def __init__(self, sent_at):
        self.sent_at = sent_at
        self.done_at = None
        self.returncode = None
        self._done = threading.Event()

    def finish(self, code, at):
        if self.returncode is None:
            self.returncode = code
            self.done_at = at
            self._done.set()

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self._done.wait(timeout)
        return self.returncode


class AdbShell:
    """Постоянное соединение `adb shell`. run("input tap 100 200") — отправить команду.

    popen, clock и log подменяются в тестах."""

    def __init__(self, command=None, popen=subprocess.Popen, clock=time.monotonic, log=print):
        self._command = list(command or SHELL_COMMAND)
        self._popen = popen
        self._clock = clock
        self._log = log
        self._lock = threading.Lock()
        self._proc = None
        self._pending = {}
        self._ids = itertools.count(1)
        self._last_try = None
        self._ever_connected = False
        self.connects = 0      # сколько раз соединение открывалось (для замеров и тестов)

    # --- соединение ---
    def _alive(self):
        return self._proc is not None and self._proc.poll() is None

    def _connect(self):
        now = self._clock()
        if self._last_try is not None and now - self._last_try < RECONNECT_PAUSE_S:
            return False
        self._last_try = now
        try:
            proc = self._popen(self._command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, bufsize=0, **NO_WINDOW)
        except (OSError, ValueError) as e:
            self._log(f"[ADB] Не удалось открыть постоянное соединение с телефоном ({e}). Нажимаю по-старому.")
            return False
        self._proc = proc
        self.connects += 1
        threading.Thread(target=self._read_loop, args=(proc,), daemon=True).start()
        if self._ever_connected:
            self._log("[ADB] Постоянное соединение с телефоном снова открыто.")
        self._ever_connected = True
        return True

    def _broken(self, proc, why):
        """Соединение оборвалось: все ждущие команды считаются невыполненными, при следующей команде — переподключение."""
        if proc is not self._proc:
            return
        self._proc = None
        pending, self._pending = self._pending, {}
        now = self._clock()
        for cmd in pending.values():
            cmd.finish(1, now)
        try:
            proc.kill()
        except Exception:
            pass
        self._log(f"[ADB] Постоянное соединение с телефоном оборвалось ({why}). Переподключусь при следующем нажатии.")

    def _read_loop(self, proc):
        stream = proc.stdout
        while True:
            try:
                raw = stream.readline()
            except Exception:
                raw = b""
            if not raw:
                with self._lock:
                    self._broken(proc, "adb закрылся")
                return
            line = raw.decode("utf-8", "replace").strip()
            if line.startswith(MARK):
                try:
                    n = int(line[len(MARK):])
                except ValueError:
                    continue
                with self._lock:
                    cmd = self._pending.pop(n, None)
                if cmd is not None:
                    cmd.finish(0, self._clock())
            elif line:
                self._log(f"[ADB] Телефон ответил: {line}")

    def _check_stuck(self):
        """Команда висит дольше COMMAND_TIMEOUT_S — соединение зависло, закрываем его."""
        now = self._clock()
        if any(now - cmd.sent_at > COMMAND_TIMEOUT_S for cmd in self._pending.values()):
            self._broken(self._proc, f"телефон не ответил за {COMMAND_TIMEOUT_S:.0f} с")

    # --- команды ---
    def run(self, line):
        """Отправить команду в постоянное соединение. Возвращает ShellCommand или None, если соединения нет
        (тогда вызывающий выполняет команду по-старому, новым процессом adb)."""
        with self._lock:
            if self._proc is not None:
                self._check_stuck()
            if not self._alive():
                if self._proc is not None:
                    self._broken(self._proc, "adb закрылся")
                if not self._connect():
                    return None
            n = next(self._ids)
            cmd = ShellCommand(self._clock())
            self._pending[n] = cmd
            proc = self._proc
            try:
                proc.stdin.write(f"{line}; echo {MARK}{n}\n".encode("utf-8"))
                proc.stdin.flush()
            except (OSError, ValueError) as e:
                self._pending.pop(n, None)
                self._broken(proc, f"не удалось отправить команду: {e}")
                return None
        return cmd

    def ping(self, timeout=COMMAND_TIMEOUT_S):
        """Сколько секунд идёт пустая команда туда и обратно (связь с телефоном без «input»). None — не ответил."""
        cmd = self.run("true")
        if cmd is None or cmd.wait(timeout) != 0:
            return None
        return cmd.done_at - cmd.sent_at

    def close(self):
        with self._lock:
            proc, self._proc = self._proc, None
        if proc is not None:
            try:
                proc.stdin.close()
                proc.kill()
            except Exception:
                pass


def spawn_seconds(command=("adb", "shell", "true"), runs=3, popen=subprocess.Popen, clock=time.monotonic):
    """Сколько секунд идёт пустая команда, если на неё запускать новый процесс adb (как раньше на каждое нажатие).
    Возвращает список замеров (пустой, если adb не запускается)."""
    result = []
    for _ in range(runs):
        started = clock()
        try:
            proc = popen(list(command), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **NO_WINDOW)
            if proc.wait(timeout=COMMAND_TIMEOUT_S) != 0:
                continue
        except Exception:
            continue
        result.append(clock() - started)
    return result
