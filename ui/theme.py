"""Дизайн-токены нового интерфейса (задача 15): цвета, шрифты, размеры, стихии и титаны.

Источник — design/theme.py и макеты в design/mockups. Отличия от design/theme.py:
- титаны записаны внутренними именами (как в assets/ и i18n.py: "angus", "araji"), а не русскими;
- смешанная комната — "mix" (как в bot_data/rules/mix.yml), "mixed" оставлен как второе имя;
- названия стихий берутся из i18n.py (elem_earth, ...), русских строк здесь нет;
- добавлены цвета, которые в design/README.md записаны прямо в тексте (кнопка «Удалить все», поле с ошибкой).

Tkinter не умеет полупрозрачные цвета (rgba), поэтому все «подкрашенные» фоны уже смешаны с фоном.
Новый оттенок — через blend(), а не hex руками в виджете.
Модуль без Tk: его можно импортировать в тестах в облаке.
"""
import unicodedata
from pathlib import Path


def blend(fg: str, bg: str, alpha: float) -> str:
    """Смешать цвет fg поверх bg с прозрачностью alpha (0..1). Возвращает #RRGGBB."""
    f = [int(fg[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(bg[i:i + 2], 16) for i in (1, 3, 5)]
    mixed = [round(bb + (ff - bb) * alpha) for ff, bb in zip(f, b)]
    return "#{:02X}{:02X}{:02X}".format(*mixed)


# ── Базовые цвета ────────────────────────────────────────────────────────────
COLORS = {
    # фоны (от самого тёмного к светлому)
    "bg_primary": "#12131A",      # фон окна, сайдбар, консоль
    "bg_surface": "#1B1D26",      # карточки, панели, шапка списков, футер
    "bg_elevated": "#242734",     # поля ввода, второстепенные кнопки, строки списков
    # рамки
    "border": "#2E3244",          # обычная рамка 1px
    "border_strong": "#3A3F55",   # контурные кнопки, трек выключенного тумблера
    "border_focus": "#4A5068",    # выбранный фильтр, пунктир «добавить»
    # текст
    "text": "#E8EAF0",            # основной
    "text_secondary": "#A9AFC2",  # подписи полей, неактивные пункты
    "text_muted": "#8A90A6",      # подсказки, время в логе (не светлее!)
    # зелёный — ТОЛЬКО старт и сохранение
    "green": "#3B8E26",           # большая кнопка «Начать фарм» (текст 19px bold), столбики графика
    "green_button": "#2F7A1E",    # кнопки «Сохранить …» с мелким текстом (контраст белого 5.3:1)
    "green_hover": "#4AA52F",
    # синий — выбранное и активное
    "blue": "#2979FF",            # тумблер ВКЛ, прогресс-бар титанита, рамка выделенного
    "blue_button": "#1F6FEB",     # синие кнопки с текстом и выбранный сегмент (контраст 4.6:1)
    "blue_text": "#6EA8FF",       # синие ссылки и иконки на тёмном фоне
    # статусы
    "success": "#4ADE80",
    "warning": "#FACC15",
    "danger": "#EF4444",          # рамки, иконки, точки
    "danger_text": "#F87171",     # красный ТЕКСТ (на #EF4444 мелкий текст плохо читается)
    "danger_button": "#DC2626",   # опасная кнопка в диалоге («Удалить все»), текст белый
    "gold": "#F5C542",            # «золотые правила», блок доната
    "sos_bg": "#302129",          # фон док-плеера в состоянии SOS
    "white": "#FFFFFF",
}

# ── Подкрашенные фоны (rgba из макетов, уже смешанные) ───────────────────────
TINTS = {
    # активный пункт сайдбара: rgba(41,121,255,.16) + рамка rgba(41,121,255,.45) на #12131A
    "nav_active_bg": blend(COLORS["blue"], COLORS["bg_primary"], 0.16),
    "nav_active_border": blend(COLORS["blue"], COLORS["bg_primary"], 0.45),
    # выделенная строка/карточка на поверхности
    "blue_on_surface": blend(COLORS["blue"], COLORS["bg_surface"], 0.16),
    # выбранный титан в пикере / выбранный враг
    "green_on_surface": blend(COLORS["green"], COLORS["bg_surface"], 0.14),
    # плашка-подсказка «Как это работает» (вкладка Авто-тактика)
    "info_banner_bg": "#182033",
    "info_banner_border": blend(COLORS["blue"], COLORS["bg_primary"], 0.35),
    # бейджи статусов на #242734
    "success_badge_bg": blend(COLORS["success"], COLORS["bg_elevated"], 0.14),
    "warning_badge_bg": blend(COLORS["warning"], COLORS["bg_elevated"], 0.14),
    "danger_badge_bg": blend(COLORS["danger"], COLORS["bg_elevated"], 0.18),
    # подложка иконки в диалоге подтверждения (экран 8): rgba(239,68,68,.16) и rgba(250,204,21,.14) на #1B1D26
    "danger_on_surface": blend(COLORS["danger"], COLORS["bg_surface"], 0.16),
    "warning_on_surface": blend(COLORS["warning"], COLORS["bg_surface"], 0.14),
    "blue_icon_bg": blend(COLORS["blue"], COLORS["bg_surface"], 0.16),
    "gold_on_surface": blend(COLORS["gold"], COLORS["bg_surface"], 0.16),
    # поле ввода с ошибкой и недоступное (экран 8)
    "field_error_bg": "#2A1F27",
    "field_disabled_bg": "#1F2129",
    # наведение на кнопки (в макетах не нарисовано: чуть светлее фона кнопки)
    "hover_elevated": blend(COLORS["white"], COLORS["bg_elevated"], 0.06),
    "hover_surface": blend(COLORS["white"], COLORS["bg_surface"], 0.05),
    "hover_primary": blend(COLORS["white"], COLORS["bg_primary"], 0.05),
    "hover_blue": blend(COLORS["white"], COLORS["blue_button"], 0.12),
    "hover_green_button": blend(COLORS["white"], COLORS["green_button"], 0.10),
    "hover_danger_button": blend(COLORS["white"], COLORS["danger_button"], 0.10),
}

# ── Стихии ───────────────────────────────────────────────────────────────────
# color — рамки аватарок, иконки, заголовки колонок
# text  — если стихия пишется ТЕКСТОМ мелким шрифтом (у «Смешанной» основной цвет темноват)
# tint  — фон аватарки/бейджа (16% цвета поверх карточки #1B1D26)
# Название стихии — i18n.py, ключ elem_<стихия> (без значка: ui.theme.plain_text)
ELEMENTS = {
    "earth": {"color": "#52B788", "text": "#52B788", "icon": "leaf"},
    "water": {"color": "#00B4D8", "text": "#00B4D8", "icon": "droplet"},
    "fire": {"color": "#F77F00", "text": "#F77F00", "icon": "flame"},
    "light": {"color": "#E9C46A", "text": "#E9C46A", "icon": "sun"},
    "dark": {"color": "#A3A8C3", "text": "#A3A8C3", "icon": "moon"},
    # «Смешанная» — это тип КОМНАТЫ, а не стихия титана
    "mix": {"color": "#9D4EDD", "text": "#BF8CF0", "icon": "swords"},
}
for _el in ELEMENTS.values():
    _el["tint"] = blend(_el["color"], COLORS["bg_surface"], 0.16)
ELEMENTS["mixed"] = ELEMENTS["mix"]

# Титан без стихии (новый, которого ещё нет в TITANS): серая рамка
UNKNOWN_ELEMENT = {"color": COLORS["border_strong"], "text": COLORS["text_secondary"], "icon": "user",
                   "tint": COLORS["bg_elevated"]}

# Стихии титанов (как в окне «Собери состав»). Имена — внутренние, как картинки в assets/ и ключи titan_<имя> в i18n.py
TITANS = {
    "earth": ["angus", "avalon", "eden", "silva", "verdok", "pallant"],
    "water": ["hyperion", "sigurd", "tidus", "nova", "mairi", "orm"],
    "fire": ["araji", "ignis", "acheron", "vulcan", "moloch", "alecto"],
    "light": ["rigel", "iyari", "lumira", "solaris", "amon"],
    "dark": ["mor", "tenebris", "brustar", "umbra", "keros"],
}
TITAN_ELEMENT = {name: el for el, names in TITANS.items() for name in names}

# Эларитовые титаны (ответ пользователя 22.10.2026, шаг 3). Паллант, Орм и Алекто — эларитовые, но встают и в комнату
# своей стихии (поэтому они в TITANS выше). Метида — только эларит: её ставят лишь в смешанную комнату.
# Цвет — как у смешанной комнаты (другой комнаты у неё нет), значок — кристалл. Название — i18n.py, elem_elarite
ELARITE_ONLY = ["metida"]
ELEMENTS["elarite"] = {**ELEMENTS["mix"], "icon": "gem"}
TITAN_ELEMENT.update({name: "elarite" for name in ELARITE_ONLY})


def room_titans(room):
    """Кого можно поставить в комнату: в комнату земли, воды и огня — только титанов этой стихии,
    в смешанную — всех, и Метиду. Комната неизвестна — всех."""
    if room in ("earth", "water", "fire"):
        return list(TITANS[room])
    return [name for names in TITANS.values() for name in names] + ELARITE_ONLY


# Цвета тегов журнала
LOG_TAGS = {
    "СИСТЕМА": "#5BC0EB",
    "GUI": COLORS["text_muted"],
    "БОЙ": COLORS["success"],
    "ПЕРЕХВАТ": COLORS["warning"],
    "ОШИБКА": COLORS["danger_text"],
    "SOS": COLORS["danger_text"],
    "ML": "#BF8CF0",
}

# Журнал нового окна (шаг 3): бот пишет свои теги ([ТАКТИКА], [НАВИГАЦИЯ] ...), поэтому тег красится цветом своей
# «таблетки» (ui/log_lines.py): бои — зелёным, правила — жёлтым (как [ПЕРЕХВАТ] в макете), система — голубым, ошибки — красным.
# Строки самого окна ([GUI]) — серым, время в начале строки — серым
LOG_CATEGORY_COLORS = {
    "fights": LOG_TAGS["БОЙ"],
    "rules": LOG_TAGS["ПЕРЕХВАТ"],
    "system": LOG_TAGS["СИСТЕМА"],
    "errors": LOG_TAGS["ОШИБКА"],
    "gui": LOG_TAGS["GUI"],
}

# «Правила и перехваты» (шаг 5в, макет 03c): значки в строке правила — (цвет текста, подложка на фоне строки bg_elevated).
# Тип правила (ваш ответ 4.2): ЛЕЧЕНИЕ, СКИП, ХП, ВРАГИ, ЭНЕРГИЯ; действие без пака: «Спросить вас», «Пропустить комнату»
_SKIP_TEXT = "#C3C8D6"
RULE_TAG_COLORS = {
    "heal": (COLORS["success"], blend(COLORS["success"], COLORS["bg_elevated"], 0.14)),
    "skip": (_SKIP_TEXT, blend(COLORS["text_secondary"], COLORS["bg_elevated"], 0.14)),
    "hp": (COLORS["warning"], blend(COLORS["warning"], COLORS["bg_elevated"], 0.14)),
    "enemies": (COLORS["danger_text"], blend(COLORS["danger"], COLORS["bg_elevated"], 0.16)),
    "energy": (COLORS["blue_text"], blend(COLORS["blue"], COLORS["bg_elevated"], 0.16)),
}
RULE_ACTION_COLORS = {
    "ask": RULE_TAG_COLORS["hp"],
    "skip": RULE_TAG_COLORS["skip"],
}
RULE_DIM = 0.45   # выключенное правило бледное (макет: opacity 0.45), но не удалено


def rule_room_badge(room):
    """Значок стихии в строке правила: (цвет текста, подложка на фоне строки)."""
    style = ELEMENTS.get(room, UNKNOWN_ELEMENT)
    return style["text"], blend(style["color"], COLORS["bg_elevated"], 0.18 if room == "mix" else 0.16)


# Иконки ui/icons, которых нет в design/icons: нарисованы по контуру Lucide тем же размером (ui/icons/__init__.py)
EXTRA_ICONS = {"minimize-2"}

# Цель сессии на главной: значок и его цвет (кристалл титанита — фиолетовый, как в макете 01_main)
GOAL_ICONS = {
    "titanite": ("gem", "#9D4EDD"),
    "rooms": ("door-open", COLORS["blue_text"]),
    "floors": ("layers", COLORS["blue_text"]),
    "time": ("gauge", COLORS["blue_text"]),
}

# ── Шрифты ───────────────────────────────────────────────────────────────────
# Roboto идёт вместе с CustomTkinter. Моноширинный: Consolas (есть в Windows).
# Размер — в пикселях, как в макетах; CustomTkinter сам увеличивает его под масштаб Windows.
FONT_FAMILY = "Roboto"
MONO_FAMILY = "Consolas"
FONTS = {
    "page_title": (FONT_FAMILY, 18, "bold"),   # заголовок в шапке
    "section": (FONT_FAMILY, 15, "bold"),      # заголовок карточки/раздела
    "card_title": (FONT_FAMILY, 14, "bold"),
    "dialog_title": (FONT_FAMILY, 16, "bold"),
    "body": (FONT_FAMILY, 14),
    "body_bold": (FONT_FAMILY, 14, "bold"),
    "button": (FONT_FAMILY, 13),
    "button_bold": (FONT_FAMILY, 13, "bold"),
    "text": (FONT_FAMILY, 13),                 # текст диалогов и уведомлений
    "label": (FONT_FAMILY, 12),                # подписи полей, подсказки
    "label_bold": (FONT_FAMILY, 12, "bold"),
    "small": (FONT_FAMILY, 11),
    "small_bold": (FONT_FAMILY, 11, "bold"),   # «ОБЫЧНОЕ», «РАЗДЕЛ 1»
    "cta": (FONT_FAMILY, 19, "bold"),          # «Начать фарм»
    "kpi": (MONO_FAMILY, 26),                  # большие цифры
    "mono": (MONO_FAMILY, 12),                 # журнал
    "mono_field": (MONO_FAMILY, 14),           # числа в полях ввода
    "version": (MONO_FAMILY, 10),              # «v1.6.1» под логотипом в полоске
}

# ── Размеры ──────────────────────────────────────────────────────────────────
SIZES = {
    "window": (1100, 720),        # размер по умолчанию, если экран позволяет
    "window_min": (1000, 620),    # меньше не даём; не влезло — прокрутка внутри
    "rail_width": 64,             # полоска навигации с иконками
    "rail_button": 44,            # кнопка в полоске (иконка 20)
    "header_height": 56,
    "header_button": 34,          # иконки-кнопки в шапке
    "footer_height": 64,          # футер «Сохранить настройки» в мастере правил
    "content_padding": 24,
    "gap_xs": 6, "gap_s": 8, "gap_m": 12, "gap_l": 16, "gap_xl": 24,
    "radius_card": 10,
    "radius_dialog": 12,
    "radius_control": 6,
    "radius_chip": 15,            # фильтры-«таблетки» высотой 30
    "control_height": 36,         # поля ввода, выпадающие списки, обычные кнопки
    "button_height_footer": 38,
    "cta_height": 56,
    "chip_height": 30,
    "avatar": 36,                 # мини-аватар титана, рамка 2px цветом стихии
    "avatar_small": 26,
    "avatar_border": 2,
    "icon": 18,                   # иконка в кнопке
    "icon_nav": 20,
    "hud_height": 60,             # док-плеер под окном scrcpy (макет)
    "hud_height_tall": 100,       # док-плеер на деле: выше макета, 4 строки (ваш ответ после проверки шага 4)
    "toast_height": 44,
    "toast_ms": 4000,             # уведомление видно 4 с
    "tooltip_delay_ms": 400,
}

# ── Картинки титанов для оболочки ────────────────────────────────────────────
# Только для окна программы: бот их не читает (титанов для слотов он ищет в корне assets/, а не в папках).
# Имя файла — внутреннее имя титана: assets/icons/angus.png. Нет картинки — в квадрате две буквы имени.
TITAN_ICON_DIRS = (
    Path("assets") / "icons",                                       # запуск из папки проекта (start.bat)
    Path(__file__).resolve().parent.parent / "assets" / "icons",    # рядом с кодом (и в собранном .exe)
)
TITAN_ICON_EXTS = (".png", ".webp", ".jpg")


def element_of(titan):
    """Стихия титана ("earth", ...) или None, если титана нет в TITANS (новый титан)."""
    return TITAN_ELEMENT.get(titan)


def element_style(element):
    """Цвета стихии (color, text, tint, icon). Неизвестная стихия — серый стиль."""
    return ELEMENTS.get(element, UNKNOWN_ELEMENT)


def titan_icon_path(titan, dirs=TITAN_ICON_DIRS):
    """Путь к картинке титана для оболочки или None, если её ещё нет."""
    for folder in dirs:
        for ext in TITAN_ICON_EXTS:
            path = Path(folder) / f"{titan}{ext}"
            if path.is_file():
                return path
    return None


def plain_text(text):
    """Убрать значки-эмодзи в начале надписи из i18n.py: «🌿 Земля» → «Земля», «⚔️ Смешанная» → «Смешанная».
    В новом интерфейсе эмодзи нет (Tkinter в Windows рисует их плохо), а старые надписи с ними ещё нужны старому окну.
    Конец надписи не трогаем: там бывают нужные стрелки («Открыть →»)."""
    start = 0
    while start < len(text) and (unicodedata.category(text[start])[0] in "SCZ" or text[start] in "️‍"):
        start += 1
    return text[start:].rstrip()


def initials(name):
    """Две буквы имени для квадрата титана, пока нет картинки: «Араджи» → «Ар», «amon» → «Am»."""
    letters = [ch for ch in plain_text(name) if ch.isalnum()]
    if not letters:
        return "?"
    return (letters[0].upper() + "".join(letters[1:2]).lower())
