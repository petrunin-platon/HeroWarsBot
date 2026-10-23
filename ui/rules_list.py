"""Что показывает и пишет «Мастер правил → Правила и перехваты» (задача 15, шаг 5в; макеты 03c и 03d) — правила
bot_data/rules/<стихия>.yml. Модуль без Tk.

Как и остальной мастер правил (ui/rules_store.py), вкладка ничего не пишет сама: список правил лежит в форме страницы
(page.rules), его меняют стрелки, тумблер, ✕, «Очистить все правила» и окно «Новое правило», а пишет — «Сохранить
настройки», и только у стихий, где правила правда поменялись (ваше замечание: беречь диск). Из файла меняется только
список rules: основной пак (default_team) и остальное остаётся как было.

Пока окно открыто, бот мог сам запомнить правило (после отката, «золотое правило» при запуске). Поэтому при сохранении
файл перечитывается: правила, которые появились в нём после того, как окно его прочитало, ставятся наверх списка,
а те, что бот за это время убрал (обновил правило с тем же условием), не возвращаются (save_rules).

Что видно в строке (ваши ответы 23.10.2026):
- значок по смыслу (вопрос 4.2): СКИП — правило запрещает дверь; ЛЕЧЕНИЕ — условие по ХП и смена пака, без врагов;
  иначе по условию: ВРАГИ (если в условии есть враги), ХП, ЭНЕРГИЯ;
- правила, которые бот запомнил сам, — коротко на языке окна (вопрос 4.3): «Авто: Ангус + Сильва в комнате»,
  «Золотое: …», ниже — кто и почему. В файле имя не меняется (его бот пишет в журнал); переименовали — видно ваше имя;
- пак [STOP] — «Спросить вас»: бот открывает окно «Нет подходящего пака» и ждёт ответа (а не мягкая пауза, как в макете);
- выключенное тумблером правило — enabled: false (бот его пропускает, rules_engine.rule_enabled); включили — пометка
  убирается: правила без неё включены.
Окно «Новое правило» при изменении правила сохраняет скрытые поля (source, allowed_delta, special_ult, enabled и всё,
чего окно не показывает) — старое окно их теряло (ошибка 4.4 сверки).
"""
import copy
import os

import yaml

import config
import data_paths
from i18n import get_text
from ui import rules_store, theme

ROOMS = rules_store.ROOMS
ROOM_NAMES_RU = {"earth": "Земля", "water": "Вода", "fire": "Огонь", "mix": "Смешанная"}   # для строк журнала [GUI]
ENEMIES = list(config.ENEMY_TITANS)     # враги, которых бот узнаёт в подземелье (картинки assets/enemy_<титан>.png)
TRIGGERS = ("hp", "energy", "enemies")
TRIGGER_KEYS = {"hp": "titan_hp_below", "energy": "titan_energy_below", "enemies": "enemies_contain"}
STOP_PACK = ["STOP"]
PACK, ASK, SKIP = "pack", "ask", "skip"
DEFAULT_VALUES = {"hp": 35, "energy": 100}   # как в старом окне «Новое правило»
MIN_PACK, MAX_PACK = 3, 5
MIN_FOUGHT = 1                                # обкатка — от 1 до 5 титанов (ваш ответ 23.10.2026)
# Имена правил, которые бот пишет сам (rules_engine.learned_rule_name, add_golden_rule)
LEARNED_PREFIX = "Анти-пак против:"
GOLDEN_PREFIX = "Золотое правило против:"
OK, MISSING, BROKEN = rules_store.OK, rules_store.MISSING, rules_store.BROKEN


# ── Чтение ──────────────────────────────────────────────────────────────────
def read_all(read=rules_store.read_rules):
    """Правила всех стихий: ({стихия: [правило]}, [стихии с битым файлом]). Записи не-словари пропускаются."""
    rules, broken = {}, []
    for room in ROOMS:
        state, data = read(room)
        rules[room] = _rule_list(data) if state == OK else []
        if state == BROKEN:
            broken.append(room)
    return rules, broken


def _rule_list(data):
    items = data.get("rules") if isinstance(data, dict) else None
    return [copy.deepcopy(r) for r in items or [] if isinstance(r, dict)] if isinstance(items, list) else []


# ── Что показать в строке ───────────────────────────────────────────────────
def enabled(rule):
    """Как у бота (rules_engine.rule_enabled): выключено только с enabled: false."""
    return rule.get("enabled") is not False


def action(rule):
    """Что делает правило: PACK — ставит свой пак, ASK — пак [STOP] (окно «Нет подходящего пака»), SKIP — запрет двери."""
    if rule.get("action") == "skip":
        return SKIP
    return ASK if list(rule.get("team") or []) == STOP_PACK else PACK


def tag(rule):
    """Значок типа (ваш ответ 4.2): "skip", "enemies", "heal", "hp", "energy" или None (условия нет)."""
    cond = condition(rule)
    if action(rule) == SKIP:
        return "skip"
    if cond.get("enemies_contain"):
        return "enemies"
    if cond.get("titan_hp_below"):
        return "heal" if action(rule) == PACK else "hp"
    if cond.get("titan_energy_below"):
        return "energy"
    return None


def condition(rule):
    cond = rule.get("condition")
    return cond if isinstance(cond, dict) else {}


def titan_name(lang, titan):
    key = f"titan_{titan}"
    name = get_text(lang, key)
    return titan if name == key else name


def names(lang, titans, sep=", "):
    return sep.join(titan_name(lang, t) for t in titans)


def condition_parts(cond, lang, skip=()):
    """Условие словами на языке окна: ["Араджи: ХП ниже 50%", "Враги в комнате: Молох, Вулкан", ...].
    skip — каких ключей условия не писать."""
    parts = []
    if cond.get("enemies_contain") and "enemies_contain" not in skip:
        parts.append(get_text(lang, "ri_cond_enemies").format(names=names(lang, cond["enemies_contain"])))
    for key, text_key in (("titan_hp_below", "ri_cond_hp"), ("titan_energy_below", "ri_cond_energy")):
        values = cond.get(key)
        if isinstance(values, dict) and key not in skip:
            parts += [get_text(lang, text_key).format(titan=titan_name(lang, t), n=v) for t, v in values.items()]
    if cond.get("require_fought") and "require_fought" not in skip:
        parts.append(get_text(lang, "ri_cond_fought").format(names=names(lang, cond["require_fought"])))
    return parts


def condition_text(rule, lang):
    return " · ".join(condition_parts(condition(rule), lang)) or get_text(lang, "ri_cond_none")


def bot_named(rule):
    """Имя правила — то, что бот дал ему сам (вы не переименовали): "learned", "golden" или None."""
    name = str(rule.get("name") or "")
    if not rule.get("source"):
        return None
    if name.startswith(GOLDEN_PREFIX):
        return "golden"
    if name.startswith(LEARNED_PREFIX):
        return "learned"
    return None


def title_and_sub(rule, lang):
    """Название и серая строка под ним (ваш ответ 4.3): правило, названное ботом, — «Авто: Ангус + Сильва в комнате»
    и «Запомнил бот после отката · Араджи: ХП ниже 50%»; ваше — имя из файла и условие словами.
    Пустое имя — условие словами (так его назовёт и окно «Новое правило»)."""
    cond = condition(rule)
    kind = bot_named(rule)
    if kind:
        enemies = cond.get("enemies_contain") or []
        title = get_text(lang, "ri_name_golden" if kind == "golden" else "ri_name_auto").format(
            names=names(lang, enemies, " + "))
        if kind == "golden":
            by = "ri_by_golden"
        else:
            by = "ri_by_auto" if rule.get("source") == "auto" else "ri_by_you"
        sub = " · ".join([get_text(lang, by)] + condition_parts(cond, lang, skip=("enemies_contain",)))
        return title, sub
    text = condition_text(rule, lang)
    return str(rule.get("name") or "").strip() or text, text


def summary(rule, lang):
    """Всё, что видно в строке списка."""
    title, sub = title_and_sub(rule, lang)
    team = [str(t) for t in rule.get("team") or []] if action(rule) == PACK else []
    return {"title": title, "sub": sub, "tag": tag(rule), "action": action(rule), "team": team,
            "enabled": enabled(rule)}


def visible(rules, room_filter):
    """Строки списка по порядку: [(стихия, номер в стихии, правило)]. «Все» — стихии подряд: Земля, Вода, Огонь,
    Смешанная (бот проверяет правила по порядку только внутри своей стихии)."""
    rooms = ROOMS if room_filter is None else (room_filter,)
    return [(room, i, rule) for room in rooms for i, rule in enumerate(rules.get(room, []))]


# ── Правки списка (в форме, без записи) ─────────────────────────────────────
def move(rules, room, index, delta):
    """Стрелка ↑ (delta -1) или ↓ (+1): поменять местами с соседом в той же стихии. True — поменялось."""
    items = rules[room]
    other = index + delta
    if not (0 <= index < len(items) and 0 <= other < len(items)):
        return False
    items[index], items[other] = items[other], items[index]
    return True


def set_enabled(rule, on):
    """Тумблер: выключено — enabled: false, включено — пометки нет (правила без неё бот берёт)."""
    if on:
        rule.pop("enabled", None)
    else:
        rule["enabled"] = False


def remove(rules, room, index):
    """Удалить правило: возвращает (стихия, место, правило) — для «Вернуть»."""
    return room, index, rules[room].pop(index)


def put_back(rules, removed):
    """«Вернуть» удалённые правила на их места. removed — из одного remove или clear: [(стихия, место, правило)],
    места — в списке до удаления, по возрастанию (так и вставляем)."""
    for room, index, rule in removed:
        items = rules[room]
        items.insert(min(index, len(items)), rule)


def clear(rules, room_filter):
    """«Очистить все правила» — то, что видно (ваш ответ): выбрана стихия — только её правила, «Все» — все.
    Возвращает удалённые (для «Вернуть»)."""
    removed = []
    for room in ROOMS if room_filter is None else (room_filter,):
        removed += [(room, i, rule) for i, rule in enumerate(rules[room])]
        rules[room] = []
    return removed


def locate(rules, room, rule):
    """Где сейчас это правило в стихии (сначала то же самое, потом такое же), или None — его уже нет."""
    items = rules.get(room, [])
    found = next((i for i, r in enumerate(items) if r is rule), None)
    return found if found is not None else next((i for i, r in enumerate(items) if r == rule), None)


def put(rules, room, rule, old_room=None, index=None):
    """Правило из окна «Новое правило». Новое — на 1-е место стихии (как в старом окне: выше — раньше проверяется).
    Изменённое — на своё место; стихию поменяли — переезжает на 1-е место новой стихии. Возвращает новое место."""
    if old_room is not None and index is not None and 0 <= index < len(rules[old_room]):
        if old_room == room:
            rules[room][index] = rule
            return index
        rules[old_room].pop(index)
    rules[room].insert(0, rule)
    return 0


# ── Окно «Новое правило» ────────────────────────────────────────────────────
def editor_values(rule=None, room="mix"):
    """Что показать в окне «Новое правило»: для нового правила — значения по умолчанию (как в старом окне:
    по ХП, 35%), для изменения — из правила. extra — части условия, которых окно не показывает (бот запомнил правило
    «против этих врагов, при Араджи < 50% ХП»: видно «По врагам», а ХП Араджи сохранится как есть)."""
    allowed = theme.room_titans(room)
    values = {"room": room, "name": "", "trigger": "hp", "titan": allowed[0], "value": DEFAULT_VALUES["hp"],
              "enemies": [], "action": PACK, "team": [], "fought": [], "extra": {}}
    if rule is None:
        return values
    cond = condition(rule)
    trigger = next((t for t in ("enemies", "hp", "energy")
                    if isinstance(cond.get(TRIGGER_KEYS[t]), list if t == "enemies" else dict)
                    and cond[TRIGGER_KEYS[t]]), "hp")
    values.update(name=str(rule.get("name") or ""), trigger=trigger, action=action(rule),
                  team=[str(t) for t in rule.get("team") or []] if action(rule) == PACK else [],
                  fought=[str(t) for t in cond.get("require_fought") or []])
    if trigger == "enemies":
        values["enemies"] = [str(e) for e in cond["enemies_contain"]]
    elif cond.get(TRIGGER_KEYS[trigger]):
        titan, value = next(iter(cond[TRIGGER_KEYS[trigger]].items()))
        values.update(titan=str(titan), value=value)
    values["extra"] = {k: copy.deepcopy(v) for k, v in cond.items()
                       if k not in (TRIGGER_KEYS[trigger], "require_fought")}
    return values


def rule_from_editor(values, original=None, lang="RU"):
    """Правило из окна «Новое правило». original — правило, которое меняли: его скрытые поля и части условия,
    которых окно не показывает, остаются (ошибка 4.4). Пустое название — условие словами на языке окна (ваш ответ)."""
    rule = copy.deepcopy(original) if original else {}
    trigger = values["trigger"]
    cond = {k: copy.deepcopy(v) for k, v in (values.get("extra") or {}).items()}
    if trigger == "enemies":
        cond[TRIGGER_KEYS[trigger]] = list(values["enemies"])
    else:
        cond[TRIGGER_KEYS[trigger]] = {values["titan"]: int(values["value"])}
    if values.get("fought"):
        cond["require_fought"] = list(values["fought"])
    rule["condition"] = _ordered(cond)
    rule.pop("action", None)
    if values["action"] == SKIP:
        rule["team"] = []
        rule["action"] = "skip"
    elif values["action"] == ASK:
        rule["team"] = list(STOP_PACK)
    else:
        rule["team"] = list(values["team"])
    name = str(values.get("name") or "").strip()
    rule["name"] = name or condition_text({"condition": cond}, lang)
    return _ordered_rule(rule)


def _ordered(cond):
    """Ключи условия в привычном порядке файла (бот на порядок не смотрит)."""
    order = ("titan_hp_below", "titan_energy_below", "enemies_contain", "require_fought")
    return {**{k: cond[k] for k in order if k in cond}, **{k: v for k, v in cond.items() if k not in order}}


def _ordered_rule(rule):
    order = ("name", "condition", "team", "action")
    return {**{k: rule[k] for k in order if k in rule}, **{k: v for k, v in rule.items() if k not in order}}


def editor_problem(values):
    """Почему «Сохранить правило» недоступна: ключ надписи i18n или None — можно сохранять."""
    if values["trigger"] == "enemies" and not values["enemies"]:
        return "re_need_enemy"
    if values["trigger"] != "enemies" and values.get("value") is None:
        return "re_need_number"
    if values["action"] == SKIP and values["trigger"] == "enemies":
        return "re_skip_enemies"
    if values["action"] == PACK and not MIN_PACK <= len(values["team"]) <= MAX_PACK:
        return "re_need_pack"
    return None


def fit_room(values, room):
    """Стихию в окне поменяли: титан условия и пак — только из тех, кого можно в эту комнату (theme.room_titans)."""
    allowed = theme.room_titans(room)
    values["room"] = room
    if values["titan"] not in allowed:
        values["titan"] = allowed[0]
    team = [t for t in values["team"] if t in allowed]
    values["team"] = team if len(team) >= MIN_PACK else []
    return values


# ── Запись ──────────────────────────────────────────────────────────────────
def changed_rooms(saved, rules):
    return [room for room in ROOMS if rules.get(room, []) != saved.get(room, [])]


def save_rules(saved, rules, read=rules_store.read_rules):
    """Записать правила стихий, где они поменялись. saved — какими окно их прочитало, rules — форма.
    Файл перечитывается: правила, которые бот добавил за это время, встают наверх, убранные ботом не возвращаются.
    Возвращает (записанные стихии, битые стихии (не тронуты), {стихия: правила, добавленные ботом}).
    После записи saved и rules — то, что теперь в файлах."""
    written, broken, added_by_bot = [], [], {}
    for room in changed_rooms(saved, rules):
        state, data = read(room)
        if state == BROKEN:
            broken.append(room)
            continue
        if state == MISSING:
            data = {}
        theirs = _rule_list(data)
        mine = rules[room]
        if theirs != saved.get(room, []):
            added = [r for r in theirs if r not in saved.get(room, [])]
            gone = [r for r in saved.get(room, []) if r not in theirs]
            mine = added + [r for r in mine if r not in gone]
            if added:
                added_by_bot[room] = added
        data["rules"] = copy.deepcopy(mine)
        write_rules_file(room, data)
        rules[room] = copy.deepcopy(mine)
        saved[room] = copy.deepcopy(mine)
        written.append(room)
    return written, broken, added_by_bot


def write_rules_file(room, data):
    """Как бот (rules_engine._save_rule_first): через .tmp и замену — бот не прочитает половину файла."""
    path = data_paths.rules_path(room)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    os.replace(tmp, path)
