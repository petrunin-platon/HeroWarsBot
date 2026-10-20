# telegram_report.py
# Красивые сообщения для Telegram (задача 13): итог сессии, окно SOS, проверка пака, тревоги бота.
# Текст — HTML (parse_mode="HTML"): <b>жирный</b>, <i>курсив</i>, <code>моноширинный</code>.
# Кнопки можно красить (поле style у InlineKeyboardButton): "success" — зелёная, "primary" — синяя, "danger" — красная.
# Старые приложения Telegram цвет не показывают, но кнопки работают.
# Язык — тот же, что в окне программы: слова из telegram_i18n.py, имена титанов и стихий и кнопки — из i18n.py.
# Модуль без сети и без OpenCV: только собирает текст и кнопки, проверяется тестами (tests/test_telegram.py).
import html
import json
import re
import os
import time

from i18n import get_text
from telegram_i18n import tg_text

# Цвета кнопок
GREEN, BLUE, RED = "success", "primary", "danger"

# Подписи для Telegram не длиннее 1024 знаков, сообщения — 4096
CAPTION_LIMIT = 1024
MESSAGE_LIMIT = 4096

ROOM_ICONS = {"water": "💧", "mix": "🌀", "earth": "🌿", "fire": "🔥"}
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


def room_name(room, lang="RU"):
    """Стихия словом на языке программы (из i18n.py: «🔥 Огонь» → «Огонь»)."""
    return get_text(lang, f"elem_{room}").split(" ", 1)[-1]


def room_title(room, lang="RU"):
    """«🔥 Огонь» по стихии комнаты; неизвестная стихия — пустая строка."""
    if room in ROOM_ICONS:
        return f"{ROOM_ICONS[room]} {room_name(room, lang)}"
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
        return f"❔ <b>{esc(titan_name(titan, lang))}</b> — {tg_text(lang, 'not_read')}"
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


def humanize(text, lang="RU"):
    """Причина из лога по-человечески: «ARAJI: ХП 12%» → «Араджи: ХП 12%» (имена титанов на языке программы)."""
    def name(match):
        word = match.group(0)
        known = get_text(lang, f"titan_{word.lower()}") != f"titan_{word.lower()}"
        return titan_name(word.lower(), lang) if known else word
    return re.sub(r"\b[A-Z]{3,}\b", name, str(text))


def enemies_text(enemies, lang="RU"):
    return ", ".join(esc(titan_name(e, lang)) for e in enemies) if enemies else tg_text(lang, "enemies_unknown")


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
    """Короткое сообщение: заголовок жирным, сразу под ним комната и враги (на кого шли — это главное),
    потом пояснение, внизу курсивом — что делать. Заголовок, строки и footer — уже на нужном языке (tg_text)."""
    parts = [f"{icon} <b>{esc(title)}</b>"]
    if room_title(room, lang):
        parts.append(f"🚪 {tg_text(lang, 'room')}: {room_title(room, lang)}")
    if enemies:
        parts += ["", f"⚔️ <b>{tg_text(lang, 'enemies')}:</b> {enemies_text(enemies, lang)}"]
    body = [esc(humanize(line, lang)) for line in lines if line]
    if body:
        parts.append("")
        parts.extend(body)
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
    title = tg_text(lang, "sos_no_team" if no_team else "sos_title")
    head = f"🆘 <b>{title}</b>"
    where = []
    if info.get("room_no"):
        where.append(tg_text(lang, "sos_room_no", no=info["room_no"]))
    if room_title(info.get("room"), lang):
        where.append(room_title(info["room"], lang))
    parts = [head + (f"\n{' · '.join(where)}" if where else "")]

    # Главное — на кого шли (ваше замечание к задаче 13): враги сразу под заголовком, каждый на своей строке
    if "enemies" in info:
        parts += ["", f"⚔️ <b>{tg_text(lang, 'sos_enemies')}</b>"]
        if info.get("enemies"):
            parts += [f"   • <b>{esc(titan_name(e, lang))}</b>" for e in info["enemies"]]
        else:
            parts.append(f"   <i>{tg_text(lang, 'sos_enemies_unknown')}</i>")

    if info.get("reason"):
        parts += ["", f"❗ <i>{esc(humanize(info['reason'], lang))}</i>"]
    elif not can_rollback and not is_manual:
        parts += ["", f"❗ <i>{tg_text(lang, 'sos_no_rules')}</i>"]

    # Наш пак — списком, как враги: полоска ХП, сколько потерял за бой, энергия
    team = info.get("team") or titans
    if team:
        parts += ["", f"🛡 <b>{tg_text(lang, 'sos_team')}</b>"]
        parts += team_lines(team, info.get("hp_before"), lang)

    parts += [LINE]
    if is_manual:
        parts.append(f"<i>{tg_text(lang, 'sos_manual')}</i>")
    elif no_team:
        parts.append(f"<i>{tg_text(lang, 'sos_no_team_hint')}</i>")
    else:
        parts.append(f"<i>{tg_text(lang, 'sos_question')}</i>")
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
    parts = [f"🧪 <b>{esc(get_text(lang, 'test_success'))}</b>", "", f"🛡 <b>{tg_text(lang, 'test_team')}</b>"]
    parts += team_lines(titans, None, lang)
    parts += [LINE, f"<i>{tg_text(lang, 'test_question')}</i>"]
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


def session_status(reason, lang="RU"):
    """(значок, заголовок, удачно ли) по причине остановки. Причину бот пишет по-русски (как в логе)."""
    reason = reason or ""
    if reason.startswith("Ошибка"):
        return "⛔", tg_text(lang, "st_error"), False
    if reason.startswith(LIMIT_REASONS):
        return "✅", tg_text(lang, "st_done"), True
    if reason.startswith(USER_REASONS):
        return "⏹", tg_text(lang, "st_user"), True
    if not reason:
        return "⏹", tg_text(lang, "st_stopped"), True
    return "⚠️", tg_text(lang, "st_check"), False


def duration_text(seconds, lang="RU"):
    minutes = int(seconds // 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return tg_text(lang, "dur_h", h=hours, m=f"{minutes:02d}")
    if minutes:
        return tg_text(lang, "dur_m", m=minutes, s=f"{int(seconds % 60):02d}")
    return tg_text(lang, "dur_s", s=int(seconds))


def session_report(data, lang="RU"):
    """Итог сессии на языке программы. data — SessionLog.report_data(): reason, started, finished (ЧЧ:ММ), seconds,
    rooms, floors, titanite, by_room {стихия: комнат}, counts {sos, rollbacks, auto_rollbacks, stuck, heal_packs,
    door_misses}, longest [(номер, стихия, секунд)], avg_room (секунд или None)."""
    icon, title, _ = session_status(data.get("reason"), lang)
    parts = [f"{icon} <b>{title}</b>"]
    if data.get("reason"):
        parts.append(f"<i>{esc(data['reason'])}</i>")

    when = f"🕐 {data.get('started', '?')} → {data.get('finished', '?')}"
    parts += ["", f"{when}  ·  ⏱ {duration_text(data.get('seconds', 0), lang)}"]
    parts += [LINE,
              f"🚪 {tg_text(lang, 'rep_rooms')}: <b>{data.get('rooms', 0)}</b>   "
              f"🏰 {tg_text(lang, 'rep_floors')}: <b>{data.get('floors', 0)}</b>",
              f"💎 {tg_text(lang, 'rep_titanite')}: <b>{data.get('titanite', 0)}</b>"]
    by_room = data.get("by_room") or {}
    if by_room:
        parts.append("   ".join(f"{ROOM_ICONS.get(r, '🚪')} {n}" for r, n in sorted(by_room.items(),
                                                                                key=lambda x: -x[1])))
    if data.get("avg_room"):
        parts.append(f"⏳ {tg_text(lang, 'rep_avg', t=duration_text(data['avg_room'], lang))}")

    counts = data.get("counts") or {}
    problems = []
    if counts.get("sos"):
        problems.append(f"🆘 {esc(tg_text(lang, 'rep_sos', n=counts['sos']))}")
    if counts.get("rollbacks"):
        own = counts.get("auto_rollbacks", 0)
        problems.append(f"🔄 {tg_text(lang, 'rep_rollbacks', n=counts['rollbacks'])}"
                        + (f" ({tg_text(lang, 'rep_rollbacks_own', n=own)})" if own else ""))
    if counts.get("heal_packs"):
        problems.append(f"🩹 {tg_text(lang, 'rep_heal', n=counts['heal_packs'])}")
    if counts.get("stuck"):
        problems.append(f"🧊 {tg_text(lang, 'rep_stuck', n=counts['stuck'])}")
    if counts.get("door_misses"):
        problems.append(f"🎯 {tg_text(lang, 'rep_door', n=counts['door_misses'])}")
    parts.append(LINE)
    parts += problems or [f"👌 {tg_text(lang, 'rep_clean')}"]

    longest = data.get("longest") or []
    if longest:
        parts += ["", f"🐢 <b>{tg_text(lang, 'rep_longest')}</b>"]
        for no, room, seconds in longest:
            parts.append(f"   №{no} {ROOM_ICONS.get(room, '')} {esc(room_name(room, lang) if room in ROOM_ICONS else room)} — "
                         f"{duration_text(seconds, lang)}")
    return fit("\n".join(parts), MESSAGE_LIMIT)
