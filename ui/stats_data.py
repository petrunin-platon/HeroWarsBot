"""«Статистика» нового окна (задача 15, шаг 6; макет design/mockups/05_stats): что показать — без Tk.

Цифры — из bot_data/stats.json (stats_manager: бот пишет их после каждой комнаты, по игровым дням со сдвигом reset_hour).
Периоды (ваш ответ 6.1 — как в макете): 7, 14, 30 дней и «Всё время». Столбиков не больше ~15 (ваше замечание:
«чтобы в окне не было 100500 полосок»): 7 и 14 дней — по дням, 30 дней — по неделям, «Всё время» — по дням,
пока данных не больше чем за 14 дней, по неделям — пока недель не больше 15, дальше по месяцам.
Неделя — с понедельника по воскресенье, у края периода — только его дни.
Дневной нормы и плитки «Создано правил» нет (ваши ответы 6.2: у бота норм нет; плитку правил — убрать).
Числа на графике — коротко: 850, 3.6K, 20K, 140K (ваше замечание: по 20 000 титанита в день на столбике недели).
Ручная корректировка — как в старой вкладке (ui/statistics_tab.py): нельзя меньше, чем бот собрал сам,
комнаты, этажи и зелье пересчитываются по титаниту (calc_rewards).
"""
from datetime import datetime, timedelta

PERIODS = ("7d", "14d", "30d", "all")
DEFAULT_PERIOD = "14d"
METRICS = ("titanite", "rooms", "floors", "potions")
MAX_DAY_BARS = 14     # «Всё время»: по дням, пока дней не больше
MAX_WEEK_BARS = 15    # по неделям, пока недель не больше; дальше — по месяцам
CORRECTION_DAYS = 7   # ручная корректировка: последние 7 дней (как старая вкладка) и день, выбранный на графике


def parse_day(text):
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def day_key(day):
    return day.strftime("%Y-%m-%d")


def compact(value):
    """Коротко для графика: 850, 3.6K, 20K, 140K, 1.2M."""
    value = int(round(value))
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value < 1000:
        return f"{sign}{value}"
    if value < 10_000:
        return f"{sign}{value / 1000:.1f}".rstrip("0").rstrip(".") + "K"
    if value < 1_000_000:
        return f"{sign}{round(value / 1000)}K"
    return f"{sign}{value / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"


def full(value):
    """Полностью, с пробелами между тысячами: 7 536, 31 400."""
    return f"{int(value):,}".replace(",", " ")


TILE_FULL_BELOW = 100_000   # в плитке до 100 000 — полностью, дальше сокращённо (ваше замечание: бывают и миллионы)


def tile_number(value):
    """Число в плитке: 98 540, 105.5K, 1.24M — помещается в плитку и при самом узком окне.
    Полное число плитка показывает в подсказке при наведении."""
    value = int(value)
    if abs(value) < TILE_FULL_BELOW:
        return full(value)
    if abs(value) < 1_000_000:
        return f"{value / 1000:.1f}".rstrip("0").rstrip(".") + "K"
    return f"{value / 1_000_000:.2f}".rstrip("0").rstrip(".") + "M"


def _day_values(daily, day):
    row = daily.get(day_key(day)) or {}
    return {m: int(row.get(m, 0) or 0) for m in METRICS}


def _bucket(kind, days, daily, today):
    values = [_day_values(daily, d) for d in days]
    bucket = {"kind": kind, "start": days[0], "end": days[-1], "days": list(days), "today": today in days,
              "per_day": [(d, v["titanite"]) for d, v in zip(days, values)]}
    for metric in METRICS:
        bucket[metric] = sum(v[metric] for v in values)
    return bucket


def _days(start, end):
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _weeks(start, end):
    """Недели с понедельника по воскресенье, обрезанные по краям периода."""
    groups, current = [], []
    for day in _days(start, end):
        if current and day.weekday() == 0:
            groups.append(current)
            current = []
        current.append(day)
    if current:
        groups.append(current)
    return groups


def _months(start, end):
    groups = []
    for day in _days(start, end):
        if groups and (groups[-1][0].year, groups[-1][0].month) == (day.year, day.month):
            groups[-1].append(day)
        else:
            groups.append([day])
    return groups


def first_day(stats):
    """Первый игровой день, за который есть хоть какие-то цифры, или None."""
    days = [parse_day(k) for k, row in (stats.get("daily") or {}).items()
            if isinstance(row, dict) and any(row.get(m) for m in METRICS)]
    days = [d for d in days if d]
    return min(days) if days else None


def grouping(period, stats, today):
    """(как группировать, первый день): "day", "week" или "month"."""
    if period == "all":
        start = min(first_day(stats) or today, today)
        span = (today - start).days + 1
        if span <= MAX_DAY_BARS:
            return "day", start
        if len(_weeks(start, today)) <= MAX_WEEK_BARS:
            return "week", start
        return "month", start
    days = {"7d": 7, "14d": 14, "30d": 30}.get(period, 14)
    return ("week" if period == "30d" else "day"), today - timedelta(days=days - 1)


def buckets(stats, period, today):
    """Столбики графика за период: [{kind, start, end, days, today, per_day, titanite, rooms, floors, potions}]."""
    daily = stats.get("daily") or {}
    kind, start = grouping(period, stats, today)
    if kind == "day":
        groups = [[d] for d in _days(start, today)]
    elif kind == "week":
        groups = _weeks(start, today)
    else:
        groups = _months(start, today)
    return [_bucket(kind, g, daily, today) for g in groups]


def day_titanite(stats, day):
    return _day_values(stats.get("daily") or {}, day)["titanite"]


def totals(stats, period, today, bars=None):
    """Плитки: титанит, титанит сегодня, зелье, комнаты, этажи — за период. «Всё время» — общие счётчики файла
    (как старая вкладка: в них есть и дни, которых уже нет в daily)."""
    daily = stats.get("daily") or {}
    result = {"today": _day_values(daily, today)["titanite"]}
    if period == "all":
        for metric in METRICS:
            result[metric] = int(stats.get(f"total_{metric}", 0) or 0)
        return result
    bars = bars if bars is not None else buckets(stats, period, today)
    for metric in METRICS:
        result[metric] = sum(b[metric] for b in bars)
    return result


def nice_ticks(top, count=4):
    """Деления шкалы слева: 0 и «круглые» числа до верха графика (верх — не меньше самого высокого столбика)."""
    if top <= 0:
        return [0, 25, 50, 75, 100][:count + 1]
    raw = top / count
    magnitude = 10 ** (len(str(int(raw))) - 1)
    for mult in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        step = mult * magnitude
        if step == int(step) and step * count >= top:
            break
    return [int(step) * i for i in range(count + 1)]


def calc_rewards(titanite):
    """Комнаты, этажи и зелье по титаниту за день — как старая вкладка (первые 10 комнат по 6, дальше по 12 с «x2»)."""
    if titanite <= 60:
        rooms = titanite // 6
        potions = rooms * 25
    else:
        rooms = 10 + (titanite - 60) // 12
        potions = 250 + ((titanite - 60) // 12) * 50
    return rooms, rooms // 5, potions


def correction(stats, day, new_total):
    """Ручная корректировка титанита за день. Возвращает ("below_bot", сколько бот собрал сам), ("same", 0)
    или ("ok", {метрика: на сколько изменить})."""
    row = (stats.get("daily") or {}).get(day, {}) or {}
    current = int(row.get("titanite", 0) or 0)
    baseline = int(row.get("bot_titanite", 0) or 0)
    if new_total < baseline:
        return "below_bot", baseline
    delta = new_total - current
    if delta == 0:
        return "same", 0
    old, new = calc_rewards(current), calc_rewards(new_total)
    changes = {"titanite": delta}
    for metric, before, after in zip(("rooms", "floors", "potions"), old, new):
        if after != before:
            changes[metric] = after - before
    return "ok", changes


def correction_days(today, selected=None):
    """Дни для ручной корректировки: последние 7 (сегодня первым) и день, выбранный на графике (ваш ответ)."""
    days = [today - timedelta(days=i) for i in range(CORRECTION_DAYS)]
    if selected and selected not in days and selected <= today:
        days.append(selected)
    return days


def parse_total(text):
    """Титанит из поля: целое число от 0, иначе None."""
    text = (text or "").strip().replace(" ", "")
    return int(text) if text.isdigit() else None


def today_of(game_datetime):
    """Игровая дата (date) из stats_manager.get_game_datetime()."""
    return game_datetime.date() if isinstance(game_datetime, datetime) else game_datetime

