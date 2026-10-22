"""Две строки событий мини-бара (задача 15, шаг 4; ваш ответ 22.10.2026 — «короткие события»).

В макете «Бой выигран · ХП Сигурда 85%» — таких строк бот не пишет. Поэтому окно само собирает короткие события
из строк, которые бот уже печатает (бот ради мини-бара не меняется), и показывает их на языке окна:
- комната пройдена ([СТАТИСТИКА] Комнат: N) — номер, время комнаты ([ВРЕМЯ] ... всего N с) и меньше всего ХП после боя
  (строки « ---> ТИТАН: ХП N%» окна результата); метка — стихия комнаты ([КОМБАТ] Успешный вход. Комната: WATER);
- этаж пройден ([СТАТИСТИКА] Этажей: N), откат боя, причина SOS ([SOS] Причина: ...), бот решил сам (ответа нет),
  лимит сессии, пауза отладки, бот ждёт в коридоре на мягкой паузе;
- окно игры не активно ([ВНИМАНИЕ] Окно игры перекрыто — бот ждёт) и снова активно;
- ошибки — текст бота как есть (по-русски, как в журнале).
Пауза и «пауза снята», «бот запущен» — события самого окна (add).
Модуль без Tk: проверяется тестами (tests/test_ui_hud.py).
"""
import re
import time
from collections import deque

from i18n import get_text
from ui import log_lines, theme

KEEP = 2   # верхняя строка — последнее событие, нижняя — предыдущее

# Вид события → (ключ метки в i18n.py, цвет метки). У комнаты метка — название стихии и её цвет
BADGES = {
    "floor": ("hud_badge_floor", "blue_text"),
    "rollback": ("hud_badge_rollback", "warning"),
    "sos": ("hud_badge_sos", "danger_text"),
    "pause": ("hud_badge_pause", "warning"),
    "bot": ("hud_badge_bot", "success"),
    "limit": ("hud_badge_limit", "blue_text"),
    "focus": ("hud_badge_focus", "warning"),
    "error": ("hud_badge_error", "danger_text"),
}
# Событие → вид метки и ключ текста
EVENTS = {
    "started": ("bot", "hud_ev_started"),
    "floor": ("floor", "hud_ev_floor"),
    "rollback": ("rollback", "hud_ev_rollback"),
    "sos": ("sos", None),
    "pause": ("pause", "hud_ev_pause"),
    "waiting": ("pause", "hud_ev_waiting"),
    "resume": ("bot", "hud_ev_resume"),
    "debug": ("pause", "hud_ev_debug"),
    "auto": ("bot", "hud_ev_auto"),
    "limit": ("limit", "hud_ev_limit"),
    "focus_lost": ("focus", "hud_ev_focus_lost"),
    "focus_back": ("bot", "hud_ev_focus_back"),
    "error": ("error", None),
    "python_error": ("error", "hud_ev_python_error"),
}

_ENTER = re.compile(r"\[КОМБАТ\] Успешный вход\. Комната: (\w+)")
_HP = re.compile(r"--->\s*([A-Z_]+):\s*(?:ХП\s*(\d+)%|\[МЕРТВ\])")
_ROOMS = re.compile(r"\[СТАТИСТИКА\] Комнат: (\d+) \| Титанит: \d+")
_ROOM_TIME = re.compile(r"\[ВРЕМЯ\] Комната (\d+) .*?всего (\d+(?:\.\d+)?) с")
_FLOORS = re.compile(r"\[СТАТИСТИКА\] Этажей: (\d+)")
_SOS = re.compile(r"\[SOS\] Причина: (.+)")
_AUTO = re.compile(r"\[ТАКТИКА\] Ответа нет (\d+) мин")
_ROLLBACK = "[ОТКАТ] Запускаю протокол отката боя"
_LIMIT = "[ЛИМИТ]"
_WAITING = "[МЯГКАЯ ПАУЗА] Бот ждет в коридоре"
_DEBUG = "[ПАУЗА ОТЛАДКИ]"
_FOCUS_LOST = "Окно игры перекрыто"
_FOCUS_BACK = "[ИНФО] Окно снова активно"


class Event:
    __slots__ = ("kind", "time", "data")

    def __init__(self, kind, at, **data):
        self.kind, self.time, self.data = kind, at, data

    def __repr__(self):
        return f"Event({self.kind!r}, {self.time!r}, {self.data!r})"


def line_time(line):
    """«10:42:31» из «10:42:31.457 [ТЕГ] ...» (время ставит бот) или None."""
    match = log_lines._TIME.match(line)
    return match.group(0).split(".")[0] if match else None


class HudFeed:
    def __init__(self, clock=lambda: time.strftime("%H:%M:%S")):
        self.clock = clock
        self.events = deque(maxlen=KEEP)
        self.reset()

    def reset(self):
        self.events.clear()
        self.door = None
        self.hp = {}
        self.version = 0          # растёт при каждом изменении: мини-бар перерисовывает строки, только если оно сменилось

    def latest(self):
        """События, новое первым (не больше двух)."""
        return list(reversed(self.events))

    def add(self, kind, at=None, **data):
        self.events.append(Event(kind, at or self.clock(), **data))
        self.version += 1

    def feed(self, line):
        """Строка бота (как в журнале). Событие появляется, только если строка о нём."""
        at = line_time(line) or self.clock()
        match = _ENTER.search(line)
        if match:
            self.door, self.hp = match.group(1).lower(), {}
            return
        match = _HP.search(line)
        if match:
            self.hp[match.group(1).lower()] = int(match.group(2) or 0)
            return
        match = _ROOMS.search(line)
        if match:
            low = min(self.hp.items(), key=lambda item: item[1]) if self.hp else None
            self.add("room", at, n=int(match.group(1)), door=self.door, low=low, seconds=None)
            return
        match = _ROOM_TIME.search(line)
        if match:
            # [ВРЕМЯ] приходит после [СТАТИСТИКА]: дописываем время в событие той же комнаты
            room = next((e for e in self.events if e.kind == "room" and e.data["n"] == int(match.group(1))), None)
            if room is not None:
                room.data["seconds"] = round(float(match.group(2)))
                self.version += 1
            return
        match = _FLOORS.search(line)
        if match:
            self.add("floor", at, n=int(match.group(1)))
            return
        match = _SOS.search(line)
        if match:
            self.add("sos", at, reason=match.group(1).strip())
            return
        match = _AUTO.search(line)
        if match:
            self.add("auto", at, m=int(match.group(1)))
            return
        if _ROLLBACK in line:
            self.add("rollback", at)
        elif _LIMIT in line:
            self.add("limit", at)
        elif _WAITING in line:
            self.add("waiting", at)
        elif _DEBUG in line:
            self.add("debug", at)
        elif _FOCUS_LOST in line:
            self.add("focus_lost", at)
        elif _FOCUS_BACK in line:
            self.add("focus_back", at)
        else:
            self._error(line, at)

    def _error(self, line, at):
        time_end, span, tag = log_lines.split(line)
        if tag:
            if log_lines.category_of_tag(tag) == log_lines.ERRORS and tag.upper() not in ("SOS", "SOS_CLOSE"):
                text = line[span[1]:].strip()
                if text:
                    self.add("error", at, text=text)
        elif line[time_end:].lstrip().startswith("Traceback"):
            self.add("python_error", at)


def titan_name(lang, titan):
    name = get_text(lang, f"titan_{titan}")
    return titan.capitalize() if name == f"titan_{titan}" else name


def badge(event, lang):
    """(текст метки, цвет текста, цвет фона метки) — фон: 16% цвета на фоне мини-бара."""
    if event.kind == "room":
        door = event.data.get("door")
        style = theme.element_style(door)
        name = theme.plain_text(get_text(lang, f"elem_{door}")) if door else ""
        if not door or name == f"elem_{door}":
            name = get_text(lang, "hud_badge_room")
        color = style["text"]
    else:
        key, color_key = BADGES[EVENTS[event.kind][0]]
        name, color = get_text(lang, key), theme.COLORS[color_key]
    return name, color, theme.blend(color, theme.COLORS["bg_surface"], 0.16)


def text(event, lang):
    """Текст события на языке окна."""
    g = lambda key: get_text(lang, key)  # noqa: E731
    data = event.data
    if event.kind == "room":
        parts = [g("hud_ev_room").format(n=data["n"])]
        if data.get("seconds") is not None:
            parts.append(g("hud_ev_room_time").format(s=data["seconds"]))
        if data.get("low"):
            titan, hp = data["low"]
            parts.append(g("hud_ev_low_hp").format(titan=titan_name(lang, titan), hp=hp))
        return " · ".join(parts)
    if event.kind == "sos":
        import telegram_report
        return telegram_report.humanize(data["reason"], lang)
    if event.kind == "error":
        return data["text"]
    return g(EVENTS[event.kind][1]).format(**data)
