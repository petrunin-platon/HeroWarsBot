# telegram_report.py
# Красивые сообщения для Telegram (задача 13): итог сессии, окно SOS, проверка пака, тревоги бота.
# Текст — HTML (parse_mode="HTML"): <b>жирный</b>, <i>курсив</i>, <code>моноширинный</code>.
# Кнопки можно красить (поле style у InlineKeyboardButton): "success" — зелёная, "primary" — синяя, "danger" — красная.
# Старые приложения Telegram цвет не показывают, но кнопки работают.
# Модуль без сети и без OpenCV: только собирает текст и кнопки, проверяется тестами (tests/test_telegram.py).
import html
import json
import os
import time

from i18n import get_text

# Цвета кнопок
GREEN, BLUE, RED = "success", "primary", "danger"

# Подписи для Telegram не длиннее 1024 знаков, сообщения — 4096
CAPTION_LIMIT = 1024
MESSAGE_LIMIT = 4096

ROOM_ICONS = {"water": "💧", "mix": "🌀", "earth": "🌿", "fire": "🔥"}
ROOM_NAMES = {"water": "Вода", "mix": "Смешанная", "earth": "Земля", "fire": "Огонь"}
LINE = "━━━━━━━━━━━━━━━━"
BAR_CELLS = 10


def esc(text):
    """Текст для HTML Telegram: <, > и & в именах и причинах не должны ломать разметку."""
    return html.escape(str(text), quote=False)


def button(text, data, style=None):
    """Кнопка под сообщением. style — GREEN, BLUE, RED или None (цвет по умолчанию)."""
    btn = {"text": text, "callback_data": data}
    if style:
        btn["style"] = style
    return btn


def keyboard(*rows):
    """Клавиатура под сообщением: каждая строка — список кнопок."""
    return {"inline_keyboard": [list(row) for row in rows]}


def chosen(text):
    """Клавиатура после ответа: одна зелёная кнопка «✅ Выбрано: …», нажимать её не нужно."""
    return keyboard([button(f"✅ {text}", "noop", GREEN)])


def titan_name(titan, lang="RU"):
    name = get_text(lang, f"titan_{titan}")
    return name if name != f"titan_{titan}" else str(titan).capitalize()


def room_title(room):
    """«🔥 Огонь» по стихии комнаты; неизвестная стихия — пустая строка."""
    if room in ROOM_NAMES:
        return f"{ROOM_ICONS[room]} {ROOM_NAMES[room]}"
    return ""  # "unknown" — бот ещё не входил в комнату


def hp_icon(hp):
    if hp <= 0:
        return "💀"
    if hp >= 70:
        return "🟢"
    if hp >= 40:
        return "🟡"
    return "🔴"


def hp_bar(hp):
    """Полоска ХП из 10 клеток: ▰▰▰▰▰▰▱▱▱▱."""
    filled = max(0, min(BAR_CELLS, round(hp / 100 * BAR_CELLS)))
    return "▰" * filled + "▱" * (BAR_CELLS - filled)


def _number(value):
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def titan_line(titan, hp, energy=None, before=None, lang="RU"):
    """Строка титана: значок, имя, полоска, ХП, сколько потерял за бой и энергия."""
    hp = _number(hp)
    if hp is None:
        return f"❔ <b>{esc(titan_name(titan, lang))}</b> — не прочитано"
    line = f"{hp_icon(hp)} <b>{esc(titan_name(titan, lang))}</b>  <code>{hp_bar(hp)}</code> {hp}%"
    before = _number(before)
    if before is not None and before > hp:
        line += f" <i>(−{before - hp})</i>"
    energy = _number(energy)
    if energy is not None:
        line += f" · ⚡{energy}%"
    return line


def team_lines(titans, before=None, lang="RU"):
    """Строки пака. titans — {титан: ХП} или {титан: {"hp": .., "energy": ..}}."""
    before = before or {}
    lines = []
    for titan, value in (titans or {}).items():
        if isinstance(value, dict):
            hp = None if value.get("status") == "ОТСУТСТВУЕТ" else value.get("hp")  # иконку на окне не нашли
            lines.append(titan_line(titan, hp, value.get("energy"), before.get(titan), lang))
        else:
            lines.append(titan_line(titan, value, None, before.get(titan), lang))
    return lines


def enemies_text(enemies, lang="RU"):
    return ", ".join(esc(titan_name(e, lang)) for e in enemies) if enemies else "не распознаны"


def fit(text, limit):
    """Обрезает слишком длинный текст по строкам, чтобы не порвать HTML-теги посередине."""
    if len(text) <= limit:
        return text
    lines, size = [], 0
    for line in text.split("\n"):
        if size + len(line) + 1 > limit - 2:
            break
        lines.append(line)
        size += len(line) + 1
    return "\n".join(lines + ["…"])


# ---------------------------------------------------------------------------
# Тревоги бота (send_alert): откат не удался, завис, ПК заблокирован, бот решил сам
# ---------------------------------------------------------------------------
def alert(icon, title, lines=(), room=None, enemies=None, footer=None, lang="RU"):
    """Короткое сообщение: заголовок жирным, пояснение, комната и враги, внизу курсивом — что делать."""
    parts = [f"{icon} <b>{esc(title)}</b>"]
    body = [esc(line) for line in lines if line]
    if body:
        parts.append("")
        parts.extend(body)
    info = []
    if room_title(room):
        info.append(f"🚪 Комната: {room_title(room)}")
    if enemies:
        info.append(f"⚔️ Враги: {enemies_text(enemies, lang)}")
    if info:
        parts.append("")
        parts.extend(info)
    if footer:
        parts.append("")
        parts.append(f"<i>{esc(footer)}</i>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Окно SOS («Требуется вмешательство»)
# ---------------------------------------------------------------------------
def sos_report(titans, info=None, is_manual=False, can_rollback=True, lang="RU"):
    """Подпись к скриншоту SOS. titans — ХП из [SOS_TRIGGER]; info — sos_info.json от бота
    (комната, номер, враги, причина, пак с ХП и энергией, ХП до боя). Без info — только титаны, как раньше."""
    info = info or {}
    no_team = info.get("type") == "NO_VALID_TEAM"
    title = "Нет подходящего пака" if no_team else "Нужна ваша помощь"
    head = f"🆘 <b>{title}</b>"
    where = []
    if info.get("room_no"):
        where.append(f"комната {info['room_no']}")
    if room_title(info.get("room")):
        where.append(room_title(info["room"]))
    parts = [head + (f"\n{' · '.join(where)}" if where else "")]

    if info.get("reason"):
        parts += ["", f"❗ <i>{esc(info['reason'])}</i>"]
    elif not can_rollback and not is_manual:
        parts += ["", "❗ <i>Нет правил для смены пака</i>"]

    if "enemies" in info:
        parts += ["", f"⚔️ <b>Враги:</b> {enemies_text(info.get('enemies'), lang)}"]

    team = info.get("team") or titans
    if team:
        parts += ["", "🛡 <b>Наш пак после боя:</b>"]
        parts += team_lines(team, info.get("hp_before"), lang)

    parts += [LINE]
    if is_manual:
        parts.append("<i>Бой шёл вручную (Ангус): откатить его бот не может.</i>")
    elif no_team:
        parts.append("<i>Пройдите комнату руками или остановите бота.</i>")
    else:
        parts.append("<i>Откатить бой и собрать другой пак, пройти руками или продолжить?</i>")
    return fit("\n".join(parts), CAPTION_LIMIT)


def sos_keyboard(is_manual=False, can_rollback=True, lang="RU"):
    """Кнопки SOS: зелёная «Откатить» (или красная «Остановить»), синяя «Пройти руками», серая «Продолжить»."""
    if is_manual or not can_rollback:
        middle = button("🛑 " + get_text(lang, "tg_bot_stop"), "stop", RED)
    else:
        middle = button("🔄 " + get_text(lang, "tg_bot_rollback"), "rollback", GREEN)
    return keyboard(
        [middle],
        [button("🎮 " + get_text(lang, "tg_bot_manual"), "manual", BLUE)],
        [button("➡️ " + get_text(lang, "tg_bot_ignore"), "ignore")],
    )


def test_report(titans, lang="RU"):
    """Подпись к скриншоту: проверяемый пак выиграл, нужно подтверждение."""
    parts = [f"🧪 <b>{esc(get_text(lang, 'test_success'))}</b>", "", "🛡 <b>Пак после боя:</b>"]
    parts += team_lines(titans, None, lang)
    parts += [LINE, "<i>Сохранить пак правилом против этих врагов или попробовать другой?</i>"]
    return fit("\n".join(parts), CAPTION_LIMIT)


def test_keyboard(lang="RU"):
    return keyboard(
        [button(get_text(lang, "test_btn_confirm"), "test_confirm", GREEN)],
        [button(get_text(lang, "test_btn_rollback"), "test_retry", BLUE)],
    )


def pack_confirm_keyboard(lang="RU"):
    return keyboard(
        [button("✅ " + get_text(lang, "tg_bot_btn_confirm"), "confirm_pack", GREEN)],
        [button("✏️ " + get_text(lang, "tg_bot_btn_retry"), "retry_pack", BLUE)],
    )


# sos_info.json старше этого — от прошлого окна SOS, в сообщение его не берём
SOS_INFO_MAX_AGE_S = 120


def read_sos_info(path, now=None):
    """sos_info.json, который бот пишет перед [SOS_TRIGGER]. Нет файла, он битый или старый — пустой словарь."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    if (now or time.time()) - data.get("saved", 0) > SOS_INFO_MAX_AGE_S:
        return {}
    return data


def write_sos_info(path, info, now=None):
    """Пишет sos_info.json целиком (через временный файл, чтобы окно программы не прочитало половину)."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({**info, "saved": now or time.time()}, f, ensure_ascii=False)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Итог сессии
# ---------------------------------------------------------------------------
LIMIT_REASONS = ("Превышен лимит", "Цель по титаниту", "Пройдено ")
USER_REASONS = ("Ручная остановка", "Экстренная остановка", "Команда STOP")


def session_status(reason):
    """(значок, заголовок, удачно ли) по причине остановки."""
    reason = reason or ""
    if reason.startswith("Ошибка"):
        return "⛔", "Бот упал с ошибкой", False
    if reason.startswith(LIMIT_REASONS):
        return "✅", "Фарм завершён", True
    if reason.startswith(USER_REASONS):
        return "⏹", "Бот остановлен вами", True
    if not reason:
        return "⏹", "Бот остановлен", True
    return "⚠️", "Бот остановился: нужна проверка", False


def duration_text(seconds):
    minutes = int(seconds // 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours} ч {minutes:02d} мин"
    if minutes:
        return f"{minutes} мин {int(seconds % 60):02d} с"
    return f"{int(seconds)} с"


def session_report(data):
    """Итог сессии. data — SessionLog.report_data(): reason, started, finished (ЧЧ:ММ), seconds, rooms, floors,
    titanite, by_room {стихия: комнат}, counts {sos, rollbacks, auto_rollbacks, stuck, heal_packs, door_misses},
    longest [(номер, стихия, секунд)], avg_room (секунд или None)."""
    icon, title, _ = session_status(data.get("reason"))
    parts = [f"{icon} <b>{title}</b>"]
    if data.get("reason"):
        parts.append(f"<i>{esc(data['reason'])}</i>")

    when = f"🕐 {data.get('started', '?')} → {data.get('finished', '?')}"
    parts += ["", f"{when}  ·  ⏱ {duration_text(data.get('seconds', 0))}"]
    parts += [LINE,
              f"🚪 Комнат: <b>{data.get('rooms', 0)}</b>   🏰 Этажей: <b>{data.get('floors', 0)}</b>",
              f"💎 Титанит: <b>{data.get('titanite', 0)}</b>"]
    by_room = data.get("by_room") or {}
    if by_room:
        parts.append("   ".join(f"{ROOM_ICONS.get(r, '🚪')} {n}" for r, n in sorted(by_room.items(),
                                                                                key=lambda x: -x[1])))
    if data.get("avg_room"):
        parts.append(f"⏳ Комната в среднем: {duration_text(data['avg_room'])}")

    counts = data.get("counts") or {}
    problems = []
    if counts.get("sos"):
        problems.append(f"🆘 Окон «Требуется вмешательство»: {counts['sos']}")
    if counts.get("rollbacks"):
        own = counts.get("auto_rollbacks", 0)
        problems.append(f"🔄 Откатов: {counts['rollbacks']}" + (f" (бот сам: {own})" if own else ""))
    if counts.get("heal_packs"):
        problems.append(f"🩹 Паков отхила собрал сам: {counts['heal_packs']}")
    if counts.get("stuck"):
        problems.append(f"🧊 Зависаний: {counts['stuck']}")
    if counts.get("door_misses"):
        problems.append(f"🎯 Промахов по двери: {counts['door_misses']}")
    parts.append(LINE)
    parts += problems or ["👌 Без происшествий"]

    longest = data.get("longest") or []
    if longest:
        parts += ["", "🐢 <b>Самые долгие комнаты:</b>"]
        for no, room, seconds in longest:
            parts.append(f"   №{no} {ROOM_ICONS.get(room, '')} {esc(ROOM_NAMES.get(room, room))} — "
                         f"{duration_text(seconds)}")
    return fit("\n".join(parts), MESSAGE_LIMIT)
