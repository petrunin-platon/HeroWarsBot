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

С проверки шага 4 (ваш ответ 22.10.2026: панель выше, 4 строки) ещё:
- что бот делает сейчас (phase) и сколько секунд — коридор, выбор двери, сборка пака, бой, окно результата, откат,
  точка сохранения, пауза, ждёт вашего решения, ждёт окно игры, ждёт связь; видно, если бот вдруг стоит;
- ХП пака после последнего боя (team) — из строк окна результата « ---> ТИТАН: ХП N%»;
- сколько осталось до цели по скорости этой сессии (eta_seconds).
Модуль без Tk: проверяется тестами (tests/test_ui_hud.py).
"""
import re
import time
from collections import deque

from i18n import get_text
from ui import log_lines, theme

KEEP = 4   # верхняя строка — последнее событие, ниже — предыдущие

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
_ABSENT = re.compile(r"--->\s*([A-Z_]+):\s*\[ОТСУТСТВУЕТ\]")

# Что бот делает сейчас: строка бота → этап (ключ надписи hud_now_<этап>). Первое совпадение
PHASES = (
    ("[НАВИГАЦИЯ] Сканирую коридор", "corridor"),
    ("[НАВИГАЦИЯ] Этаж пройден! Активируем точку сохранения", "checkpoint"),
    ("[УСПЕХ] Окно выбора комнат открылось", "doors"),
    ("[КОМБАТ] Успешный вход", "team"),
    ("[ТАКТИКА] Выполняю быстрый старт боя", "battle"),
    ("[АНГУС] Ожидаю загрузки боя", "battle"),
    ("[АНАЛИЗАТОР] Окно результата", "result"),
    ("[ОТКАТ] Запускаю протокол отката", "rollback"),
    ("[УМНЫЙ СТАРТ] Сканирую экран", "smart"),
    ("[МЯГКАЯ ПАУЗА] Бот ждет в коридоре", "paused"),
    ("[SOS] Причина", "sos"),
    ("[ЛОГИКА] Ожидание команды от GUI", "sos"),
    ("[ТАКТИКА] Ручной режим", "manual"),
    ("Похоже, нет связи", "network"),
)
ROOM_PHASES = {"team", "battle", "result", "rollback"}   # к этим этапам дописывается стихия комнаты


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
    def __init__(self, clock=lambda: time.strftime("%H:%M:%S"), monotonic=time.monotonic):
        self.clock = clock
        self.monotonic = monotonic
        self.events = deque(maxlen=KEEP)
        self.reset()

    def reset(self):
        self.events.clear()
        self.door = None
        self.hp = {}
        self.team = []            # ХП пака после последнего боя: [(титан, ХП или None — иконка не нашлась)]
        self.phase = None         # что бот делает сейчас (ключ PHASES)
        self.phase_door = None
        self.phase_since = None
        self._before_focus = None
        self.version = 0          # растёт при каждом изменении: мини-бар перерисовывает строки, только если оно сменилось

    def set_phase(self, phase):
        if phase == "focus" and self.phase != "focus":
            self._before_focus = (self.phase, self.phase_door, self.phase_since)
        self.phase, self.phase_door, self.phase_since = phase, self.door, self.monotonic()

    def phase_seconds(self):
        return 0 if self.phase_since is None else max(0, int(self.monotonic() - self.phase_since))

    def _track_phase(self, line):
        if _FOCUS_LOST in line:
            self.set_phase("focus")
        elif _FOCUS_BACK in line and self._before_focus:
            self.phase, self.phase_door, self.phase_since = self._before_focus   # бот вернулся к тому, что делал
            self._before_focus = None
        else:
            for marker, phase in PHASES:
                if marker in line:
                    if phase == "team":
                        match = _ENTER.search(line)
                        self.door = match.group(1).lower() if match else self.door
                    self.set_phase(phase)
                    return

    def latest(self):
        """События, новое первым (не больше двух)."""
        return list(reversed(self.events))

    def add(self, kind, at=None, **data):
        self.events.append(Event(kind, at or self.clock(), **data))
        self.version += 1

    def feed(self, line):
        """Строка бота (как в журнале). Событие появляется, только если строка о нём."""
        at = line_time(line) or self.clock()
        self._track_phase(line)
        match = _ENTER.search(line)
        if match:
            self.door, self.hp = match.group(1).lower(), {}
            return
        match = _HP.search(line)
        if match:
            self._team_hp(match.group(1), int(match.group(2) or 0))
            return
        match = _ABSENT.search(line)
        if match:
            self._team_hp(match.group(1), None)   # иконка не нашлась
            return
        match = _ROOMS.search(line)
        if match:
            known = [(titan, hp) for titan, hp in self.hp.items() if hp is not None]
            low = min(known, key=lambda item: item[1]) if known else None
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

    def _team_hp(self, titan, hp):
        """ХП пака — из строк окна результата этой комнаты (в том порядке, как их печатает бот)."""
        self.hp[titan.lower()] = hp
        self.team = list(self.hp.items())
        self.version += 1

    def _error(self, line, at):
        time_end, span, tag = log_lines.split(line)
        if tag:
            if log_lines.category_of_tag(tag) == log_lines.ERRORS and tag.upper() not in ("SOS", "SOS_CLOSE"):
                text = line[span[1]:].strip()
                if text:
                    self.add("error", at, text=text)
        elif line[time_end:].lstrip().startswith("Traceback"):
            self.add("python_error", at)


def eta_seconds(goal, progress, elapsed_s):
    """Сколько секунд до цели по скорости этой сессии; None — посчитать нельзя (нет цели, ещё ничего не сделано)."""
    if not goal or not progress:
        return None
    done, target, _share = progress
    if done >= target:
        return 0
    if goal[0] == "time":
        return max(0, target * 60 - elapsed_s)
    if done <= 0 or elapsed_s < 1:
        return None
    return (target - done) * elapsed_s / done


def duration_text(seconds, lang):
    """«1 ч 10 мин», «25 мин», «меньше минуты»."""
    minutes = int(seconds // 60)
    if minutes < 1:
        return get_text(lang, "hud_less_minute")
    if minutes < 60:
        return get_text(lang, "hud_minutes").format(m=minutes)
    return get_text(lang, "hud_hours").format(h=minutes // 60, m=minutes % 60)


def phase_text(feed, lang):
    """«Бой · Огонь · 12 с» — что бот делает сейчас и сколько секунд."""
    if feed.phase is None:
        return ""
    parts = [get_text(lang, f"hud_now_{feed.phase}")]
    if feed.phase in ROOM_PHASES and feed.phase_door:
        name = theme.plain_text(get_text(lang, f"elem_{feed.phase_door}"))
        if name != f"elem_{feed.phase_door}":
            parts.append(name)
    parts.append(get_text(lang, "hud_seconds").format(s=feed.phase_seconds()))
    return " · ".join(parts)


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
