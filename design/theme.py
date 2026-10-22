"""Дизайн-токены интерфейса RPA BOT (Hero Wars: Knowledge Engine Bot v1.6.1).

Источник правды — макеты в design/mockups и картинки в design/screenshots.
Tkinter/CustomTkinter не умеет полупрозрачные цвета (rgba), поэтому все
«подкрашенные» фоны здесь уже смешаны с фоном и записаны обычным hex.
Если нужен новый оттенок — используй blend(), а не rgba.
"""


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
}

# ── Стихии ───────────────────────────────────────────────────────────────────
# color — рамки аватарок, иконки, заголовки колонок
# text  — если стихия пишется ТЕКСТОМ мелким шрифтом (у «Смешанной» основной цвет темноват)
# tint  — фон аватарки/бейджа (16% цвета поверх карточки #1B1D26)
ELEMENTS = {
    "earth": {"name": "Земля", "color": "#52B788", "text": "#52B788", "icon": "leaf"},
    "water": {"name": "Вода", "color": "#00B4D8", "text": "#00B4D8", "icon": "droplet"},
    "fire": {"name": "Огонь", "color": "#F77F00", "text": "#F77F00", "icon": "flame"},
    "light": {"name": "Свет", "color": "#E9C46A", "text": "#E9C46A", "icon": "sun"},
    "dark": {"name": "Тьма", "color": "#A3A8C3", "text": "#A3A8C3", "icon": "moon"},
    # «Смешанная» — это тип КОМНАТЫ, а не стихия титана
    "mixed": {"name": "Смешанная", "color": "#9D4EDD", "text": "#BF8CF0", "icon": "swords"},
}
for _el in ELEMENTS.values():
    _el["tint"] = blend(_el["color"], COLORS["bg_surface"], 0.16)

# Стихии титанов (как в окне «Собери состав»)
TITANS = {
    "earth": ["Ангус", "Авалон", "Эдем", "Сильва", "Вердок", "Паллант"],
    "water": ["Гиперион", "Сигурд", "Тидус", "Нова", "Маири", "Орм"],
    "fire": ["Араджи", "Игнис", "Ашерон", "Вулкан", "Молох", "Алекто"],
    "light": ["Ригель", "Ияри", "Люмира", "Солярис", "Амон"],
    "dark": ["Мор", "Тенебрис", "Брустар", "Умбра", "Керос"],
}
TITAN_ELEMENT = {name: el for el, names in TITANS.items() for name in names}

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

# ── Шрифты ───────────────────────────────────────────────────────────────────
# Roboto идёт вместе с CustomTkinter. Моноширинный: Consolas (есть в Windows).
FONT_FAMILY = "Roboto"
MONO_FAMILY = "Consolas"
FONTS = {
    "page_title": (FONT_FAMILY, 18, "bold"),   # заголовок в шапке
    "section": (FONT_FAMILY, 15, "bold"),      # заголовок карточки/раздела
    "card_title": (FONT_FAMILY, 14, "bold"),
    "body": (FONT_FAMILY, 14),
    "label": (FONT_FAMILY, 12),                # подписи полей, подсказки
    "small": (FONT_FAMILY, 11),
    "cta": (FONT_FAMILY, 19, "bold"),          # «Начать фарм»
    "kpi": (MONO_FAMILY, 26),                  # большие цифры
    "mono": (MONO_FAMILY, 12),                 # журнал, числа в полях
}

# ── Размеры ──────────────────────────────────────────────────────────────────
SIZES = {
    "window": (1100, 720),        # окно не растягивается; не влезло — прокрутка внутри
    "rail_width": 64,             # полоска навигации с иконками
    "rail_button": 44,            # кнопка в полоске (иконка 20)
    "header_height": 56,
    "footer_height": 64,          # футер «Сохранить настройки» в мастере правил
    "content_padding": 24,
    "gap_xs": 6, "gap_s": 8, "gap_m": 12, "gap_l": 16, "gap_xl": 24,
    "radius_card": 10,
    "radius_control": 6,
    "radius_chip": 15,            # фильтры-«таблетки» высотой 30
    "control_height": 36,         # поля ввода, выпадающие списки, обычные кнопки
    "button_height_footer": 38,
    "cta_height": 56,
    "chip_height": 30,
    "avatar": 36,                 # мини-аватар титана, рамка 2px цветом стихии
    "avatar_small": 26,
    "icon": 18,                   # иконка в кнопке
    "icon_nav": 20,
    "hud_height": 60,             # док-плеер под окном scrcpy
}
