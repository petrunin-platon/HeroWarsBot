"""Строки журнала нового окна (задача 15, шаг 3): к какой «таблетке» относится строка и что окно узнаёт из неё о сессии.

Раскладка — docs/ui_inventory.md, 1.2 (решено): строки бота показываем как есть, тег красим цветом его таблетки
(ui/theme.py: LOG_CATEGORY_COLORS). Строка без тега (« ---> ARAJI: ХП…», продолжение ошибки Python) идёт туда же,
куда строка над ней. Новый неизвестный тег — в «Систему».
Цифры сессии (комнаты, титанит, этажи, дверь, откаты, SOS, время комнат, итог) — только из строк, которые бот уже
печатает: бот ради окна не меняется.
Модуль без Tk: проверяется тестами (tests/test_ui_main.py).
"""
import re
import time

ALL, FIGHTS, RULES, SYSTEM, ERRORS = "all", "fights", "rules", "system", "errors"
FILTERS = (ALL, FIGHTS, RULES, SYSTEM, ERRORS)
GUI = "gui"  # цвет строк самого окна ([GUI]); таблетка у них — «Система»

# Бои: ход прохождения
FIGHT_TAGS = {"КОМБАТ", "СТАТИСТИКА", "ВРЕМЯ", "СОСТОЯНИЕ", "АНАЛИЗАТОР", "ОТКАТ", "АНГУС", "ЛИМИТ", "МЯГКАЯ ПАУЗА",
              "ИТОГ"}
# Правила: решения бота. [SOS_CLOSE] — бот решил сам, пока вы не ответили на окно SOS
RULE_TAGS = {"ТАКТИКА", "ОБУЧЕНИЕ", "SKIP", "СКИП", "ПРАВИЛА", "КОМАНДА", "ПРОВЕРКА", "SOS_CLOSE"}
# Ошибки (и всё, что начинается с «ОШИБКА» или «ФАТАЛЬНАЯ ОШИБКА»: [ОШИБКА ФОКУСА], [ФАТАЛЬНАЯ ОШИБКА КОМАНДЫ] ...)
ERROR_TAGS = {"ERROR", "ВНИМАНИЕ", "ПРЕДУПРЕЖДЕНИЕ", "СТОРОЖ", "SOS", "АЛЕРТ"}
ERROR_PREFIXES = ("ОШИБКА", "ФАТАЛЬНАЯ ОШИБКА")

_TIME = re.compile(r"\d{1,2}:\d{2}:\d{2}(?:\.\d{1,3})?(?=\s)")
_TAG = re.compile(r"\s*\[([^\[\]\n]{1,40})\]")
_PY_ERROR = re.compile(r"\s*(Traceback \(most recent call last\)|[A-Za-z_][\w.]*(Error|Exception)\b)")


def split(line):
    """Части строки для раскраски: (конец времени или 0, (начало, конец) тега или None, тег или None).
    Время — «14:03:21.457 » в начале строки (его ставит бот), тег — первый [...] сразу после него."""
    match = _TIME.match(line)
    time_end = match.end() if match else 0
    tag = _TAG.match(line, time_end)
    if not tag:
        return time_end, None, None
    return time_end, (tag.start(1) - 1, tag.end()), tag.group(1).strip()


def category_of_tag(tag):
    """Таблетка тега: FIGHTS, RULES, SYSTEM или ERRORS."""
    upper = tag.upper()
    if upper in ERROR_TAGS or upper.startswith(ERROR_PREFIXES):
        return ERRORS
    if upper in FIGHT_TAGS:
        return FIGHTS
    if upper in RULE_TAGS:
        return RULES
    return SYSTEM


class Classifier:
    """Раскладывает строки по таблеткам. Помнит таблетку прошлой строки: строка без тега идёт туда же."""

    def __init__(self):
        self.last = SYSTEM

    def classify(self, line):
        """(таблетка, цвет тега, части для раскраски, новая ли это ошибка для счётчика «Ошибки (N)»)."""
        time_end, span, tag = split(line)
        if tag:
            category = category_of_tag(tag)
            color = GUI if tag.upper() == "GUI" else category
            counted = category == ERRORS
        elif _PY_ERROR.match(line, time_end):
            category = color = ERRORS
            counted = line[time_end:].lstrip().startswith("Traceback")  # ошибка Python — одна на весь её текст
        else:
            category, color, counted = self.last, self.last, False
        self.last = category
        return category, color, (time_end, span), counted


# ---------------------------------------------------------------------------
# Цифры сессии
# ---------------------------------------------------------------------------
_ROOMS = re.compile(r"\[СТАТИСТИКА\] Комнат: (\d+) \| Титанит: (\d+)")
_FLOORS = re.compile(r"\[СТАТИСТИКА\] Этажей: (\d+)")
_DOOR = re.compile(r"\[КОМБАТ\] Успешный вход\. Комната: (\w+)")
_ROLLBACK = "[ОТКАТ] Запускаю протокол отката боя"
_SOS = "[SOS] Причина:"
_ROOM_TIME = re.compile(r"\[ВРЕМЯ\] Комната \d+ .*?всего (\d+(?:\.\d+)?) с")
_SUMMARY = "[ИТОГ]"
_STOP_REASON = re.compile(r"\[ИТОГ\] Причина остановки: (.+)")
_SUMMARY_ROOMS = re.compile(r"\[ИТОГ\] Длительность: .*\| Комнат: (\d+) \| Титанит: (\d+)")
_SUMMARY_SOS = re.compile(r"окна SOS (\d+)")
_SUMMARY_ROLLBACKS = re.compile(r"откаты (\d+)")

# Почему бот остановился, если он не успел написать [ИТОГ] (окно остановило процесс): ключи i18n.py
ENDED_KILLED = "main_reason_killed"
ENDED_SCRCPY = "main_reason_scrcpy"
ENDED_EXIT = "main_reason_exit"


class SessionStats:
    """Сессия бота глазами окна: что бот напечатал с запуска. Время считает само окно (от запуска бота)."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.started = None
        self.reset()

    def reset(self):
        self.rooms = self.titanite = self.floors = self.rollbacks = self.sos = 0
        self.door = None
        self.room_times = []
        self.summary = []          # строки [ИТОГ] (кнопка «Подробно»)
        self.stop_reason = None    # из [ИТОГ] — текст бота по-русски
        self.ended_by = None       # ENDED_*: бот не написал причину сам
        self.ended = None

    def start(self):
        self.reset()
        self.started = self.clock()

    def finish(self, ended_by=ENDED_EXIT):
        """Процесс бота закончился. ended_by — почему, если бот не написал [ИТОГ] (его остановило окно)."""
        if self.started is None or self.ended is not None:
            return
        self.ended = self.clock()
        if not self.stop_reason:
            self.ended_by = ended_by

    @property
    def running(self):
        return self.started is not None and self.ended is None

    @property
    def battles(self):
        """Бои: каждая засчитанная комната — победа, каждый откат — бой, который переиграли."""
        return self.rooms + self.rollbacks

    def elapsed(self):
        if self.started is None:
            return 0.0
        return max(0.0, (self.ended if self.ended is not None else self.clock()) - self.started)

    def avg_room(self):
        """Среднее «всего» из строк [ВРЕМЯ] (секунды) или None, если комнат ещё не было."""
        return sum(self.room_times) / len(self.room_times) if self.room_times else None

    def feed(self, line):
        if _SUMMARY in line:
            self._feed_summary(line)
            return
        match = _ROOMS.search(line)
        if match:
            self.rooms, self.titanite = int(match.group(1)), int(match.group(2))
            return
        match = _FLOORS.search(line)
        if match:
            self.floors = int(match.group(1))
            return
        match = _DOOR.search(line)
        if match:
            self.door = match.group(1).lower()
            return
        match = _ROOM_TIME.search(line)
        if match:
            self.room_times.append(float(match.group(1)))
            return
        if _ROLLBACK in line:
            self.rollbacks += 1
        elif _SOS in line:
            self.sos += 1

    def _feed_summary(self, line):
        self.summary.append(line.rstrip("\n"))
        match = _STOP_REASON.search(line)
        if match:
            self.stop_reason = match.group(1).strip()
            return
        match = _SUMMARY_ROOMS.search(line)
        if match:
            self.rooms, self.titanite = int(match.group(1)), int(match.group(2))
            return
        sos, rollbacks = _SUMMARY_SOS.search(line), _SUMMARY_ROLLBACKS.search(line)
        if sos and rollbacks:  # строка счётчиков: «... | окна SOS 0 | откаты 1 | ...» — точные числа бота
            self.sos, self.rollbacks = int(sos.group(1)), int(rollbacks.group(1))


def clock_text(seconds):
    """00:42:17"""
    total = int(seconds)
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def group_digits(number):
    """2838 → «2 838» (как в макете)."""
    return f"{int(number):,}".replace(",", " ")
