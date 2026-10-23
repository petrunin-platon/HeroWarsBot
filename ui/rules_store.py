"""Что показывает и пишет «Мастер правил → База и комнаты» (задача 15, шаг 5а; макет 03a) — profile.yml и основные паки.

Окно держит все значения в словаре «формы» и пишет их кнопкой «Сохранить настройки» (ваш ответ 22.10.2026, сверка 4.1).
Файлы пишутся как можно реже (ваше замечание: беречь диск): profile.yml — только если поменялось что-то из профиля,
bot_data/rules/<стихия>.yml — только у стихий, где поменяли основной пак. В профиль пишутся только поменянные значения:
остальные ключи профиля (и то, что за это время поменяло другое окно, например «Тактика») остаются как были.

Ключи профиля — те же, что у старой вкладки (ui/rules_tab.py) и бота:
- цели: settings.target_titanite / target_rooms / target_floors / target_time. Цель одна (сверка 1.5 и 1.7): окно пишет
  все четыре — выбранную и нули;
- global_thresholds.critical_hp, max_hp_delta; settings.reset_hour, angus_manual_control, auto_rollback, telegram;
- запасные паки — settings.backup_teams (как окно «Тактика», tactics.write_tactics);
- вкладка «Авто-тактика и ХП» (шаг 5б, макет 03b) — то же, что писало окно «⚙️ Тактика» (tactics.read_tactics /
  write_tactics): settings.auto_rollback_tries, sos_timeout_minutes, door_order, heal_below_hp, heal_remove_order;
  global_thresholds.group_loss_titans, group_loss_percent, titan_critical_hp.
Значения при чтении — по правилам бота (tactics.Settings, ui/launch_config.py): нет ключа — то, что взял бы бот.
Модуль без Tk.
"""
import copy
import os
import shutil

import yaml

import data_paths
import tactics
from ui import launch_config

PROFILE = launch_config.PROFILE
ROOMS = ("earth", "water", "fire", "mix")
GOAL_KINDS = tuple(kind for kind, _key, _default in launch_config.GOALS)
MAX_BACKUPS = 5          # запасных паков на стихию (как в окне «Тактика»)
PERCENT_MAX = 100
GOAL_MAX = 999999

# Где лежит каждое значение формы в профиле: (раздел, ключ)
PLACES = {
    "critical_hp": ("global_thresholds", "critical_hp"),
    "max_hp_delta": ("global_thresholds", "max_hp_delta"),
    "reset_hour": ("settings", "reset_hour"),
    "angus_manual_control": ("settings", "angus_manual_control"),
    "auto_rollback": ("settings", "auto_rollback"),
    "telegram": ("settings", "telegram"),
}
# Вкладка «Авто-тактика и ХП»: ключи tactics.read_tactics, пишутся tactics.write_tactics
TACTICS_KEYS = ("auto_rollback_tries", "sos_timeout_minutes", "group_loss_titans", "group_loss_percent",
                "door_order", "heal_below_hp", "heal_remove_order", "titan_critical_hp")
BASE_KEYS = ("goal",) + tuple(PLACES) + ("backup_teams",)
PROFILE_KEYS = BASE_KEYS + TACTICS_KEYS
# Пределы чисел вкладки (как в окне «Тактика» и у бота, tactics.Settings): (от, до)
LIMITS = {
    "auto_rollback_tries": (1, tactics.MAX_TRIES),
    "sos_timeout_minutes": (0, tactics.MAX_SOS_TIMEOUT),
    "group_loss_titans": (0, 5),
    "group_loss_percent": (0, PERCENT_MAX),
    "heal_below_hp": (0, PERCENT_MAX),
    "titan_critical_hp": (0, PERCENT_MAX),
}

# Чем закончилось чтение файла
OK, MISSING, BROKEN = "ok", "missing", "broken"


def read_profile(path=PROFILE):
    """(состояние, словарь профиля). Нет файла — MISSING и {}; битый файл — BROKEN и {} (бот тоже берёт значения
    по умолчанию). Для BROKEN третьим — где ошибка (строка, символ) или ""."""
    if not os.path.exists(path):
        return MISSING, {}, ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        return BROKEN, {}, f"{mark.line + 1}:{mark.column + 1}" if mark else ""
    except OSError:
        return BROKEN, {}, ""
    if not isinstance(data, dict):
        return BROKEN, {}, ""
    return OK, data, ""


def _number(value, default):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def form_from_profile(profile):
    """Значения формы из словаря профиля (по правилам бота)."""
    get = tactics.profile_getter(profile)
    settings = tactics.Settings(get)
    goal = ("titanite", 0)
    for kind, key, default in launch_config.GOALS:
        value = max(0, _number(get(key, default), 0))
        if value > 0:
            goal = (kind, value)
            break
    tg = settings_dict(profile).get("telegram")
    tg = tg if isinstance(tg, dict) else {}
    tactic = tactics.read_tactics(profile)
    return {
        "goal": goal,
        "critical_hp": settings.critical_hp,
        "max_hp_delta": settings.max_hp_delta,
        "reset_hour": max(0, min(23, settings.reset_hour)),
        "angus_manual_control": get("angus_manual_control", False) is True,
        "auto_rollback": settings.auto_rollback,
        "telegram": {"active": tg.get("active", False) is True, "token": str(tg.get("token", "") or ""),
                     "chat_id": str(tg.get("chat_id", "") or "")},
        "backup_teams": tactic["backup_teams"],
        **{key: tactic[key] for key in TACTICS_KEYS},
    }


def settings_dict(profile):
    value = profile.get("settings")
    return value if isinstance(value, dict) else {}


def read_default_teams(read=None):
    """Основные паки стихий из bot_data/rules/<стихия>.yml: ({стихия: пак}, [стихии с битым файлом])."""
    teams, broken = {}, []
    for room in ROOMS:
        state, data = read_rules(room) if read is None else read(room)
        team = data.get("default_team") if state == OK else None
        teams[room] = [str(t) for t in team] if isinstance(team, list) else []
        if state == BROKEN:
            broken.append(room)
    return teams, broken


def read_rules(room):
    """(состояние, словарь) файла правил стихии."""
    path = data_paths.rules_path(room)
    if not os.path.exists(path):
        return MISSING, {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return BROKEN, {}
    return (OK, data) if isinstance(data, dict) else (BROKEN, {})


# ── Проверка полей ──────────────────────────────────────────────────────────
def parse_number(text, limit, low=0):
    """Число из поля: (число, None) или (None, "empty"/"range"). Пробелы по краям не мешают."""
    text = str(text).strip()
    if not text:
        return None, "empty"
    if not text.isdigit() or not low <= int(text) <= limit:
        return None, "range"
    return int(text), None


def telegram_on(tg):
    """Telegram включён и заполнен — то же правило, что у бота (telegram_agent.read_telegram_settings)."""
    token, chat_id = str(tg.get("token", "") or ""), str(tg.get("chat_id", "") or "")
    return bool(tg.get("active") and token and chat_id and "YOUR_" not in token and "YOUR_" not in chat_id
                and chat_id != "None")


def add_backup(form, room, team):
    """Добавить запасной пак стихии. Такой же пак (в любом порядке) не добавляется, больше MAX_BACKUPS — тоже.
    True — добавлен."""
    packs = form["backup_teams"].setdefault(room, [])
    if len(packs) >= MAX_BACKUPS or sorted(team) in [sorted(p) for p in packs]:
        if not packs:
            form["backup_teams"].pop(room, None)
        return False
    packs.append(list(team))
    return True


def choose_door(order, place, room):
    """Порядок дверей: на место place выбрали стихию room. Стоявшая там стихия встаёт на прежнее место room
    (как в окне «Тактика»: повторов не бывает). Возвращает новый список."""
    order = list(order)
    if room not in order or not 0 <= place < len(order):
        return order
    other = order.index(room)
    order[place], order[other] = room, order[place]
    return order


def choose_remove(order, place, titan):
    """«Кого убирать из пака ради раненого» (до tactics.MAX_HEAL_REMOVE): на место place выбрали titan,
    None — «— сам —» (место пустое, следующие сдвигаются). Титан уже стоит на другом месте — меняются местами.
    Место дальше занятых — титан встаёт в конец. Возвращает новый список."""
    order = list(order)
    if titan is None:
        if place < len(order):
            order.pop(place)
        return order
    if titan in order:
        other = order.index(titan)
        if place < len(order):
            order[place], order[other] = titan, order[place]
        return order
    if place < len(order):
        order[place] = titan
    elif len(order) < tactics.MAX_HEAL_REMOVE:
        order.append(titan)
    return order


def set_personal(form, titan, value):
    """Личный порог паники титана (value — % ХП) или None — убрать его. Новый титан — в конец списка."""
    personal = dict(form["titan_critical_hp"])
    if value is None:
        personal.pop(titan, None)
    else:
        personal[titan] = value
    form["titan_critical_hp"] = personal


def remove_backup(form, room, index):
    packs = form["backup_teams"].get(room, [])
    if 0 <= index < len(packs):
        packs.pop(index)
    if not packs:
        form["backup_teams"].pop(room, None)


# ── Запись ──────────────────────────────────────────────────────────────────
def changed_keys(saved, form):
    """Какие значения формы отличаются от сохранённых."""
    return [key for key in PROFILE_KEYS if form.get(key) != saved.get(key)]


def apply_form(profile, form, keys):
    """Записать в словарь профиля значения формы с ключами keys (остальное не трогается). Возвращает профиль."""
    for section in ("settings", "global_thresholds"):
        if not isinstance(profile.get(section), dict):
            profile[section] = {}
    for key in keys:
        if key == "goal":
            kind, value = form["goal"]
            for goal_kind, profile_key, _default in launch_config.GOALS:
                profile["settings"][profile_key] = value if goal_kind == kind else 0
        elif key == "backup_teams":
            teams = {room: [list(p) for p in packs] for room, packs in form["backup_teams"].items() if packs}
            tactics.write_tactics(profile, {"backup_teams": teams})
        elif key in TACTICS_KEYS:
            tactics.write_tactics(profile, {key: copy.deepcopy(form[key])})
        else:
            section, profile_key = PLACES[key]
            profile[section][profile_key] = copy.deepcopy(form[key])
    return profile


def write_profile(profile, path=PROFILE):
    """Записать profile.yml (как старая вкладка) и его копию bot_data/profile.yml.bak (для «Восстановить / Сброс»)."""
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.dump(profile, f, allow_unicode=True, default_flow_style=False)
    os.replace(tmp, path)
    shutil.copy2(path, data_paths.profile_backup_file())


def save_profile(saved, form, path=PROFILE):
    """Записать поменянные значения формы в profile.yml. Файл перечитывается: остальные ключи — как сейчас в файле.
    Возвращает (OK, ключи) — записано (пустой список — писать было нечего), (BROKEN, где) — файл битый, не тронут."""
    keys = changed_keys(saved, form)
    state, profile, where = read_profile(path)
    if state == BROKEN:
        return BROKEN, where
    if state == MISSING:
        keys = list(PROFILE_KEYS)  # первое сохранение: в профиль — всё, что видно на экране
    if not keys:
        return OK, []
    if "goal" not in keys:
        keys.append("goal")  # цель всегда одна: старые лишние цели обнуляются при любом сохранении (сверка 1.7)
    write_profile(apply_form(profile, form, keys), path)
    return OK, keys


def save_default_team(room, team):
    """Основной пак стихии в bot_data/rules/<стихия>.yml (как старая вкладка): файл перечитывается, меняется только
    default_team, правила остаются. Битый файл не трогается: возвращает False."""
    state, data = read_rules(room)
    if state == BROKEN:
        return False
    if state == MISSING:
        data = {"rules": []}
    data["default_team"] = list(team)
    path = data_paths.rules_path(room)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return True


def restore_profile(path=PROFILE):
    """«Восстановить / Сброс» (как старая вкладка): profile.yml из копии bot_data/profile.yml.bak; копии нет —
    profile.yml удаляется (бот возьмёт значения по умолчанию). Возвращает "restored", "reset" или "nothing"."""
    backup = data_paths.profile_backup_file()
    if os.path.exists(backup):
        shutil.copy2(backup, path)
        return "restored"
    if os.path.exists(path):
        os.remove(path)
        return "reset"
    return "nothing"


def ensure_backup(path=PROFILE):
    """Копия profile.yml для «Восстановить / Сброс», если её ещё нет и профиль читается (старая вкладка делала копию
    при каждом открытии — теперь только когда её нет: файлы пишем как можно реже)."""
    backup = data_paths.profile_backup_file()
    if not os.path.exists(backup) and read_profile(path)[0] == OK:
        shutil.copy2(path, backup)
