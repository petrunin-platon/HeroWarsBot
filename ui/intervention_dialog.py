# ui/intervention_dialog.py
import customtkinter as ctk
import os
import yaml
import threading
from i18n import get_text
from telegram_agent import TelegramAgent

class InterventionDialog(ctk.CTkToplevel):
    def __init__(self, master, titan_data, callback, is_manual=False):
        super().__init__(master)
        
        self.callback = callback
        self.is_manual = is_manual
        lang = getattr(master, 'current_lang', 'RU')
        self.tg_agent = None
        
        self.title(get_text(lang, "sos_title"))
        self.geometry("600x370")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.grab_set()
        
        self.grid_columnconfigure(0, weight=1)
        
        self.lbl_alert = ctk.CTkLabel(self, text=get_text(lang, "sos_title"), font=ctk.CTkFont(size=20, weight="bold"), text_color="#dc3545")
        self.lbl_alert.grid(row=0, column=0, pady=(20, 10))
        
        self.lbl_msg = ctk.CTkLabel(self, text=get_text(lang, "sos_msg"), font=ctk.CTkFont(size=14), wraplength=450)
        self.lbl_msg.grid(row=1, column=0, pady=(0, 20))
        
        self.stats_frame = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.stats_frame.grid(row=2, column=0, padx=20, sticky="ew")
        
        for i, (titan, hp) in enumerate(titan_data.items()):
            color = "#dc3545" if hp < 40 else "#28a745"
            titan_name = get_text(lang, f"titan_{titan}")
            lbl = ctk.CTkLabel(self.stats_frame, text=f"➤ {titan_name.upper()}: {hp}% HP", font=ctk.CTkFont(size=14, weight="bold"), text_color=color)
            lbl.grid(row=i, column=0, padx=10, pady=5, sticky="w")
            
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=3, column=0, pady=25)
        
        self.btn_manual = ctk.CTkButton(self.btn_frame, text=get_text(lang, "sos_btn_manual"), fg_color="#007bff", hover_color="#0056b3", command=self.on_manual)
        self.btn_manual.grid(row=0, column=0, padx=10)
        
        # ДИНАМИЧЕСКАЯ КНОПКА (Откат невозможен при ручном бое)
        if self.is_manual:
            self.btn_rollback = ctk.CTkButton(self.btn_frame, text="🛑 Остановить бота", fg_color="#dc3545", hover_color="#c82333", text_color="white", command=self.on_stop)
        else:
            self.btn_rollback = ctk.CTkButton(self.btn_frame, text=get_text(lang, "sos_btn_rollback"), fg_color="#ffc107", text_color="black", hover_color="#e0a800", command=self.on_rollback)
            
        self.btn_rollback.grid(row=0, column=1, padx=10)
        
        self.btn_ignore = ctk.CTkButton(self.btn_frame, text=get_text(lang, "sos_btn_ignore"), fg_color="#6c757d", hover_color="#5a6268", command=self.on_ignore)
        self.btn_ignore.grid(row=0, column=2, padx=10)

        threading.Thread(target=self.load_telegram_and_send, args=(titan_data, lang), daemon=True).start()

    def load_telegram_and_send(self, titan_data, lang):
        token = ""
        chat_id = ""
        if os.path.exists("profile.yml"):
            try:
                with open("profile.yml", 'r', encoding='utf-8') as f:
                    profile = yaml.safe_load(f) or {}
                    tg = profile.get("settings", {}).get("telegram", {})
                    if tg.get("active", False):
                        token = tg.get("token", "")
                        chat_id = str(tg.get("chat_id", ""))
            except Exception as e:
                print(f"[GUI] Ошибка чтения profile.yml для Telegram: {e}")
                
        if token and chat_id:
            self.tg_agent = TelegramAgent(token, chat_id)
            msg = get_text(lang, "sos_title") + "\n\n"
            for titan, hp in titan_data.items():
                titan_name = get_text(lang, f"titan_{titan}")
                msg += f"➤ {titan_name.upper()}: {hp}% HP\n"
                
            msg_id = self.tg_agent.send_sos("temp_sos.png", msg, is_manual=self.is_manual)
            if msg_id:
                self.tg_agent.start_polling(msg_id, self.on_telegram_decision)

    def on_telegram_decision(self, decision):
        if decision == "manual":
            self.master.after(0, self.on_manual)
        elif decision == "rollback":
            self.master.after(0, self.on_rollback)
        elif decision == "stop":
            self.master.after(0, self.on_stop)
        elif decision == "ignore":
            self.master.after(0, self.on_ignore)

    def on_manual(self):
        if self.tg_agent: self.tg_agent.stop()
        self.grab_release()
        self.master.after(50, lambda: self.callback("manual"))
        self.destroy()
        
    def on_rollback(self):
        if self.tg_agent: self.tg_agent.stop()
        self.grab_release()
        self.master.after(50, lambda: self.callback("rollback"))
        self.destroy()
        
    def on_stop(self):
        if self.tg_agent: self.tg_agent.stop()
        self.grab_release()
        self.master.after(50, lambda: self.callback("stop"))
        self.destroy()
        
    def on_ignore(self):
        if self.tg_agent: self.tg_agent.stop()
        self.grab_release()
        self.master.after(50, lambda: self.callback("ignore"))
        self.destroy()
        
    def destroy(self):
        if self.tg_agent:
            self.tg_agent.stop()
        super().destroy()