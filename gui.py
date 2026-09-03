# gui.py
import sys
import ctypes
import subprocess 

# =====================================================================
# ЖИЗНЕННО ВАЖНО: АППАРАТНЫЙ ФИКС DPI WINDOWS
# ДОЛЖЕН БЫТЬ ДО ИМПОРТА ЛЮБЫХ БИБЛИОТЕК
# =====================================================================
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2) 
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
# =====================================================================

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# ИНТЕЛЛЕКТУАЛЬНЫЙ РОУТИНГ ДЛЯ .EXE (FORK PATTERN)
if "--bot-mode" in sys.argv:
    import main
    sys.exit(0)

import customtkinter as ctk
import os
from i18n import get_text
from ui.dashboard import DashboardFrame
from ui.rules_tab import RulesFrame
from ui.analytics_tab import AnalyticsFrame
from ui.statistics_tab import StatisticsFrame
from ui.about_tab import AboutFrame
from ui.guide_tab import GuideFrame

ctk.set_appearance_mode("Dark")  
ctk.set_default_color_theme("blue") 

# =====================================================================
# СЛОВАРЬ ЯЗЫКОВ (МАППИНГ)
# Здесь мы связываем красивое название языка с системным префиксом.
# Можешь добавлять любые языки в будущем!
# =====================================================================
LANGUAGE_MAP = {
    # СНГ и Глобальный
    "Русский": "RU",
    "English": "EN",
    "Беларуская": "BY",
    "Українська": "UK",
    
    # Европа
    "Deutsch": "DE",
    "Español": "ES",     # Испанский
    "Français": "FR",    # Французский
    "Polski": "PL",      # Польский
    
    # Ближний Восток / Латинская Америка
    "Português": "PT",   # Португальский (Бразилия)
    "Türkçe": "TR",      # Турецкий
    
    # Азия
    "中文": "ZH",          # Китайский
    "한국어": "KO",          # Корейский
    "日本語": "JA"           # Японский
}
# Обратный словарь (чтобы быстро найти название по префиксу при запуске)
REVERSE_LANG_MAP = {v: k for k, v in LANGUAGE_MAP.items()}
# =====================================================================

class HeroWarsLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.current_lang = "RU"

        self.title(get_text(self.current_lang, "app_title"))
        self.geometry("1000x580")
        self.resizable(False, False)
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        if os.path.exists("pause.flag"):
            os.remove("pause.flag")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.sidebar.grid_rowconfigure(7, weight=1) 

        self.lbl_sidebar_title = ctk.CTkLabel(self.sidebar, text=get_text(self.current_lang, "sidebar_title"), font=ctk.CTkFont(size=20, weight="bold"))
        self.lbl_sidebar_title.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.btn_dash = ctk.CTkButton(self.sidebar, text=get_text(self.current_lang, "btn_main"), command=lambda: self.select_frame("dash"))
        self.btn_dash.grid(row=1, column=0, padx=20, pady=10)
        
        self.btn_rules = ctk.CTkButton(self.sidebar, text=get_text(self.current_lang, "btn_rules"), command=lambda: self.select_frame("rules"))
        self.btn_rules.grid(row=2, column=0, padx=20, pady=10)

        self.btn_analytics = ctk.CTkButton(self.sidebar, text=get_text(self.current_lang, "btn_analytics"), command=lambda: self.select_frame("analytics"))
        self.btn_analytics.grid(row=3, column=0, padx=20, pady=10)

        self.btn_stats = ctk.CTkButton(self.sidebar, text=get_text(self.current_lang, "btn_stats"), command=lambda: self.select_frame("stats"))
        self.btn_stats.grid(row=4, column=0, padx=20, pady=10)

        self.btn_guide = ctk.CTkButton(self.sidebar, text=get_text(self.current_lang, "btn_guide"), command=lambda: self.select_frame("guide"))
        self.btn_guide.grid(row=5, column=0, padx=20, pady=10)

        self.btn_about = ctk.CTkButton(self.sidebar, text=get_text(self.current_lang, "btn_about"), command=lambda: self.select_frame("about"))
        self.btn_about.grid(row=6, column=0, padx=20, pady=10)

        # =====================================================================
        # НОВЫЙ ВЫПАДАЮЩИЙ СПИСОК ВМЕСТО КНОПОК RU И EN
        # =====================================================================
        self.lang_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.lang_frame.grid(row=8, column=0, pady=(0, 20), sticky="s")
        
        initial_lang_name = REVERSE_LANG_MAP.get(self.current_lang, "Русский")
        self.lang_var = ctk.StringVar(value=initial_lang_name)
        
        self.lang_dropdown = ctk.CTkOptionMenu(
            self.lang_frame, 
            values=list(LANGUAGE_MAP.keys()), 
            variable=self.lang_var,
            command=self.on_language_change,
            width=140
        )
        self.lang_dropdown.pack(pady=5, padx=20)
        # =====================================================================

        self.frames = {
            "dash": DashboardFrame(self, self),
            "rules": RulesFrame(self, self),
            "analytics": AnalyticsFrame(self, self),
            "stats": StatisticsFrame(self, self),
            "guide": GuideFrame(self, self),
            "about": AboutFrame(self, self)
        }

        self.select_frame("dash")
        self.set_language("RU", force=True)

    def select_frame(self, frame_name):
        if frame_name == "stats":
            self.frames["stats"].refresh_data()
            
        for f in self.frames.values():
            f.grid_forget()
        self.frames[frame_name].grid(row=0, column=1, sticky="nsew", padx=20, pady=0)

    # Перехватчик: получает красивое имя из меню и переводит его в префикс
    def on_language_change(self, choice):
        prefix = LANGUAGE_MAP.get(choice, "RU")
        self.set_language(prefix)

    def set_language(self, lang, force=False):
        if lang == self.current_lang and not force:
            return
            
        self.current_lang = lang
        
        # Обновляем текст в выпадающем списке (если язык установлен программно)
        display_name = REVERSE_LANG_MAP.get(lang, "Русский")
        self.lang_var.set(display_name)
        
        # Записываем красивый лог
        self.frames["dash"].append_log(f"[GUI] Язык интерфейса изменен: {display_name} ({lang})\n")
            
        self.title(get_text(lang, "app_title"))
        self.lbl_sidebar_title.configure(text=get_text(lang, "sidebar_title"))
        self.btn_dash.configure(text=get_text(lang, "btn_main"))
        self.btn_rules.configure(text=get_text(lang, "btn_rules"))
        self.btn_analytics.configure(text=get_text(lang, "btn_analytics"))
        self.btn_stats.configure(text=get_text(lang, "btn_stats"))
        self.btn_guide.configure(text=get_text(lang, "btn_guide"))
        self.btn_about.configure(text=get_text(lang, "btn_about"))
        
        for frame in self.frames.values():
            if hasattr(frame, 'update_language'):
                frame.update_language(lang)

    def on_closing(self):
        try:
            subprocess.run(["taskkill", "/F", "/IM", "scrcpy.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
            subprocess.run(["taskkill", "/F", "/IM", "adb.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
        except Exception:
            pass
        self.destroy()

if __name__ == "__main__":
    app = HeroWarsLauncher()
    app.mainloop()