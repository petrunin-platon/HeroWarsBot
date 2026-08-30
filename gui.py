# gui.py
import sys
import ctypes

# =====================================================================
# ЖИЗНЕННО ВАЖНО: АППАРАТНЫЙ ФИКС DPI WINDOWS
# ДОЛЖЕН БЫТЬ ДО ИМПОРТА ЛЮБЫХ БИБЛИОТЕК
# =====================================================================
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2) # PROCESS_PER_MONITOR_DPI_AWARE
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

        self.lang_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.lang_frame.grid(row=8, column=0, pady=(0, 20), sticky="s")
        
        self.btn_ru = ctk.CTkButton(self.lang_frame, text="RU", width=60, fg_color="#007bff", hover_color="#0056b3", command=lambda: self.set_language("RU"))
        self.btn_ru.grid(row=0, column=0, padx=5)

        self.btn_en = ctk.CTkButton(self.lang_frame, text="EN", width=60, fg_color="#444444", hover_color="#555555", command=lambda: self.set_language("EN"))
        self.btn_en.grid(row=0, column=1, padx=5)

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

    def set_language(self, lang, force=False):
        if lang == self.current_lang and not force:
            return
            
        self.current_lang = lang
        
        if lang == "RU":
            self.btn_ru.configure(fg_color="#007bff")
            self.btn_en.configure(fg_color="#444444")
            self.frames["dash"].append_log("[GUI] Выбран язык: Русский\n")
        else:
            self.btn_ru.configure(fg_color="#444444")
            self.btn_en.configure(fg_color="#007bff")
            self.frames["dash"].append_log("[GUI] Language selected: English\n")
            
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
        # ИСПРАВЛЕНИЕ: Гарантированно убиваем процесс бота перед выходом из GUI
        if "dash" in self.frames:
            self.frames["dash"].stop_bot()
            
        os.system("taskkill /f /im scrcpy.exe >nul 2>&1")
        os.system("adb kill-server >nul 2>&1")
        self.destroy()

if __name__ == "__main__":
    app = HeroWarsLauncher()
    app.mainloop()