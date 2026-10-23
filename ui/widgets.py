"""Общие виджеты нового интерфейса (задача 15, шаг 1): то, из чего собираются все экраны.

Card — карточка; Button — кнопка нужного вида (второстепенная, синяя, сохранить, «Начать фарм», опасная);
IconButton — квадратная кнопка с иконкой (шапка, сайдбар, мини-бар); Tooltip — подсказка при наведении;
TitanAvatar — квадрат титана цветом стихии (TitanTile — то же одной картинкой, для длинных списков);
Chip — фильтр-«таблетка»; Field — поле ввода с подписью и состояниями;
Switch — тумблер, Dropdown — выпадающий список (шаг 5а, мастер правил);
DialogBody / ConfirmDialog — подтверждение опасного действия; ToastBody / Toast — короткое уведомление.

Цвета, шрифты и размеры — только из ui/theme.py, иконки — ui/icons. Надписи передаёт тот, кто создаёт виджет (из i18n.py).
Виджеты трогаем только из главного потока Tk.

Чтобы окно в Windows не зависало (на этом уже обжигались):
- обработчики наведения (<Enter>/<Leave>) меняют только цвета и только если вид правда поменялся. Шрифт, текст и картинку
  в них не трогаем: CustomTkinter при этом убирает и заново ставит часть виджета под мышкой, Windows снова шлёт
  «мышь вошла» — и окно крутится в этом круге;
- никаких вложенных ожиданий (wait_visibility, wait_window): окно подтверждения ждёт показа через after;
- окошки без рамки (подсказка, уведомление) — обычные окна Tk, без особых режимов Windows (прозрачный цвет).
"""
import tkinter as tk
from functools import lru_cache

import customtkinter as ctk
from customtkinter.windows.widgets.core_widget_classes import DropdownMenu
from PIL import Image, ImageDraw, ImageTk

from i18n import get_text
from ui import theme
from ui.icons import dot, icon

C = theme.COLORS
T = theme.TINTS
F = theme.FONTS
S = theme.SIZES

# Уголки окошек без рамки: в цвет фона окна программы, поэтому скругление карточки внутри не видно как «квадрат»
_CORNER_COLOR = C["bg_primary"]


def _frameless_window(root, inactive=False):
    """Окошко без рамки поверх окна программы (не поверх всех окон: иначе оно может попасть на снимок игры).
    inactive — окошко не берёт фокус и не принимает нажатия (подсказка): окно программы не теряет активность."""
    top = tk.Toplevel(root)
    top.withdraw()
    top.overrideredirect(True)
    top.configure(bg=_CORNER_COLOR)
    top.transient(root)
    if inactive:
        try:
            top.wm_attributes("-disabled", True)  # есть только в Windows
        except tk.TclError:
            pass
    return top


SHOW_DELAY_MS = 50       # окно показывается не сразу: сначала CustomTkinter перекрашивает заголовок (см. present_window)


def present_window(window, place, hidden=lambda: False, on_shown=None):
    """Показать готовое окно (CTkToplevel): place() ставит размер и место, потом окно появляется сверху.

    В Windows CustomTkinter после создания окна и после resizable() перекрашивает заголовок в тёмный: прячет окно
    и через миг возвращает в то состояние, какое было ДО перекраски. Показали окно в этот миг — оно снова пропадает
    (шаг 3: окно «Собери состав» появлялось и сразу исчезало), а показанное раньше моргает и дорисовывается на глазах.
    Поэтому ждём, пока перекраска кончится (её флаг в CustomTkinter), и только потом показываем; через 0,3 с проверяем,
    что окно правда на экране. hidden() — окно закрыли или спрятали нарочно: тогда не показываем."""
    def attempt(left):
        if hidden():
            return
        try:
            if getattr(window, "_windows_set_titlebar_color_called", False) and left > 0:
                window.after(20, attempt, left - 1)
                return
            in_mini = _detach_from_hidden_owner(window)
            place()
            window.deiconify()
            window.lift()
            if in_mini:
                bring_to_front(window)
            window.focus_set()
            window.after(300, check, 3)
        except tk.TclError:
            return
        if on_shown:
            on_shown()

    def check(left):
        if hidden():
            return
        try:
            if window.state() == "withdrawn" and left > 0:
                window.deiconify()
                window.lift()
                window.after(300, check, left - 1)
        except tk.TclError:
            pass

    try:
        window.after(SHOW_DELAY_MS, attempt, 100)
    except tk.TclError:
        pass


def _app_of(widget):
    """Окно программы (ui/app.py: App), к которому относится виджет или окно, или None."""
    while widget is not None and not hasattr(widget, "mini"):
        widget = getattr(widget, "master", None)
    return widget


def _detach_from_hidden_owner(window):
    """Окно программы свёрнуто в мини-бар (шаг 4): окно, привязанное к нему (transient), Windows прячет вместе с ним.
    Тогда окно (SOS, «Собери состав») отвязывается и показывается само по себе над игрой (ваш ответ 22.10.2026).
    Возвращает True, если окно программы сейчас в мини-баре."""
    app = _app_of(window)
    if app is None or not app.mini:
        return False
    if window.master is app:
        try:
            window.wm_transient("")
        except tk.TclError:
            pass
    return True


def bring_to_front(window, hold_ms=400):
    """Поднять окно над всеми (над окном игры тоже) на миг и отпустить: окно SOS при свёрнутом окне программы
    иначе могло бы открыться под игрой. Поверх всех оно не остаётся."""
    try:
        window.lift()
        window.attributes("-topmost", True)
        window.after(hold_ms, lambda: window.winfo_exists() and window.attributes("-topmost", False))
    except tk.TclError:
        pass


def show_over_game(window):
    """Показать окно (SOS, «Собери состав») и поднять над всеми: кнопка мини-бара на SOS. В мини-баре окно
    отвязывается от свёрнутого окна программы, иначе Windows прячет его вместе с ним."""
    try:
        _detach_from_hidden_owner(window)
        if window.state() != "normal":
            window.deiconify()
        bring_to_front(window)
    except tk.TclError:
        pass


def anchor_area(root):
    """(x, y, ширина, высота): по центру чего ставить окно. Обычно — окно программы; свёрнуто в мини-бар —
    картинка игры (App.dialog_area), а если её не видно — весь экран."""
    app = _app_of(root)
    if app is not None and app.mini:
        area = app.dialog_area()
        if area:
            return area
        return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()
    return root.winfo_rootx(), root.winfo_rooty(), root.winfo_width(), root.winfo_height()


def _pointer_inside(widget):
    """Мышь над виджетом (или над его частями: у кнопок CustomTkinter внутри несколько виджетов)."""
    try:
        x, y = widget.winfo_pointerxy()
        left, top = widget.winfo_rootx(), widget.winfo_rooty()
        return left <= x < left + widget.winfo_width() and top <= y < top + widget.winfo_height()
    except tk.TclError:
        return False


class Card(ctk.CTkFrame):
    """Карточка: фон bg_surface, рамка 1 px, скругление 10."""

    def __init__(self, master, fg_color=None, border_color=None, corner_radius=None, **kwargs):
        super().__init__(master, fg_color=fg_color or C["bg_surface"], border_width=1,
                         border_color=border_color or C["border"],
                         corner_radius=S["radius_card"] if corner_radius is None else corner_radius, **kwargs)


# Виды кнопок (design/README.md, «Компоненты»). icon — цвет иконки, disabled — цвет текста неактивной кнопки
BUTTON_KINDS = {
    "secondary": dict(fg_color=C["bg_elevated"], hover_color=T["hover_elevated"], border_width=1,
                      border_color=C["border"], text_color=C["text"], font=F["button"], icon=C["text_secondary"]),
    "blue": dict(fg_color=C["blue_button"], hover_color=T["hover_blue"], border_width=0,
                 text_color=C["white"], font=F["button_bold"], icon=C["white"]),
    "save": dict(fg_color=C["green_button"], hover_color=T["hover_green_button"], border_width=0,
                 text_color=C["white"], font=F["button_bold"], icon=C["white"]),
    "cta": dict(fg_color=C["green"], hover_color=C["green_hover"], border_width=0,
                text_color=C["white"], font=F["cta"], icon=C["white"]),
    "danger": dict(fg_color="transparent", hover_color=T["danger_badge_bg"], border_width=1,
                   border_color=C["danger"], text_color=C["danger_text"], font=F["button"], icon=C["danger_text"]),
    "danger_solid": dict(fg_color=C["danger_button"], hover_color=T["hover_danger_button"], border_width=0,
                         text_color=C["white"], font=F["button_bold"], icon=C["white"]),
    "ghost_danger": dict(fg_color="transparent", hover_color=C["bg_elevated"], border_width=0,
                         text_color=C["danger_text"], font=F["button"], icon=C["danger_text"]),
    "ghost": dict(fg_color="transparent", hover_color=C["bg_elevated"], border_width=0,
                  text_color=C["text_secondary"], font=F["button"], icon=C["text_secondary"]),
    "link": dict(fg_color="transparent", hover_color=C["bg_surface"], border_width=0,
                 text_color=C["blue_text"], font=F["button"], icon=C["blue_text"]),
}


class Button(ctk.CTkButton):
    """Кнопка с текстом нужного вида (BUTTON_KINDS). Ширина — по надписи: длинные немецкие тексты не обрезаются.
    icon_name — иконка слева (имя файла из ui/icons), compound="right" — справа от надписи («RU ▾»).
    set_kind() меняет вид (пауза и стоп становятся яркими во время фарма)."""

    def __init__(self, master, text="", kind="secondary", icon_name=None, icon_size=16, command=None, height=None,
                 pad_x=14, compound="left", **kwargs):
        self._pad_x = pad_x
        self._kind = kind
        self._icon_name = icon_name
        self._icon_size = icon_size
        style = dict(BUTTON_KINDS[kind])
        icon_color = style.pop("icon")
        style.update(kwargs)
        height = height or (S["cta_height"] if kind == "cta" else S["control_height"])
        super().__init__(master, text=text, command=command, height=height, width=0,
                         corner_radius=S["radius_control"] if kind != "cta" else 8, border_spacing=2,
                         text_color_disabled=C["text_muted"], compound=compound,
                         image=icon(icon_name, icon_color, icon_size) if icon_name else None, **style)

    def _create_grid(self):
        # У CustomTkinter отступ слева и справа равен скруглению (6 px) — для надписи мало, как в макетах ставим pad_x
        super()._create_grid()
        pad = self._apply_widget_scaling(self._pad_x)
        self.grid_columnconfigure(0, minsize=pad)
        self.grid_columnconfigure(4, minsize=pad)

    def set_kind(self, kind):
        changed = kind != self._kind
        self._kind = kind
        style = dict(BUTTON_KINDS[kind])
        icon_color = style.pop("icon")
        if not changed:
            # Тот же вид (кнопку просто выключили или включили): шрифт не трогаем — смена шрифта перестраивает кнопку
            style.pop("font")
        disabled = self.cget("state") == "disabled"
        if disabled:
            # Неактивная кнопка бледная (экран 4: «Внедрить золотые правила», пока нечего внедрять)
            icon_color = C["text_muted"]
            if style["fg_color"] != "transparent":
                style["fg_color"] = theme.blend(style["fg_color"], C["bg_surface"], 0.3)
            if style.get("border_width"):
                style["border_color"] = theme.blend(style["border_color"], C["bg_surface"], 0.4)
        if self._icon_name:
            style["image"] = icon(self._icon_name, icon_color, self._icon_size)
        self.configure(**style)

    def set_icon(self, icon_name):
        self._icon_name = icon_name
        self.set_kind(self._kind)

    def set_enabled(self, enabled):
        self.configure(state="normal" if enabled else "disabled")
        self.set_kind(self._kind)


class IconButton(ctk.CTkButton):
    """Квадратная кнопка с иконкой: шапка (34 px), сайдбар (44 px, kind="nav"), док-плеер (38 px).
    tooltip — подсказка при наведении (у кнопок без текста она обязательна). set_active() — выбранный пункт сайдбара."""

    def __init__(self, master, icon_name, command=None, size=None, icon_size=None, tooltip=None, tooltip_side="bottom",
                 kind="default", icon_color=None, **kwargs):
        self._icon_name = icon_name
        self._kind = kind
        self._icon_size = icon_size or (S["icon_nav"] if kind == "nav" else S["icon"])
        self._icon_color = icon_color
        self._active = False
        size = size or (S["rail_button"] if kind == "nav" else S["header_button"])
        if kind == "nav":
            style = dict(fg_color="transparent", hover_color=T["hover_primary"], border_width=1,
                         border_color=C["bg_primary"], corner_radius=8)
        else:
            style = dict(fg_color=C["bg_surface"], hover_color=C["bg_elevated"], border_width=1,
                         border_color=C["border"], corner_radius=S["radius_control"])
        style.update(kwargs)
        super().__init__(master, text="", width=size, height=size, border_spacing=0, command=command,
                         image=self._icon_image(), **style)
        self.tooltip = Tooltip(self, tooltip, side=tooltip_side) if tooltip else None

    def _icon_image(self):
        if getattr(self, "_state", "normal") == "disabled":
            color = C["text_muted"]
        elif self._kind == "nav":
            color = C["blue_text"] if self._active else C["text_secondary"]
        else:
            color = self._icon_color or C["text_secondary"]
        return icon(self._icon_name, color, self._icon_size)

    def set_active(self, active):
        """Выбранный пункт сайдбара: синеватый фон, синяя рамка и иконка."""
        self._active = active
        self.configure(fg_color=T["nav_active_bg"] if active else "transparent",
                       border_color=T["nav_active_border"] if active else C["bg_primary"],
                       hover_color=T["nav_active_bg"] if active else T["hover_primary"], image=self._icon_image())

    def set_icon(self, icon_name, color=None):
        self._icon_name = icon_name
        if color:
            self._icon_color = color
        self.configure(image=self._icon_image())

    def set_enabled(self, enabled):
        self.configure(state="normal" if enabled else "disabled")
        self.configure(image=self._icon_image())

    def set_tooltip(self, text):
        if self.tooltip:
            self.tooltip.text = text
        elif text:
            self.tooltip = Tooltip(self, text)


class Tooltip:
    """Подсказка при наведении: маленькое окошко без рамки рядом с виджетом (справа для сайдбара, снизу для шапки).
    text — строка или функция без аргументов (тогда подсказка всегда на текущем языке)."""

    def __init__(self, widget, text, side="bottom", delay=None):
        self.widget = widget
        self.text = text
        self.side = side
        self.delay = S["tooltip_delay_ms"] if delay is None else delay
        self._after_id = None
        self._leave_id = None
        self._top = None
        self.attach(widget)
        widget.bind("<Destroy>", self._hide, add="+")  # виджет убрали, пока подсказка видна, — убрать и её

    def attach(self, widget):
        """Показывать подсказку и над этим виджетом (например, над картинкой внутри квадрата титана)."""
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _current_text(self):
        return self.text() if callable(self.text) else self.text

    def _on_enter(self, _event=None):
        self._cancel_leave()
        if self._top is None and self._after_id is None:
            try:
                self._after_id = self.widget.after(self.delay, self._show)
            except tk.TclError:
                pass

    def _on_leave(self, _event=None):
        # Мышь могла перейти на часть того же виджета: проверяем чуть позже, где она (одна проверка, не очередь)
        self._cancel_leave()
        try:
            self._leave_id = self.widget.after(30, self._hide_if_outside)
        except tk.TclError:
            pass

    def _hide_if_outside(self):
        self._leave_id = None
        if not _pointer_inside(self.widget):
            self._hide()

    def _cancel_leave(self):
        if self._leave_id:
            try:
                self.widget.after_cancel(self._leave_id)
            except tk.TclError:
                pass
            self._leave_id = None

    def _cancel(self):
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _show(self):
        self._after_id = None
        text = self._current_text()
        if not text or self._top is not None or not _pointer_inside(self.widget):
            return
        top = _frameless_window(self.widget.winfo_toplevel(), inactive=True)
        ctk.CTkLabel(top, text=text, font=F["label"], text_color=C["text"], fg_color=C["bg_elevated"],
                     bg_color=_CORNER_COLOR, corner_radius=S["radius_control"], height=26,
                     padx=8).pack()
        top.update_idletasks()
        w, h = top.winfo_reqwidth(), top.winfo_reqheight()
        wx, wy = self.widget.winfo_rootx(), self.widget.winfo_rooty()
        ww, wh = self.widget.winfo_width(), self.widget.winfo_height()
        gap = 8
        if self.side == "right":
            x, y = wx + ww + gap, wy + (wh - h) // 2
        elif self.side == "top":
            x, y = wx + (ww - w) // 2, wy - h - gap
        else:
            x, y = wx + (ww - w) // 2, wy + wh + gap
        screen_w = top.winfo_screenwidth()
        x = max(0, min(x, screen_w - w))
        top.geometry(f"+{x}+{max(0, y)}")
        top.deiconify()
        self._top = top

    def _hide(self, _event=None):
        self._cancel()
        self._cancel_leave()
        if self._top is not None:
            try:
                self._top.destroy()
            except tk.TclError:
                pass
            self._top = None


@lru_cache(maxsize=128)
def _titan_picture(path, mtime, size, radius):
    """Картинка титана: квадрат из середины, скруглённые углы (mtime в ключе — заменённая картинка перечитается)."""
    img = Image.open(path).convert("RGBA")
    side = min(img.size)
    left, top = (img.width - side) // 2, (img.height - side) // 2
    big = size * 4
    img = img.crop((left, top, left + side, top + side)).resize((big, big), Image.LANCZOS)
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, big - 1, big - 1), radius=radius * 4, fill=255)
    img.putalpha(Image.composite(img.getchannel("A"), mask, mask))
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


def titan_name(lang, titan):
    """Имя титана на языке окна; новый титан без перевода — по имени файла."""
    name = get_text(lang, f"titan_{titan}")
    return titan.capitalize() if name == f"titan_{titan}" else name


class TitanAvatar(ctk.CTkFrame):
    """Квадрат титана: рамка цветом стихии, фон — оттенок стихии, внутри картинка assets/icons/<титан>.png
    или две буквы имени, пока картинки нет. Подсказка с именем при наведении. command(titan) — по клику."""

    def __init__(self, master, titan, lang="RU", size=None, command=None, tooltip=True, **kwargs):
        self.titan = titan
        self.lang = lang
        self.size = size or S["avatar"]
        self.command = command
        style = theme.element_style(theme.element_of(titan))
        super().__init__(master, width=self.size, height=self.size, corner_radius=S["radius_control"],
                         border_width=S["avatar_border"], border_color=style["color"], fg_color=style["tint"], **kwargs)
        self.grid_propagate(False)
        self.pack_propagate(False)
        self.label = ctk.CTkLabel(self, text="", fg_color="transparent", text_color=C["text"],
                                  font=(theme.FONT_FAMILY, 12 if self.size >= 32 else 10, "bold"))
        self.label.place(relx=0.5, rely=0.5, anchor="center")
        self.tooltip = Tooltip(self, lambda: titan_name(self.lang, self.titan)) if tooltip else None
        if self.tooltip:
            self.tooltip.attach(self.label)
        for part in (self, self.label):
            part.bind("<Button-1>", self._on_click, add="+")
        self._render()

    def _render(self):
        path = theme.titan_icon_path(self.titan)
        inner = self.size - 2 * S["avatar_border"] - 2
        if path:
            image = _titan_picture(str(path), path.stat().st_mtime, inner, 4)
            self.label.configure(image=image, text="", width=inner, height=inner)
        else:
            self.label.configure(image=None, text=theme.initials(titan_name(self.lang, self.titan)),
                                 width=inner, height=inner)

    def _on_click(self, _event=None):
        if self.command:
            self.command(self.titan)

    def set_language(self, lang):
        self.lang = lang
        self._render()

    def set_titan(self, titan):
        self.titan = titan
        style = theme.element_style(theme.element_of(titan))
        self.configure(border_color=style["color"], fg_color=style["tint"])
        self._render()

    def set_dim(self, dim):
        """Бледный квадрат: титана нельзя выбрать (чужая стихия, уже выбрано 5). Только цвета — без перестройки."""
        style = theme.element_style(theme.element_of(self.titan))
        if dim:
            self.configure(border_color=theme.blend(style["color"], C["bg_surface"], 0.4),
                           fg_color=theme.blend(style["tint"], C["bg_surface"], 0.4))
            self.label.configure(text_color=C["text_muted"])
        else:
            self.configure(border_color=style["color"], fg_color=style["tint"])
            self.label.configure(text_color=C["text"])


# ── Лёгкие элементы для длинных прокручиваемых списков (мастер правил, проверка шага 5а) ─────────────────
# У каждой надписи и рамки CustomTkinter внутри свой холст: в Windows при прокрутке и раскрытии списка каждый
# перерисовывается отдельно, и элементы дорисовывались с заметной задержкой. В повторяющихся строках — обычные
# надписи и рамки Tk: цвет фона задаём сами (bg — цвет того, на чём они стоят), размер шрифта — с масштабом Windows.
def scaled_font(master, font):
    """Шрифт из theme.FONTS для обычной надписи Tk: размер в пикселях с учётом масштаба Windows (как у CustomTkinter)."""
    scale = ctk.ScalingTracker.get_widget_scaling(master)
    family, size, *rest = font
    return (family, -round(size * scale), *rest)


class PlainLabel(tk.Label):
    """Обычная надпись Tk вместо CTkLabel (без своего холста)."""

    def __init__(self, master, text="", font=None, color=None, bg=None, **kwargs):
        super().__init__(master, text=text, font=scaled_font(master, font or F["text"]), fg=color or C["text"],
                         bg=bg or C["bg_surface"], bd=0, highlightthickness=0, padx=0, pady=0, **kwargs)


def shared_photo(master, key, make):
    """Картинка Tk (ImageTk.PhotoImage) одна на окно программы, а не на каждый виджет: в длинных списках (правила —
    шаг 5в) одинаковых значков и квадратов титанов сотни, и создание картинок заметно тормозило постройку.
    Картинка Tk принадлежит своему окну (интерпретатору Tk), поэтому запас — у корня окна: новое окно — новый запас.
    make() — картинка PIL. Виджет, который её показывает, держит ссылку сам (если запас её когда-нибудь выбросит)."""
    root = master._root()
    cache = root.__dict__.setdefault("_shared_photos", {})
    photo = cache.get(key)
    if photo is None:
        photo = cache[key] = ImageTk.PhotoImage(make(), master=root)
    return photo


def plain_icon(master, name, color, size, box=None, tint=None, bg=None, radius=8):
    """Иконка для обычной надписи Tk (ImageTk.PhotoImage, в настоящих пикселях с учётом масштаба Windows).
    box — сторона квадрата-подложки цвета tint со скруглением radius (значок стихии 40×40), фон вокруг — bg."""
    scale = ctk.ScalingTracker.get_widget_scaling(master)
    args = (name, color.upper(), round(size * scale), round(box * scale) if box else 0, tint, bg, round(radius * scale))
    return shared_photo(master, ("icon",) + args, lambda: _plain_icon_picture(*args))


@lru_cache(maxsize=128)
def _plain_icon_picture(name, color, px, box_px, tint, bg, radius):
    from ui.icons import _colored
    k = 4
    glyph = _colored(name, color).resize((px * k, px * k), Image.LANCZOS)
    if not box_px:
        return glyph.resize((px, px), Image.LANCZOS)
    rgb = lambda c: tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))  # noqa: E731
    big = box_px * k
    img = Image.new("RGBA", (big, big), rgb(bg) + (255,))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, big - 1, big - 1), radius=radius * k, fill=rgb(tint) + (255,))
    img.alpha_composite(glyph, ((big - px * k) // 2, (big - px * k) // 2))
    return img.resize((box_px, box_px), Image.LANCZOS)


class TitanTile(tk.Label):
    """Лёгкий квадрат титана для длинных прокручиваемых списков (мастер правил): то же, что TitanAvatar
    (рамка цветом стихии, фон — оттенок стихии, картинка или две буквы, подсказка с именем), но одна обычная
    надпись Tk с готовой картинкой. У TitanAvatar внутри два холста CustomTkinter, и при прокрутке и раскрытии
    списков Windows перерисовывает каждый отдельно — элементы дорисовывались с задержкой (проверка шага 5а).
    bg — цвет того, на чём квадрат стоит (уголки скругления — его цвета). dim — бледный (выключенное правило, шаг 5в)."""

    def __init__(self, master, titan, lang="RU", size=None, bg=None, command=None, dim=False):
        self.titan = titan
        self.lang = lang
        self.command = command
        scale = ctk.ScalingTracker.get_widget_scaling(master)   # масштаб Windows: картинка — в настоящих пикселях
        px = round((size or S["avatar"]) * scale)
        path = theme.titan_icon_path(titan)
        bg = bg or C["bg_surface"]
        args = (titan, px, max(1, round(S["avatar_border"] * scale)), bg, str(path) if path else None,
                path.stat().st_mtime if path else 0)

        def picture():
            tile = _tile_picture(*args)
            if dim:
                tile = Image.blend(Image.new("RGBA", tile.size, _rgb(bg) + (255,)), tile, theme.RULE_DIM)
            return tile
        self.photo = shared_photo(master, ("tile", dim) + args, picture)
        text = "" if path else theme.initials(titan_name(lang, titan))
        font_px = round((12 if px >= 30 * scale else 10) * scale)
        super().__init__(master, image=self.photo, text=text, compound="center", bg=bg,
                         fg=theme.blend(C["text"], bg, theme.RULE_DIM) if dim else C["text"],
                         font=(theme.FONT_FAMILY, -font_px, "bold"), bd=0,
                         highlightthickness=0, padx=0, pady=0, width=px, height=px)
        self.tooltip = Tooltip(self, lambda: titan_name(self.lang, self.titan))
        if command:
            self.bind("<Button-1>", lambda _e: self.command(self.titan), add="+")


@lru_cache(maxsize=256)
def _tile_picture(titan, px, border, bg, path, mtime):
    """Готовый квадрат титана (PIL): скруглённый квадрат цвета стихии на фоне bg, внутри картинка титана.
    Рисуется в 4 раза крупнее и уменьшается — края гладкие. mtime в ключе — заменённая картинка перечитается."""
    style = theme.element_style(theme.element_of(titan))
    k = 4
    big = px * k
    rgb = lambda color: tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))  # noqa: E731
    img = Image.new("RGBA", (big, big), rgb(bg) + (255,))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, big - 1, big - 1), radius=S["radius_control"] * px * k // S["avatar"],
                                          fill=rgb(style["tint"]) + (255,), outline=rgb(style["color"]) + (255,),
                                          width=border * k)
    if path:
        inner = px - 2 * border - 2
        side_big = inner * k
        pic = Image.open(path).convert("RGBA")
        side = min(pic.size)
        left, top = (pic.width - side) // 2, (pic.height - side) // 2
        pic = pic.crop((left, top, left + side, top + side)).resize((side_big, side_big), Image.LANCZOS)
        mask = Image.new("L", (side_big, side_big), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, side_big - 1, side_big - 1), radius=4 * k * px // S["avatar"],
                                               fill=255)
        pic.putalpha(Image.composite(pic.getchannel("A"), mask, mask))
        offset = (big - side_big) // 2
        img.alpha_composite(pic, (offset, offset))
    return img.resize((px, px), Image.LANCZOS)


def _rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def text_width(widget, font, text):
    """Ширина надписи в пикселях (шрифт обычной надписи Tk — scaled_font). Без именованного шрифта Tk: его не надо
    удалять, и он не копится."""
    return int(widget.tk.call("font", "measure", scaled_font(widget, font), "-displayof", widget, text))


def pill_label(master, text, font, fg, fill, bg, height=20, radius=4, pad_x=7):
    """Значок с надписью на скруглённой подложке («Смешанная», «ЛЕЧЕНИЕ», «Спросить вас» в строке правила, шаг 5в):
    обычная надпись Tk поверх готовой картинки подложки — без своего холста, как TitanTile (длинные списки)."""
    scale = ctk.ScalingTracker.get_widget_scaling(master)
    w = text_width(master, font, text) + round(2 * pad_x * scale)
    args = (w, round(height * scale), fill, bg, round(radius * scale))
    photo = shared_photo(master, ("pill",) + args, lambda: _pill_picture(*args))
    label = tk.Label(master, image=photo, text=text, compound="center", fg=fg, bg=bg,
                     font=scaled_font(master, font), bd=0, highlightthickness=0, padx=0, pady=0)
    label.photo = photo
    return label


@lru_cache(maxsize=64)
def _pill_picture(w, h, fill, bg, radius):
    k = 4
    img = Image.new("RGBA", (w * k, h * k), _rgb(bg) + (255,))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, w * k - 1, h * k - 1), radius=radius * k, fill=_rgb(fill) + (255,))
    return img.resize((w, h), Image.LANCZOS)


class ElidedLabel(PlainLabel):
    """Надпись в одну строку, которая не раздвигает строку списка: длинный текст обрезается по ширине с «…»,
    полный — в подсказке. Ширину надписи задаёт сетка (sticky="ew"), текст подгоняется при изменении ширины."""

    def __init__(self, master, text="", font=None, **kwargs):
        super().__init__(master, "", font=font, width=1, anchor="w", **kwargs)
        self._font = font or F["text"]
        self.full = text
        self._fitted_for = None
        self.tooltip = Tooltip(self, lambda: self.full if self.cget("text") != self.full else "")
        self.bind("<Configure>", lambda _e: self.fit(), add="+")

    def set_full(self, text):
        self.full = text
        self._fitted_for = None
        self.fit()

    def fit(self):
        width = self.winfo_width()
        if width <= 1 or width == self._fitted_for:
            return
        self._fitted_for = width
        text = self.full
        if text_width(self, self._font, text) > width:
            low, high = 0, len(text)
            while low < high:   # самая длинная начальная часть, которая влезает вместе с «…»
                mid = (low + high + 1) // 2
                if text_width(self, self._font, text[:mid].rstrip() + "…") <= width:
                    low = mid
                else:
                    high = mid - 1
            text = text[:low].rstrip() + "…"
        if self.cget("text") != text:
            self.configure(text=text)


class PlainSwitch(tk.Label):
    """Лёгкий тумблер 36×20 для строк длинного списка (макет 03c, «Вкл.»): картинка, без своего холста.
    command(включён) — после щелчка; set_on() — без вызова command."""

    def __init__(self, master, value=False, command=None, bg=None, tooltip=None):
        self._bg = bg or C["bg_elevated"]
        scale = ctk.ScalingTracker.get_widget_scaling(master)
        size = (round(36 * scale), round(20 * scale))
        self._pictures = {on: shared_photo(master, ("switch", on, self._bg) + size,
                                           lambda on=on: _switch_picture(*size, on, self._bg)) for on in (True, False)}
        super().__init__(master, bg=self._bg, bd=0, highlightthickness=0, padx=0, pady=0, cursor="hand2")
        self.command = command
        self.on = None
        self.set_on(value)
        self.bind("<Button-1>", self._clicked, add="+")
        self.tooltip = Tooltip(self, tooltip) if tooltip else None

    def set_on(self, value):
        value = bool(value)
        if value != self.on:
            self.on = value
            self.configure(image=self._pictures[value])

    def _clicked(self, _event=None):
        self.set_on(not self.on)
        if self.command:
            self.command(self.on)


@lru_cache(maxsize=8)
def _switch_picture(w, h, on, bg):
    k = 4
    img = Image.new("RGBA", (w * k, h * k), _rgb(bg) + (255,))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, w * k - 1, h * k - 1), radius=h * k // 2,
                           fill=_rgb(C["blue"] if on else C["border_strong"]) + (255,))
    pad = 2 * h * k // 20
    knob = h * k - 2 * pad
    x = w * k - pad - knob if on else pad
    draw.ellipse((x, pad, x + knob - 1, pad + knob - 1), fill=_rgb(C["white"] if on else C["text_secondary"]) + (255,))
    return img.resize((w, h), Image.LANCZOS)


class RoundedBackdrop(tk.Label):
    """Скруглённая подложка с рамкой 1 px под содержимым рамки Tk (строка длинного списка, шаг 5в): готовая картинка
    вместо холста CustomTkinter. Ставится первой в рамку (place во всю рамку), содержимое кладётся поверх; при новом
    размере рамки — картинка этого размера (одна на окно для всех строк одного размера)."""

    def __init__(self, master, fill, border, outer, radius=8):
        super().__init__(master, bg=outer, bd=0, highlightthickness=0, padx=0, pady=0)
        self._look = (fill, border, outer, round(radius * ctk.ScalingTracker.get_widget_scaling(master)))
        self._size = None
        self.photo = None
        self.place(x=0, y=0, relwidth=1, relheight=1)
        master.bind("<Configure>", self._fit, add="+")

    def _fit(self, event):
        size = (event.width, event.height)
        if size == self._size or min(size) < 4:
            return
        self._size = size
        key = ("backdrop",) + size + self._look
        cache = self._root().__dict__.setdefault("_shared_photos", {})
        if key not in cache:   # размеров при изменении окна много — старые подложки не копим
            for old in [k for k in cache if k[0] == "backdrop"][:-8]:
                del cache[old]
        self.photo = shared_photo(self, key, lambda: _backdrop_picture(*size, *self._look))
        self.configure(image=self.photo)


    def restyle(self, fill, border):
        """Другие цвета подложки (наведение на кнопку): готовая картинка того же размера, виджеты не перестраиваются."""
        look = (fill, border) + self._look[2:]
        if look == self._look:
            return
        self._look = look
        if self._size:
            key = ("backdrop",) + self._size + look
            self.photo = shared_photo(self, key, lambda: _backdrop_picture(*self._size, *look))
            self.configure(image=self.photo)


def _backdrop_picture(w, h, fill, border, outer, radius):
    k = 3
    img = Image.new("RGBA", (w * k, h * k), _rgb(outer) + (255,))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, w * k - 1, h * k - 1), radius=radius * k, fill=_rgb(fill) + (255,),
                                          outline=_rgb(border) + (255,), width=k)
    return img.resize((w, h), Image.LANCZOS)


class PlainIconButton(tk.Label):
    """Лёгкая кнопка-значок для строк длинного списка (↑↓, карандаш, ✕ в «Правилах и перехватах»): картинка без
    своего холста. Наведение меняет только цвет фона; недоступная — бледный значок и щелчок не работает."""

    def __init__(self, master, icon_name, command=None, size=14, bg=None, hover=None, color=None, tooltip=None,
                 pad=8, pad_y=8):
        self._bg = bg or C["bg_elevated"]
        self._hover = hover or T["hover_elevated"]
        self._pictures = {state: plain_icon(master, icon_name, c, size)
                          for state, c in (("on", color or C["text_secondary"]), ("off", C["border_focus"]))}
        scale = ctk.ScalingTracker.get_widget_scaling(master)
        # У надписи-картинки Tk padx не работает: место вокруг значка задаёт ширина и высота (в пикселях)
        super().__init__(master, image=self._pictures["on"], bg=self._bg, bd=0, highlightthickness=0,
                         width=round((size + 2 * pad) * scale), height=round((size + 2 * pad_y) * scale),
                         cursor="hand2")
        self.command = command
        self.enabled = True
        self._look = self._bg
        self.bind("<Button-1>", self._clicked, add="+")
        self.bind("<Enter>", lambda _e: self._paint(True), add="+")
        self.bind("<Leave>", lambda _e: self._paint(False), add="+")
        self.tooltip = Tooltip(self, tooltip) if tooltip else None

    def _paint(self, hovering):
        look = self._hover if hovering and self.enabled else self._bg
        if look != self._look:
            self._look = look
            self.configure(bg=look)

    def _clicked(self, _event=None):
        if self.enabled and self.command:
            self.command()

    def set_enabled(self, enabled):
        if enabled != self.enabled:
            self.enabled = enabled
            self.configure(image=self._pictures["on" if enabled else "off"], cursor="hand2" if enabled else "")
            if not enabled:
                self._paint(False)


def plain_card(master, outer, fill=None, border=None, radius=None):
    """Карточка без холста CustomTkinter (страница «О программе», шаг 7): рамка Tk с готовой скруглённой подложкой.
    outer — цвет за карточкой (в углах), содержимое кладут прямо в неё (grid/pack), у надписей bg=fill, а от краёв — не меньше
    радиуса, чтобы квадратные уголки надписей не закрыли скругление. Прокрутка страницы с такими карточками не оставляет следов."""
    card = tk.Frame(master, bg=outer)
    card.fill = fill or C["bg_surface"]
    card.backdrop = RoundedBackdrop(card, card.fill, border or C["border"], outer,
                                    radius=S["radius_card"] if radius is None else radius)
    return card


class PlainClickFrame(tk.Frame):
    """Рамка-кнопка без холста CustomTkinter: щелчок по ней или по любой её части — command(), наведение — _paint() по
    self._hovering (только цвета). Уход мыши проверяется через 30 мс по положению указателя: при переходе между частями рамки
    «ушла/пришла» не мигает. Части, добавленные после создания, подключает bind_parts()."""

    def __init__(self, master, command=None, **kwargs):
        super().__init__(master, **kwargs)
        self.command = command
        self.enabled = True
        self._hovering = False
        self._leave_id = None
        self.bind_parts(self)
        self.bind("<Destroy>", self._cancel_leave, add="+")

    def bind_parts(self, *parts):
        for part in parts:
            part.bind("<Button-1>", self._click, add="+")
            part.bind("<Enter>", self._enter, add="+")
            part.bind("<Leave>", self._leave, add="+")

    def _paint(self):
        pass

    def _click(self, _event=None):
        if self.enabled and self.command:
            self.command()

    def _enter(self, _event=None):
        if not self._hovering:
            self._hovering = True
            self._paint()

    def _leave(self, _event=None):
        self._cancel_leave()
        try:
            self._leave_id = self.after(30, self._leave_if_outside)
        except tk.TclError:
            self._leave_id = None

    def _cancel_leave(self, _event=None):
        if self._leave_id:
            try:
                self.after_cancel(self._leave_id)
            except tk.TclError:
                pass
            self._leave_id = None

    def _leave_if_outside(self):
        self._leave_id = None
        if not _pointer_inside(self):
            self._hovering = False
            self._paint()


# Виды лёгкой кнопки: заливка, рамка, заливка при наведении, цвет текста, цвет значка
PLAIN_BUTTON_KINDS = {
    "secondary": dict(fill=C["bg_elevated"], border=C["border"], hover=T["hover_elevated"], text=C["text"],
                      icon=C["text_secondary"]),
    "blue": dict(fill=C["blue_button"], border=C["blue_button"], hover=T["hover_blue"], text=C["white"],
                 icon=C["white"]),
    "outline": dict(fill=None, border=C["border_strong"], hover=T["hover_elevated"], text=C["text"],
                    icon=C["text_secondary"]),
}


class PlainButton(PlainClickFrame):
    """Кнопка со скруглением без холста CustomTkinter (страница «О программе», шаг 7): рамка Tk, скругление — готовая
    картинка (RoundedBackdrop), внутри одна надпись Tk со значком. Наведение — другая картинка подложки и цвет надписи.
    kind: secondary / blue / outline (без заливки: цвет за кнопкой — outer). outer — цвет за кнопкой, он же заливка outline.
    Ширина — по надписи (меньше не бывает), в сетке с sticky="ew" растягивается; text="" — квадрат с одним значком.
    icon_gap — зазор между значком и надписью (у кнопки с одним значком — 0). set_text() меняет надпись и ширину (язык окна)."""

    def __init__(self, master, text="", command=None, kind="secondary", icon_name=None, icon_size=15, height=36,
                 pad_x=12, anchor="center", outer=None, font=None, width=None, tooltip=None, icon_gap=12):
        self._style = dict(PLAIN_BUTTON_KINDS[kind])
        self._outer = outer or C["bg_surface"]
        if self._style["fill"] is None:
            self._style["fill"] = self._outer
        fill = self._style["fill"]
        scale = ctk.ScalingTracker.get_widget_scaling(master)
        super().__init__(master, command=command, bg=self._outer, height=round(height * scale), cursor="hand2")
        self.grid_propagate(False)
        self.pack_propagate(False)
        self._font = font or F["button"]
        self._pad_x = pad_x
        self._min_width = width
        self._icon_gap = icon_gap if icon_name else 0
        self.backdrop = RoundedBackdrop(self, fill, self._style["border"], self._outer, radius=S["radius_control"])
        # Значок на подложке цвета заливки: по одной картинке на обычный вид и на наведение (наведение только меняет их)
        self.photos = {hovering: plain_icon(self, icon_name, self._style["icon"], icon_size,
                                            box=icon_size + self._icon_gap, tint=color, bg=color, radius=0)
                       for hovering, color in ((False, fill), (True, self._style["hover"]))} if icon_name else {}
        self.photo = self.photos.get(False)
        self.label = tk.Label(self, text=text, image=self.photo, compound="left" if icon_name else "none", fg=self._style["text"],
                              bg=fill, font=scaled_font(self, self._font), bd=0, highlightthickness=0, padx=0, pady=0,
                              anchor=anchor, cursor="hand2", width=1)
        # У значка своя подложка шире самого значка (на gap): половина зазора уже внутри картинки, отступ слева — без неё
        # Сверху и снизу — рамка 1 px, по бокам — не меньше 3 px: надпись не должна закрыть рамку и скругление подложки
        self.label.pack(fill="both", expand=True, pady=max(1, round(scale)),
                        padx=max(round(3 * scale), round((pad_x - (self._icon_gap / 2)) * scale)))
        self.bind_parts(self.label)
        self.icon_size = icon_size
        self.fit_width()
        if tooltip:
            self.tooltip = Tooltip(self, tooltip)
            self.tooltip.attach(self.label)

    def fit_width(self):
        """Ширина не меньше, чем надо надписи со значком (в языках надписи разной длины)."""
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        text = self.label.cget("text")
        inner = text_width(self, self._font, text) if text else 0
        if self.photo is not None:
            inner += round((self.icon_size + self._icon_gap) * scale)
        width = round(2 * (self._pad_x - (self._icon_gap / 2)) * scale) + inner
        self.configure(width=max(width, round((self._min_width or 0) * scale)))

    def set_text(self, text):
        if self.label.cget("text") != text:
            self.label.configure(text=text)
            self.fit_width()

    def _paint(self):
        fill = self._style["hover"] if self._hovering else self._style["fill"]
        self.backdrop.restyle(fill, self._style["border"])
        if self.label.cget("bg") != fill:
            self.label.configure(bg=fill)
            if self.photos:   # у значка своя подложка цвета заливки: на наведении — подложка цвета наведения
                self.label.configure(image=self.photos[self._hovering])


class Chip(ctk.CTkFrame):
    """Фильтр-«таблетка» высотой 30: выбранный — фон bg_elevated и светлая рамка, невыбранный — прозрачный.
    dot_color — цветная точка слева (фильтр стихии), count — красный счётчик справа («Ошибки 1»)."""

    def __init__(self, master, text, selected=False, command=None, dot_color=None, count=None, **kwargs):
        super().__init__(master, height=S["chip_height"], corner_radius=S["radius_chip"], border_width=1, **kwargs)
        self.command = command
        self.selected = selected
        self._hovering = False
        self._look = None        # что нарисовано сейчас: перекрашиваем, только если вид поменялся
        self._leave_id = None
        self._dot = ctk.CTkLabel(self, text="", image=dot(dot_color, 8), width=8) if dot_color else None
        if self._dot:
            self._dot.pack(side="left", padx=(12, 0), pady=2)
        self._label = ctk.CTkLabel(self, text=text, height=24, font=F["label"], fg_color="transparent")
        self._label.pack(side="left", pady=2)
        self._count = ctk.CTkLabel(self, text="", height=18, width=18, corner_radius=9, font=F["small_bold"],
                                   fg_color=T["danger_badge_bg"], text_color=C["danger_text"])
        self.set_count(count)
        for part in (self, self._label, self._count) + ((self._dot,) if self._dot else ()):
            part.bind("<Button-1>", self._on_click, add="+")
            part.bind("<Enter>", self._chip_enter, add="+")
            part.bind("<Leave>", self._chip_leave, add="+")
        self._paint()

    def _paint(self):
        if self.selected:
            look = (C["bg_elevated"], C["border_focus"], C["text"], True)
        else:
            look = (C["bg_elevated"] if self._hovering else "transparent", C["border"], C["text_secondary"], False)
        if look == self._look:
            return
        fg, border, text, bold = look
        old = self._look or (None, None, None, None)
        self._look = look
        if (fg, border) != old[:2]:
            self.configure(fg_color=fg, border_color=border)
        if text != old[2]:
            self._label.configure(text_color=text)
        if bold != old[3]:
            # Шрифт меняется только при выборе (не при наведении): смена шрифта перестраивает надпись
            self._label.configure(font=F["label_bold"] if bold else F["label"])

    def _on_click(self, _event=None):
        if self.command:
            self.command()

    def _chip_enter(self, _event=None):
        if not self._hovering:
            self._hovering = True
            self._paint()

    def _chip_leave(self, _event=None):
        if self._leave_id:
            try:
                self.after_cancel(self._leave_id)
            except tk.TclError:
                pass
        try:
            self._leave_id = self.after(30, self._leave_if_outside)
        except tk.TclError:
            self._leave_id = None

    def _leave_if_outside(self):
        self._leave_id = None
        if not _pointer_inside(self):
            self._hovering = False
            self._paint()

    def set_selected(self, selected):
        self.selected = selected
        self._paint()

    def set_text(self, text):
        self._label.configure(text=text)

    def set_count(self, count):
        """Счётчик справа; 0 или None — счётчика нет."""
        left = 6 if self._dot else 12
        if count:
            self._count.configure(text=str(count))
            self._label.pack_configure(padx=(left, 6))
            self._count.pack(side="left", padx=(0, 8), pady=2)
        else:
            self._label.pack_configure(padx=(left, 12))
            self._count.pack_forget()


class ClickFrame(ctk.CTkFrame):
    """Рамка, которая ведёт себя как кнопка: щелчок по ней или по любой её части — command(), наведение — _paint().
    Наследник рисует себя в _paint() по self._hovering и сам решает, что перекрасить (только цвета и только если вид
    поменялся — правило в начале файла). Части, добавленные после создания, подключает bind_parts()."""

    def __init__(self, master, command=None, **kwargs):
        super().__init__(master, **kwargs)
        self.command = command
        self.enabled = True
        self._hovering = False
        self._leave_id = None
        self.bind_parts(self)

    def bind_parts(self, *parts):
        for part in parts:
            part.bind("<Button-1>", self._frame_click, add="+")
            part.bind("<Enter>", self._frame_enter, add="+")
            part.bind("<Leave>", self._frame_leave, add="+")

    def _paint(self):
        pass

    def _frame_click(self, _event=None):
        if self.enabled and self.command:
            self.command()

    def _frame_enter(self, _event=None):
        if not self._hovering:
            self._hovering = True
            self._paint()

    def _frame_leave(self, _event=None):
        if self._leave_id:
            try:
                self.after_cancel(self._leave_id)
            except tk.TclError:
                pass
        try:
            self._leave_id = self.after(30, self._leave_if_outside)
        except tk.TclError:
            self._leave_id = None

    def _leave_if_outside(self):
        self._leave_id = None
        if not _pointer_inside(self):
            self._hovering = False
            self._paint()

    def set_enabled(self, enabled):
        if enabled != self.enabled:
            self.enabled = enabled
            self._paint()


# Кнопки «Пауза F9», «Продолжить F9», «СТОП F10» (главная, макет 01_main): цвет рамки, цвет текста, иконка
KEY_BUTTON_KINDS = {
    "pause": (C["warning"], C["warning"], "pause-filled"),
    "continue": (C["success"], C["success"], "play-filled"),
    "stop": (C["danger"], C["danger_text"], "square-filled"),
}


class KeyButton(ClickFrame):
    """Контурная кнопка с подписью клавиши справа (рамочка «F9»): высота 38, прозрачная, рамка и текст цвета вида.
    Неактивная — бледная (пока бот не работает). set_kind() меняет вид и надпись («Пауза» ⇄ «Продолжить»)."""

    def __init__(self, master, text, key, kind="pause", command=None, tooltip=None, height=38, width=100, **kwargs):
        # width — наименьшая ширина: в сетке кнопка растягивается по колонке (у рамки CustomTkinter по умолчанию 200)
        super().__init__(master, command=command, width=width, height=height, corner_radius=S["radius_control"],
                         border_width=1, fg_color="transparent", **kwargs)
        self.kind = kind
        self._look = None
        self.grid_propagate(False)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure((0, 4), weight=1)
        self._icon_label = ctk.CTkLabel(self, text="", width=14, height=14)
        self._icon_label.grid(row=0, column=1, padx=(0, 6))
        self._label = ctk.CTkLabel(self, text=text, font=F["button"], height=20)
        self._label.grid(row=0, column=2)
        self._kbd = ctk.CTkFrame(self, corner_radius=3, border_width=1, fg_color="transparent", height=16)
        self._kbd.grid(row=0, column=3, padx=(6, 0))
        self._kbd_label = ctk.CTkLabel(self._kbd, text=key, font=(theme.MONO_FAMILY, 10), height=12, width=14)
        self._kbd_label.pack(padx=4, pady=1)
        self.bind_parts(self._icon_label, self._label, self._kbd, self._kbd_label)
        self.tooltip = Tooltip(self, tooltip) if tooltip else None
        if self.tooltip:
            for part in (self._icon_label, self._label, self._kbd, self._kbd_label):
                self.tooltip.attach(part)
        self._paint()

    def _paint(self):
        border, text, icon_name = KEY_BUTTON_KINDS[self.kind]
        if not self.enabled:
            border, text = theme.blend(border, C["bg_surface"], 0.4), theme.blend(text, C["bg_surface"], 0.4)
        fg = theme.blend(border, C["bg_surface"], 0.12) if self._hovering and self.enabled else "transparent"
        look = (border, text, icon_name, fg)
        if look == self._look:
            return
        old = self._look or (None, None, None, None)
        self._look = look
        if (border, fg) != (old[0], old[3]):
            self.configure(border_color=border, fg_color=fg)
        if (text, icon_name) != old[1:3]:
            # Цвет текста и иконка меняются только при смене вида или выключении, не при наведении
            self._label.configure(text_color=text)
            self._kbd_label.configure(text_color=text)
            self._kbd.configure(border_color=theme.blend(text, C["bg_surface"], 0.5))
            self._icon_label.configure(image=icon(icon_name, text, 14))

    def set_kind(self, kind, text=None):
        self.kind = kind
        if text is not None and text != self._label.cget("text"):
            self._label.configure(text=text)
        self._paint()

    def set_text(self, text):
        if text != self._label.cget("text"):
            self._label.configure(text=text)


class Field(ctk.CTkFrame):
    """Поле ввода с подписью сверху и подсказкой снизу (экран 8). Состояния: обычное; в фокусе — рамка 2 px синяя;
    ошибка (set_error) — рамка 2 px красная, текст ошибки под полем; недоступно (set_enabled(False)) — серый текст."""

    def __init__(self, master, label="", hint="", value="", mono=True, width=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.hint = hint
        self.error = None
        self.enabled = True
        self._look = (1, C["border"], C["bg_elevated"], C["text"])  # так поле создаётся ниже
        self.grid_columnconfigure(0, weight=1)
        self.label = ctk.CTkLabel(self, text=label, font=F["label"], text_color=C["text_secondary"], anchor="w",
                                  height=18)
        self.label.grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.entry = ctk.CTkEntry(self, height=S["control_height"], width=width or 140,
                                  corner_radius=S["radius_control"], border_width=1, border_color=C["border"],
                                  fg_color=C["bg_elevated"], text_color=C["text"],
                                  font=F["mono_field"] if mono else F["body"])
        self.entry.grid(row=1, column=0, sticky="ew")
        self.entry.insert(0, str(value))
        self.note = ctk.CTkLabel(self, text=hint, font=F["label"], text_color=C["text_muted"], anchor="w", height=18,
                                 compound="left")
        self.note.grid(row=2, column=0, sticky="w", pady=(6, 0))
        if not hint:
            self.note.grid_remove()
        self._focus = False
        self.entry.bind("<FocusIn>", lambda _e: self._set_focus(True), add="+")
        self.entry.bind("<FocusOut>", lambda _e: self._set_focus(False), add="+")

    def _set_focus(self, focus):
        self._focus = focus
        self._paint(focus)

    def _paint(self, focus=False):
        if not self.enabled:
            look = (1, C["border"], T["field_disabled_bg"], C["text_muted"])
        elif self.error:
            look = (2, C["danger"], T["field_error_bg"], C["text"])
        elif focus:
            look = (2, C["blue"], C["bg_elevated"], C["text"])
        else:
            look = (1, C["border"], C["bg_elevated"], C["text"])
        if look == self._look:  # толщина рамки перестраивает поле — только если вид правда поменялся
            return
        self._look = look
        width, border, fg, text = look
        self.entry.configure(border_width=width, border_color=border, fg_color=fg, text_color=text)

    def show_focus(self):
        """Нарисовать поле «в фокусе», не забирая фокус (для витрины)."""
        self._paint(focus=True)

    def set_error(self, message):
        """Показать ошибку под полем; None — убрать её и вернуть подсказку."""
        self.error = message
        if message:
            # Пробел — зазор между значком и текстом (у CTkLabel нет своего отступа для картинки)
            self.note.configure(text=" " + message, text_color=C["danger_text"],
                                image=icon("triangle-alert", C["danger_text"], 13))
            self.note.grid()
        else:
            self.note.configure(text=self.hint, text_color=C["text_muted"], image=None)
            if self.hint:
                self.note.grid()
            else:
                self.note.grid_remove()
        self._paint(focus=self._focus)

    def set_hint(self, hint):
        self.hint = hint
        if not self.error:
            self.set_error(None)

    def set_enabled(self, enabled, hint=None):
        """Недоступное поле (например, во время фарма); hint — почему его нельзя менять."""
        self.enabled = enabled
        self.entry.configure(state="normal" if enabled else "disabled")
        if hint is not None:
            self.set_hint(hint)
        self._paint()

    def get(self):
        return self.entry.get()

    def set(self, value):
        state = self.entry.cget("state")
        self.entry.configure(state="normal")
        self.entry.delete(0, "end")
        self.entry.insert(0, str(value))
        self.entry.configure(state=state)


class Switch(ctk.CTkSwitch):
    """Тумблер 40×22 (макет 03a): включён — синий трек и белая ручка, выключен — серый трек и серая ручка.
    command(включён) — после переключения мышью; set_on() меняет положение без вызова command.
    (set и get — методы самого CTkSwitch, их не переопределяем.)"""

    def __init__(self, master, value=False, command=None, **kwargs):
        self._on_change = command
        super().__init__(master, text="", width=40, height=22, switch_width=40, switch_height=22, border_width=0,
                         corner_radius=11, button_length=0, fg_color=C["border_strong"], progress_color=C["blue"],
                         command=self._toggled, **kwargs)
        self.set_on(value)

    def _paint_knob(self):
        knob = C["white"] if self.is_on() else C["text_secondary"]
        if self.cget("button_color") != knob:  # цвет ручки — только при переключении, не при наведении
            self.configure(button_color=knob, button_hover_color=knob)

    def set_on(self, value):
        if value:
            self.select()
        else:
            self.deselect()
        self._paint_knob()

    def is_on(self):
        return self.get() == 1

    def _toggled(self):
        self._paint_knob()
        if self._on_change:
            self._on_change(self.is_on())


def plain_disc(master, size, color):
    """Кружок цвета color на прозрачном фоне (картинка для обычной надписи Tk: номер места поверх — compound="center").
    Прозрачные уголки: при наведении надпись меняет только свой фон — без новой картинки."""
    scale = ctk.ScalingTracker.get_widget_scaling(master)
    return ImageTk.PhotoImage(_disc_picture(round(size * scale), color), master=master)


@lru_cache(maxsize=16)
def _disc_picture(px, color):
    k = 4
    rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
    img = Image.new("RGBA", (px * k, px * k), rgb + (0,))
    ImageDraw.Draw(img).ellipse((0, 0, px * k - 1, px * k - 1), fill=rgb + (255,))
    return img.resize((px, px), Image.LANCZOS)


class Dropdown(ClickFrame):
    """Выпадающий список в цветах поля ввода (макет 03a: «Титанит ▾», «05:00»): высота 36, слева значок (по желанию),
    надпись, справа стрелка. Пункты — (ключ, надпись); command(ключ) — после выбора. icons — {ключ: (иконка, цвет)}.
    Список — меню CustomTkinter (как выбор языка в полоске).
    Шаг 5б (макет 03b): badge — номер места в кружке слева («1» в «Приоритете дверей»), colors — {ключ: цвет надписи}
    (стихия своим цветом), breaks — с каких пунктов начинать новую колонку меню (длинный список титанов — по стихиям).
    Внутри — обычные надписи Tk (у CTkLabel свой холст на каждую, а списков на вкладке много: в Windows они
    дорисовывались с задержкой). Наведение меняет только цвет фона рамки и надписей."""

    def __init__(self, master, items, value, command=None, icons=None, width=140, mono=False, badge=None,
                 colors=None, breaks=(), **kwargs):
        super().__init__(master, command=self.open, width=width, height=S["control_height"],
                         corner_radius=S["radius_control"], border_width=1, border_color=C["border"],
                         fg_color=C["bg_elevated"], **kwargs)
        self.items = list(items)
        self.value = value
        self.icons = icons or {}
        self.colors = colors or {}
        self.breaks = set(breaks)
        self.on_choose = command
        self._look = None
        self._pictures = {}
        self.grid_propagate(False)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)
        bg = C["bg_elevated"]
        self._badge = None
        if badge is not None:
            self._disc = plain_disc(self, 22, C["bg_primary"])
            self._badge = tk.Label(self, text=str(badge), image=self._disc, compound="center", bg=bg,
                                   fg=C["text_secondary"], font=scaled_font(self, F["label"]), bd=0,
                                   highlightthickness=0, padx=0, pady=0)
            self._badge.grid(row=0, column=0, padx=(8, 0))
        self._icon_label = tk.Label(self, bg=bg, bd=0, highlightthickness=0, padx=0, pady=0)
        self._label = PlainLabel(self, "", font=F["mono_field"] if mono else F["body"], color=C["text"], bg=bg,
                                 anchor="w")
        self._label.grid(row=0, column=2, sticky="ew", padx=(10, 4))
        self._arrow_picture = plain_icon(self, "chevron-down", C["text_muted"], 16)
        self._arrow = tk.Label(self, image=self._arrow_picture, bg=bg, bd=0, highlightthickness=0)
        self._arrow.grid(row=0, column=3, padx=(0, 10))
        self._parts = [p for p in (self._badge, self._icon_label, self._label, self._arrow) if p is not None]
        self.bind_parts(*self._parts)
        self.menu = DropdownMenu(self.winfo_toplevel(), values=[text for _k, text in self.items],
                                 command=self._chosen, fg_color=C["bg_elevated"], hover_color=C["blue_button"],
                                 text_color=C["text"], font=F["text"], min_character_width=6)
        self._break_columns()
        self._show_value()
        self._paint()

    def _break_columns(self):
        for i, (key, _text) in enumerate(self.items):
            if key in self.breaks:
                try:
                    self.menu.entryconfigure(i, columnbreak=1)
                except tk.TclError:
                    pass

    def _paint(self):
        look = T["hover_elevated"] if self._hovering and self.enabled else C["bg_elevated"]
        if look != self._look:
            self._look = look
            self.configure(fg_color=look)
            for part in self._parts:
                part.configure(bg=look)

    def _icon_picture(self, name, color):
        key = (name, color)
        if key not in self._pictures:
            self._pictures[key] = plain_icon(self, name, color, 15)
        return self._pictures[key]

    def _show_value(self):
        text = next((t for k, t in self.items if k == self.value), str(self.value))
        if self._label.cget("text") != text:
            self._label.configure(text=text)
        color = self.colors.get(self.value, C["text"])
        if self._label.cget("fg") != color:
            self._label.configure(fg=color)
        if self.value in self.icons:
            self._icon_label.configure(image=self._icon_picture(*self.icons[self.value]))
            self._icon_label.grid(row=0, column=1, padx=(10, 0))
            self._label.grid_configure(padx=(8, 4))
        else:
            self._icon_label.grid_forget()
            self._label.grid_configure(padx=(10, 4))

    def open(self):
        self.menu.open(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height() + 2)

    def _chosen(self, text):
        key = next((k for k, t in self.items if t == text), None)
        if key is None:
            return
        self.set(key)
        if self.on_choose:
            self.on_choose(key)

    def set(self, value):
        self.value = value
        self._show_value()

    def get(self):
        return self.value

    def set_items(self, items):
        """Новые надписи (другой язык)."""
        self.items = list(items)
        self.menu.configure(values=[text for _k, text in self.items])
        self._break_columns()
        self._show_value()

    def destroy(self):
        try:
            self.menu.destroy()  # меню живёт у окна, а не у списка: убираем вместе со списком
        except tk.TclError:
            pass
        super().destroy()


# Значок диалога: иконка, её цвет, цвет подложки; кнопка подтверждения по умолчанию (вид и иконка)
DIALOG_KINDS = {
    "danger": dict(icon="trash-2", color=C["danger_text"], bg=T["danger_on_surface"],
                   button="danger_solid", button_icon="trash-2"),
    "warning": dict(icon="triangle-alert", color=C["warning"], bg=T["warning_on_surface"],
                    button="save", button_icon="save"),
    "info": dict(icon="info", color=C["blue_text"], bg=T["blue_icon_bg"], button="blue", button_icon=None),
}


class DialogBody(ctk.CTkFrame):
    """Содержимое диалога подтверждения (экран 8): значок 40×40 в цветной подложке, заголовок, текст, кнопки справа.
    discard_text — третья кнопка слева красным текстом («Не сохранять»). Сам по себе не окно: окно — ConfirmDialog."""

    def __init__(self, master, title, text, confirm_text, cancel_text, kind="danger", on_confirm=None,
                 on_cancel=None, discard_text=None, on_discard=None, confirm_kind=None, confirm_icon=None,
                 wraplength=380, **kwargs):
        kwargs.setdefault("fg_color", C["bg_surface"])
        kwargs.setdefault("corner_radius", S["radius_dialog"])
        super().__init__(master, **kwargs)
        look = DIALOG_KINDS[kind]
        self.grid_columnconfigure(1, weight=1)

        badge = ctk.CTkFrame(self, width=40, height=40, corner_radius=10, fg_color=look["bg"])
        badge.grid(row=0, column=0, rowspan=2, sticky="n", padx=(20, 14), pady=(20, 0))
        badge.grid_propagate(False)
        ctk.CTkLabel(badge, text="", image=icon(look["icon"], look["color"], 20)).place(relx=0.5, rely=0.5,
                                                                                     anchor="center")
        ctk.CTkLabel(self, text=title, font=F["dialog_title"], text_color=C["text"], anchor="w",
                     justify="left").grid(row=0, column=1, sticky="w", padx=(0, 20), pady=(20, 6))
        ctk.CTkLabel(self, text=text, font=F["text"], text_color=C["text_secondary"], anchor="w", justify="left",
                     wraplength=wraplength).grid(row=1, column=1, sticky="w", padx=(0, 20))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20, pady=20)
        if discard_text:
            Button(row, discard_text, kind="ghost_danger", height=S["button_height_footer"], pad_x=12,
                   command=on_discard).pack(side="left")
        self.confirm_button = Button(row, confirm_text, kind=confirm_kind or look["button"],
                                     icon_name=confirm_icon if confirm_icon is not None else look["button_icon"],
                                     icon_size=14, height=S["button_height_footer"], command=on_confirm)
        self.confirm_button.pack(side="right")
        self.cancel_button = Button(row, cancel_text, kind="secondary", height=S["button_height_footer"],
                                    command=on_cancel)
        self.cancel_button.pack(side="right", padx=(0, 10))


class ConfirmDialog(ctk.CTkToplevel):
    """Модальное окно подтверждения: «Удалить все правила?», «Сохранить изменения?» и т.п.
    Закрытие крестиком или Esc — то же, что «Отмена». Обработчик вызывается после закрытия окна."""

    def __init__(self, master, title, text, confirm_text, on_confirm=None, kind="danger", lang="RU",
                 cancel_text=None, on_cancel=None, discard_text=None, on_discard=None, confirm_kind=None,
                 confirm_icon=None):
        root = master.winfo_toplevel()
        super().__init__(root, fg_color=C["bg_surface"])
        self.withdraw()
        self.title(title)
        self.resizable(False, False)
        self.transient(root)
        self._handlers = {"confirm": on_confirm, "cancel": on_cancel, "discard": on_discard}
        self.body = DialogBody(self, title, text, confirm_text, cancel_text or get_text(lang, "btn_cancel"),
                               kind=kind, discard_text=discard_text, confirm_kind=confirm_kind,
                               confirm_icon=confirm_icon, on_confirm=lambda: self._finish("confirm"),
                               on_cancel=lambda: self._finish("cancel"),
                               on_discard=lambda: self._finish("discard"), corner_radius=0)
        self.body.pack(fill="both", expand=True)
        self._done = False
        self.protocol("WM_DELETE_WINDOW", lambda: self._finish("cancel"))
        self.bind("<Escape>", lambda _e: self._finish("cancel"))
        present_window(self, lambda: self._place_centered(root), hidden=lambda: self._done,
                       on_shown=lambda: self._grab_when_visible(20))

    def _place_centered(self, root):
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        ax, ay, aw, ah = anchor_area(root)
        x = ax + (aw - w) // 2
        y = ay + (ah - h) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _grab_when_visible(self, tries):
        """Сделать окно модальным, когда оно уже на экране. Без wait_visibility: в Windows оно может не дождаться
        события и держать вложенный цикл. Не стало видно за 1 с — окно просто остаётся немодальным."""
        if self._done:
            return
        try:
            if self.winfo_viewable():
                self.grab_set()
                self.body.cancel_button.focus_set()
            elif tries > 0:
                self.after(50, self._grab_when_visible, tries - 1)
        except tk.TclError:
            pass

    def close(self):
        """Закрыть без ответа (вопрос устарел: например, бот уже решил сам)."""
        if self._done:
            return
        self._done = True
        try:
            self.grab_release()
            self.destroy()
        except tk.TclError:
            pass

    @property
    def done(self):
        return self._done

    def _finish(self, result):
        if self._done:  # двойной щелчок или Esc после кнопки — второй раз не обрабатываем
            return
        self._done = True
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
        handler = self._handlers.get(result)
        if handler:
            handler()


# Значки уведомлений: иконка и её цвет
TOAST_KINDS = {
    "success": ("check", C["success"]),
    "deleted": ("trash-2", C["text_secondary"]),
    "info": ("info", C["blue_text"]),
    "warning": ("triangle-alert", C["warning"]),
    "error": ("triangle-alert", C["danger_text"]),
}


class ToastBody(ctk.CTkFrame):
    """Содержимое уведомления (экран 8): значок, текст, кнопка действия («Вернуть»), крестик."""

    def __init__(self, master, text, kind="success", action_text=None, on_action=None, on_close=None, **kwargs):
        kwargs.setdefault("bg_color", "transparent")
        super().__init__(master, height=S["toast_height"], fg_color=C["bg_elevated"], border_width=1,
                         border_color=C["border_strong"], corner_radius=8, **kwargs)
        name, color = TOAST_KINDS[kind]
        ctk.CTkLabel(self, text="", image=icon(name, color, 16), width=16).pack(side="left", padx=(14, 10), pady=4)
        ctk.CTkLabel(self, text=text, font=F["text"], text_color=C["text"]).pack(side="left", pady=4)
        if action_text:
            Button(self, action_text, kind="link", height=28, pad_x=10, border_width=1,
                   border_color=C["border_strong"], font=F["button_bold"], command=on_action).pack(
                side="left", padx=(14, 0), pady=7)
        IconButton(self, "x", size=28, icon_size=13, icon_color=C["text_muted"], fg_color="transparent",
                   hover_color=C["bg_surface"], border_width=0, command=on_close).pack(side="left", padx=(6, 8))


class Toast:
    """Короткое уведомление в правом нижнем углу окна программы, на 4 с. Несколько уведомлений встают друг над другом.
    Окно программы свёрнуто — уведомление не показывается (не закрывать им игру)."""

    _open = []

    def __init__(self, master, text, kind="success", action_text=None, on_action=None, duration=None):
        self.root = master.winfo_toplevel()
        self.on_action = on_action
        self.top = None
        if self.root.state() != "normal" and self.root.state() != "zoomed":
            return
        self.top = _frameless_window(self.root)
        ToastBody(self.top, text, kind=kind, action_text=action_text, on_action=self._action,
                  on_close=self.close, bg_color=_CORNER_COLOR).pack()
        Toast._open.append(self)
        Toast._restack(self.root)
        self.top.deiconify()
        self.top.after(duration or S["toast_ms"], self.close)

    @classmethod
    def close_all(cls, root=None):
        """Закрыть все уведомления (при закрытии окна программы)."""
        for toast in list(cls._open):
            if root is None or toast.root is root:
                toast.close()

    def _action(self):
        self.close()
        if self.on_action:
            self.on_action()

    def close(self):
        if self.top is None:
            return
        try:
            self.top.destroy()
        except tk.TclError:
            pass
        self.top = None
        if self in Toast._open:
            Toast._open.remove(self)
        Toast._restack(self.root)

    @classmethod
    def _restack(cls, root):
        """Расставить открытые уведомления окна снизу вверх у правого нижнего угла."""
        try:
            right = root.winfo_rootx() + root.winfo_width() - 24
            bottom = root.winfo_rooty() + root.winfo_height() - 24
        except tk.TclError:
            return
        for toast in reversed([t for t in cls._open if t.root is root and t.top is not None]):
            try:
                toast.top.update_idletasks()
                w, h = toast.top.winfo_reqwidth(), toast.top.winfo_reqheight()
                toast.top.geometry(f"+{right - w}+{bottom - h}")
            except tk.TclError:
                continue
            bottom -= h + 10
