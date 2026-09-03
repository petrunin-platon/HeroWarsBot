import customtkinter as ctk
from i18n import get_text

# Используем только внутренние (EN) ключи
ELEMENTS = {
    "earth": ["angus", "avalon", "eden", "silva", "verdok", "pallant"],
    "water": ["hyperion", "sigurd", "tidus", "nova", "mairi", "orm"],
    "fire": ["araji", "ignis", "acheron", "vulcan", "moloch", "alecto"],
    "light": ["rigel", "iyari", "lumira", "solaris", "amon"],
    "dark": ["mor", "tenebris", "brustar", "umbra", "keros"]
}

ALLOWED_ELEMENTS = {
    "earth": ["earth"],
    "water": ["water"],
    "fire": ["fire"],
    "mix": ["earth", "water", "fire", "light", "dark"],
    "all": ["earth", "water", "fire", "light", "dark"]
}

class TeamSelectorDialog(ctk.CTkToplevel):
    def __init__(self, master, callback, room_type="mix", context="rule", preselect_titan=None):
        super().__init__(master)
        
        self.callback = callback
        self.selected_titans = []
        self.buttons = {}
        # Запоминаем титана для предварительного выбора, но НЕ блокируем его
        self.preselect_titan = preselect_titan 
        lang = getattr(master, 'current_lang', 'RU')
        
        self.title(get_text(lang, "ts_title"))
        self.geometry("900x500")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        
        self.context = context 
        self.protocol("WM_DELETE_WINDOW", self.on_closing) 
        
        self.after(100, self.grab_set)
        
        self.lbl_title = ctk.CTkLabel(self, text=get_text(lang, "ts_title"), font=ctk.CTkFont(size=20, weight="bold"))
        self.lbl_title.pack(pady=(20, 5))
        
        self.lbl_counter = ctk.CTkLabel(self, text=get_text(lang, "ts_counter").format(count=0), font=ctk.CTkFont(size=14), text_color="yellow")
        self.lbl_counter.pack(pady=(0, 15))
        
        self.grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_frame.pack(padx=10, fill="both", expand=True)
        
        allowed = ALLOWED_ELEMENTS.get(room_type, ALLOWED_ELEMENTS["all"])
        
        col = 0
        for elem_key, titans_list in ELEMENTS.items():
            is_disabled = elem_key not in allowed
            elem_text = get_text(lang, f"elem_{elem_key}")
            
            lbl_element = ctk.CTkLabel(self.grid_frame, text=elem_text, font=ctk.CTkFont(size=14, weight="bold"), text_color="gray" if is_disabled else "white")
            lbl_element.grid(row=0, column=col, pady=(0, 10))
            
            row = 1
            for en_name in titans_list:
                titan_text = get_text(lang, f"titan_{en_name}")
                btn = ctk.CTkButton(
                    self.grid_frame, 
                    text=titan_text, 
                    width=140,
                    fg_color="#444444", 
                    text_color="white",
                    hover_color="#555555",
                    command=lambda e=en_name: self.toggle_titan(e)
                )
                
                if is_disabled:
                    btn.configure(fg_color="#2b2b2b", text_color="#555555", state="disabled")
                
                # Мягкий предвыбор без замочка
                if self.preselect_titan and en_name == self.preselect_titan:
                    self.selected_titans.append(en_name)
                    btn.configure(fg_color="#007bff")
                    
                btn.grid(row=row, column=col, padx=8, pady=6)
                self.buttons[en_name] = btn
                row += 1
            col += 1
            
        btn_text = get_text(lang, "ts_btn_apply") if context == "rule" else get_text(lang, "ts_btn_rollback")
        self.btn_submit = ctk.CTkButton(self, text=btn_text, font=ctk.CTkFont(weight="bold"), fg_color="#28a745", hover_color="#218838", state="disabled", command=self.submit)
        self.btn_submit.pack(pady=20, fill="x", padx=100)
        
        self._update_counter_and_btn()

    def toggle_titan(self, en_name):
        # Ограничение на клик снято, теперь любой титан может быть отжат
        btn = self.buttons[en_name]
        if en_name in self.selected_titans:
            self.selected_titans.remove(en_name)
            btn.configure(fg_color="#444444")
        else:
            if len(self.selected_titans) < 5:
                self.selected_titans.append(en_name)
                btn.configure(fg_color="#007bff")
                
        self._update_counter_and_btn()
        
    def _update_counter_and_btn(self):
        count = len(self.selected_titans)
        lang = getattr(self.master, 'current_lang', 'RU')
        
        if 3 <= count <= 5:
            self.lbl_counter.configure(text=get_text(lang, "ts_counter").format(count=count), text_color="#28a745")
            self.btn_submit.configure(state="normal")
        else:
            self.lbl_counter.configure(text=get_text(lang, "ts_counter").format(count=count), text_color="yellow")
            self.btn_submit.configure(state="disabled")

    def submit(self):
        self.grab_release()
        self.master.after(50, lambda: self.callback(self.selected_titans))
        self.destroy()

    def on_closing(self):
        self.grab_release()
        if getattr(self, "context", "") == "rollback":
            self.master.after(50, lambda: self.callback(["STOP_BOT"]))
        else:
            self.master.after(50, lambda: self.callback([]))
        self.destroy()