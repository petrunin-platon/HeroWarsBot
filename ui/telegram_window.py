"""Окно «Настройки Telegram» нового окна программы (задача 15, шаг 5б; макета нет — в стиле окон подтверждения).

Вместо старого ui/telegram_dialog.py (его оставляем старому окну). Что умеет — как старое: включить, токен бота (скрыт,
глаз — показать), Chat ID, «Вставить» (и правой кнопкой мыши; Ctrl+V работает и при русской раскладке).
Новое — «Проверить Telegram»: пробное сообщение с тем, что сейчас введено в окне, даже до сохранения (ваш ответ
22.10.2026). Запрос идёт в фоновом потоке (telegram_agent.call_api, не дольше telegram_agent.TIMEOUT), окно забирает
ответ через after — окно не замирает. Ответ — под кнопкой: «Сообщение ушло» или ошибка (токен в ней скрыт).
«Применить» — on_apply({"active", "token", "chat_id"}): меняет форму мастера правил, в profile.yml пишет
«Сохранить настройки» (ваш ответ, сверка 4.1). Крестик, Esc и «Отмена» — закрыть без изменений.
"""
import threading
import tkinter as tk

import customtkinter as ctk

import telegram_agent
import telegram_report
from i18n import get_text
from ui import theme
from ui.icons import icon
from ui.widgets import Button, Field, IconButton, Switch, anchor_area, present_window

C = theme.COLORS
T = theme.TINTS
F = theme.FONTS
S = theme.SIZES

WIDTH = 500          # ширина окна
POLL_MS = 100
ERROR_CHARS = 60     # длинную ошибку requests обрезаем: ответ — не больше двух строк справа от кнопки
NOTE_WIDTH = 230     # подпись «Записать в файл…» слева от кнопок
V_KEYCODE = 86       # клавиша V в Windows: Ctrl+V при русской раскладке Tk не узнаёт как «вставить»


def send_check(token, chat_id, lang):
    """Пробное сообщение. (удалось, ошибка или None). Ошибок не бросает (call_api)."""
    _result, error = telegram_agent.call_api(token, "sendMessage", data={
        "chat_id": chat_id, "text": telegram_report.check_message(lang), "parse_mode": "HTML"})
    return error is None, error


class TelegramWindow(ctk.CTkToplevel):
    def __init__(self, master, lang, data, on_apply, sender=send_check):
        root = master.winfo_toplevel()
        super().__init__(root, fg_color=C["bg_surface"])
        self.withdraw()
        self.lang = lang
        self.on_apply = on_apply
        self.sender = sender
        self._done = False
        self._poll_id = None
        self._answer = None        # ответ фонового потока: (удалось, ошибка)
        self._hidden_token = True
        self.title(self.text("tw_title"))
        self.resizable(False, False)
        self.transient(root)
        self.grid_columnconfigure(0, weight=1)
        self._build_header()
        self._build_body(data)
        self._build_footer()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _e: self.close())
        present_window(self, lambda: self._place_centered(root), hidden=lambda: self._done,
                       on_shown=lambda: self._grab_when_visible(20))

    def text(self, key):
        return get_text(self.lang, key)

    # ── Части окна ──────────────────────────────────────────────────────────
    def _build_header(self):
        head = ctk.CTkFrame(self, fg_color="transparent", width=10, height=10)
        head.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 0))
        head.grid_columnconfigure(1, weight=1)
        badge = ctk.CTkFrame(head, width=40, height=40, corner_radius=10, fg_color=T["blue_icon_bg"])
        badge.grid(row=0, column=0, rowspan=2, padx=(0, 14))
        badge.grid_propagate(False)
        ctk.CTkLabel(badge, text="", image=icon("send", C["blue_text"], 20)).place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(head, text=self.text("tw_title"), font=F["dialog_title"], text_color=C["text"], anchor="w",
                     height=22).grid(row=0, column=1, sticky="sw")
        ctk.CTkLabel(head, text=self.text("tw_sub"), font=F["label"], text_color=C["text_secondary"], anchor="w",
                     height=16).grid(row=1, column=1, sticky="nw", pady=(2, 0))

    def _build_body(self, data):
        body = ctk.CTkFrame(self, fg_color="transparent", width=10, height=10)
        body.grid(row=1, column=0, sticky="ew", padx=20, pady=(18, 0))
        body.grid_columnconfigure(0, weight=1, minsize=WIDTH - 40)

        switch_row = ctk.CTkFrame(body, fg_color="transparent", width=10, height=10)
        switch_row.grid(row=0, column=0, sticky="ew")
        switch_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(switch_row, text=self.text("tw_enable"), font=F["body_bold"], text_color=C["text"], anchor="w",
                     height=18).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(switch_row, text=self.text("tw_enable_sub"), font=F["label"], text_color=C["text_muted"],
                     anchor="w", height=16).grid(row=1, column=0, sticky="w", pady=(2, 0))
        self.active = Switch(switch_row, value=bool(data.get("active")))
        self.active.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))
        tk.Frame(body, height=1, bg=C["border"]).grid(row=1, column=0, sticky="ew", pady=14)

        self.token = Field(body, label=self.text("tw_token"), value=str(data.get("token") or ""), width=10)
        self.token.grid(row=2, column=0, sticky="ew")
        self.token.entry.configure(show="•")
        self.eye = IconButton(self.token, "eye", size=S["control_height"], icon_size=15, fg_color=C["bg_elevated"],
                              hover_color=T["hover_elevated"], tooltip=lambda: self.text("tw_show"),
                              command=self.toggle_token)
        self.eye.grid(row=1, column=1, padx=(8, 0))
        self._paste_button(self.token).grid(row=1, column=2, padx=(8, 0))

        self.chat = Field(body, label=self.text("tw_chat"), value=str(data.get("chat_id") or ""), width=10)
        self.chat.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self._paste_button(self.chat).grid(row=1, column=1, columnspan=2, sticky="e", padx=(8, 0))

        self.paste_menu = tk.Menu(self, tearoff=False, bg=C["bg_elevated"], fg=C["text"],
                                  activebackground=C["blue_button"], activeforeground=C["white"], bd=0)
        self.paste_menu.add_command(label=self.text("tw_paste"), command=lambda: self.paste(self._menu_field))
        self._menu_field = None
        for field in (self.token, self.chat):
            field.entry.bind("<Button-3>", lambda e, f=field: self._show_paste_menu(e, f), add="+")
            field.entry.bind("<Control-KeyPress>", lambda e, f=field: self._ctrl_key(e, f), add="+")

        # Ответ проверки — справа от кнопки, не выше её (до двух строк; замечание к шагу 5б)
        check = tk.Frame(body, bg=C["bg_surface"])
        check.grid(row=4, column=0, sticky="ew", pady=(16, 0))
        check.grid_columnconfigure(1, weight=1)
        self.check_button = Button(check, self.text("tw_check"), kind="secondary", icon_name="send", icon_size=15,
                                   pad_x=12, command=self.check)
        self.check_button.configure(image=icon("send", C["blue_text"], 15))
        self.check_button.grid(row=0, column=0, sticky="w")
        self.check_label = ctk.CTkLabel(check, text="", font=F["label"], text_color=C["text_secondary"], anchor="w",
                                        justify="left", height=S["control_height"], compound="left")
        self.check_label.grid(row=0, column=1, sticky="ew", padx=(12, 0))
        check.bind("<Configure>", self._wrap_check, add="+")

    def _wrap_check(self, _event=None):
        """Ответ проверки — по ширине места справа от кнопки (в CTkLabel wraplength — без масштаба Windows)."""
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        free = (self.check_label.master.winfo_width() - self.check_button.winfo_width()) / scale - 30
        width = max(120, int(free))
        if self.check_label.cget("wraplength") != width:
            self.check_label.configure(wraplength=width)

    def _paste_button(self, field):
        return Button(field, self.text("tw_paste"), kind="secondary", height=S["control_height"], pad_x=10,
                      command=lambda: self.paste(field))

    def _build_footer(self):
        tk.Frame(self, height=1, bg=C["border"]).grid(row=2, column=0, sticky="ew", pady=(18, 0))
        footer = ctk.CTkFrame(self, fg_color="transparent", width=10, height=10)
        footer.grid(row=3, column=0, sticky="ew", padx=20, pady=16)
        footer.grid_columnconfigure(0, weight=1)
        # «Записать в файл…» — слева от кнопок, по центру по высоте (замечание к шагу 5б)
        self.note = ctk.CTkLabel(footer, text=self.text("tw_note"), font=F["label"], text_color=C["text_muted"],
                                 anchor="w", justify="left", wraplength=NOTE_WIDTH)
        self.note.grid(row=0, column=0, sticky="w", padx=(0, 12))
        self.cancel_button = Button(footer, self.text("btn_cancel"), kind="secondary",
                                    height=S["button_height_footer"], command=self.close)
        self.cancel_button.grid(row=0, column=1, padx=(0, 10))
        self.apply_button = Button(footer, self.text("btn_apply"), kind="blue", icon_name="check", icon_size=14,
                                   height=S["button_height_footer"], command=self.apply)
        self.apply_button.grid(row=0, column=2)

    # ── Поля ────────────────────────────────────────────────────────────────
    def toggle_token(self):
        self._hidden_token = not self._hidden_token
        self.token.entry.configure(show="•" if self._hidden_token else "")

    def _show_paste_menu(self, event, field):
        self._menu_field = field
        field.entry.focus_set()
        self.paste_menu.tk_popup(event.x_root, event.y_root)

    def _ctrl_key(self, event, field):
        """Ctrl+V при русской раскладке: Tk видит не «v», а русскую букву — вставляем сами."""
        if event.keycode == V_KEYCODE and event.keysym.lower() != "v":
            self.paste(field)
            return "break"
        return None

    def paste(self, field):
        if field is None:
            return
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return
        text = text.strip()
        entry = field.entry
        try:
            if entry.selection_present():
                entry.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        entry.insert("insert", text)
        entry.focus_set()

    def values(self):
        return {"active": self.active.is_on(), "token": self.token.get().strip(), "chat_id": self.chat.get().strip()}

    # ── «Проверить Telegram» ────────────────────────────────────────────────
    def check(self):
        if self._poll_id is not None:   # проверка уже идёт
            return
        data = self.values()
        if not data["token"] or not data["chat_id"]:
            self._show_check(False, self.text("tw_check_empty"))
            return
        self._answer = None
        self.check_button.set_enabled(False)
        self._show_check(None, self.text("tw_checking"))

        def run():
            try:
                self._answer = self.sender(data["token"], data["chat_id"], self.lang)
            except Exception as e:   # sender ошибок не бросает, но окно не должно ждать вечно
                self._answer = (False, str(e))
        threading.Thread(target=run, daemon=True).start()
        self._poll_id = self.after(POLL_MS, self._poll_check)

    def _poll_check(self):
        self._poll_id = None
        if self._done:
            return
        if self._answer is None:
            try:
                self._poll_id = self.after(POLL_MS, self._poll_check)
            except tk.TclError:   # окно программы уже закрыли
                pass
            return
        ok, error = self._answer
        self.check_button.set_enabled(True)
        if ok:
            self._show_check(True, self.text("tw_check_ok"))
        else:
            error = str(error or "")
            if len(error) > ERROR_CHARS:
                error = error[:ERROR_CHARS - 1] + "…"
            self._show_check(False, self.text("tw_check_fail").format(error=error))

    def _show_check(self, ok, text):
        """ok: True — зелёный, False — красный, None — идёт проверка (серый)."""
        if ok is None:
            color, image = C["text_secondary"], None
        elif ok:
            color, image = C["success"], icon("check", C["success"], 14)
        else:
            color, image = C["danger_text"], icon("triangle-alert", C["danger_text"], 13)
        self.check_label.configure(text=(" " + text) if image else text, text_color=color, image=image)

    # ── Показ и закрытие ────────────────────────────────────────────────────
    @property
    def done(self):
        return self._done

    def _place_centered(self, root):
        """Только место, не размер: окно растёт само, когда под кнопкой появляется ответ проверки."""
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        ax, ay, aw, ah = anchor_area(root)
        self.geometry(f"+{max(0, ax + (aw - w) // 2)}+{max(0, ay + (ah - h) // 3)}")

    def _grab_when_visible(self, tries):
        """Как ConfirmDialog: модальное, когда уже на экране, без wait_visibility."""
        if self._done:
            return
        try:
            if self.winfo_viewable():
                self.grab_set()
            elif tries > 0:
                self.after(50, self._grab_when_visible, tries - 1)
        except tk.TclError:
            pass

    def apply(self):
        data = self.values()
        self.close()
        self.on_apply(data)

    def close(self):
        """Закрыть: остановить опрос проверки (поток сам закончится не позже telegram_agent.TIMEOUT)."""
        if self._done:
            return
        self._done = True
        if self._poll_id is not None:
            try:
                self.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None
        try:
            self.grab_release()
            self.destroy()
        except tk.TclError:
            pass
