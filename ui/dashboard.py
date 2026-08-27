# ui/dashboard.py
import customtkinter as ctk
import tkinter as tk
import threading
import subprocess
import sys
import os
import datetime
import webbrowser
import time
import json
import pygetwindow as gw
import pyautogui
from environment import launch_scrcpy, calibrate_window
from i18n import get_text

class DashboardFrame(ctk.CTkFrame):
    def __init__(self, master, controller, **kwargs):
        super().__init__(master, corner_radius=10, fg_color="transparent", **kwargs)
        self.controller = controller 
        self.bot_process = None
        self.action_state = "start"

        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure(3, weight=1)

        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=2, pady=(15, 10), sticky="ew")
        header_frame.grid_columnconfigure(1, weight=1)

        self.lbl_title = ctk.CTkLabel(header_frame, text="", font=ctk.CTkFont(size=24, weight="bold"))
        self.lbl_title.grid(row=0, column=0, sticky="w", padx=5)
        
        phone_frame = ctk.CTkFrame(header_frame, fg_color="#1e1e1e", corner_radius=5)
        phone_frame.grid(row=0, column=1, sticky="e")
        self.lbl_device = ctk.CTkLabel(phone_frame, text="")
        self.lbl_device.pack(side="left", padx=10)
        
        self.btn_wake = ctk.CTkButton(phone_frame, text="", width=90, height=24, fg_color="#28a745", hover_color="#218838", command=self.wake_phone)
        self.btn_wake.pack(side="left", padx=5, pady=5)
        
        self.btn_sleep = ctk.CTkButton(phone_frame, text="", width=90, height=24, fg_color="#6c757d", hover_color="#5a6268", command=self.sleep_phone)
        self.btn_sleep.pack(side="left", padx=5, pady=5)
        
        self.btn_restart = ctk.CTkButton(phone_frame, text="", width=110, height=24, fg_color="#444444", hover_color="#555555", command=self.restart_scrcpy)
        self.btn_restart.pack(side="left", padx=5, pady=5)

        self.btn_launch_scrcpy = ctk.CTkButton(self, text="", height=40, command=self.launch_phone)
        self.btn_launch_scrcpy.grid(row=1, column=0, padx=(5, 5), pady=(5, 5), sticky="ew")

        self.btn_action = ctk.CTkButton(self, text="", height=40, fg_color="transparent", border_color="gray", border_width=1, text_color="gray", state="disabled", command=self.handle_action_btn)
        self.btn_action.grid(row=1, column=1, padx=(5, 5), pady=(5, 5), sticky="ew")

        self.btn_pause = ctk.CTkButton(self, text="", height=40, fg_color="transparent", border_color="gray", border_width=1, text_color="gray", state="disabled", command=self.toggle_pause)
        self.btn_pause.grid(row=2, column=0, padx=(5, 5), pady=(5, 10), sticky="ew")

        self.btn_stop = ctk.CTkButton(self, text="", height=40, fg_color="transparent", border_color="gray", border_width=1, text_color="gray", state="disabled", command=self.stop_bot)
        self.btn_stop.grid(row=2, column=1, padx=(5, 5), pady=(5, 10), sticky="ew")

        self.log_box = ctk.CTkTextbox(self, wrap="word", font=("Consolas", 12), fg_color="#1e1e1e", text_color="#00ff00")
        self.log_box.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(0, 10), padx=5)
        
        # Настраиваем защиту от редактирования + Контекстное меню
        self.setup_readonly_and_menu(self.log_box)
        self.log_box.insert("end", "[СИСТЕМА] Интерфейс загружен. Ожидание подключения...\n")

        log_footer = ctk.CTkFrame(self, fg_color="transparent")
        log_footer.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 15), padx=5)
        
        self.btn_export = ctk.CTkButton(log_footer, text="", fg_color="#444444", hover_color="#555555", command=self.export_log)
        self.btn_export.pack(side="left", padx=(0, 5))
        self.btn_send = ctk.CTkButton(log_footer, text="", fg_color="#007bff", hover_color="#0056b3", command=self.send_log_to_author)
        self.btn_send.pack(side="left", padx=5)
        self.btn_clear = ctk.CTkButton(log_footer, text="", fg_color="transparent", border_color="#dc3545", border_width=1, text_color="#dc3545", hover_color="#4a151b", command=self.clear_log)
        self.btn_clear.pack(side="right", padx=(5, 0))

    def setup_readonly_and_menu(self, textbox):
        def prevent_edit(event):
            # Разрешаем копирование (Ctrl+C, Cmd+C) и выделение (Ctrl+A, Cmd+A)
            if event.state & 0x0004 or event.state & 0x0008:
                if event.keysym.lower() in ['c', 'a']:
                    return None
            # Разрешаем навигацию (Стрелки, Home, End, PageUp, PageDown)
            if event.keysym in ['Up', 'Down', 'Left', 'Right', 'Prior', 'Next', 'Home', 'End']:
                return None
            # Жестко блокируем все остальные клавиши (ввод текста, Backspace, Delete, Enter)
            return "break"
            
        textbox.bind("<Key>", prevent_edit)
        textbox.bind("<<Paste>>", lambda e: "break")
        textbox.bind("<<Cut>>", lambda e: "break")

        # Создаем нативное контекстное меню Tkinter
        self.context_menu = tk.Menu(self, tearoff=False, bg="#2b2b2b", fg="white", activebackground="#007bff")
        lang = getattr(self.controller, 'current_lang', 'RU')
        self.context_menu.add_command(label=get_text(lang, "ctx_copy"), command=lambda: self.copy_text(textbox))

        textbox.bind("<Button-3>", lambda event: self.show_context_menu(event, textbox))

    def show_context_menu(self, event, textbox):
        try:
            # Меню появится, только если есть выделенный текст
            if textbox.get(tk.SEL_FIRST, tk.SEL_LAST):
                self.context_menu.tk_popup(event.x_root, event.y_root)
        except tk.TclError:
            pass

    def copy_text(self, textbox):
        try:
            selected_text = textbox.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.clipboard_clear()
            self.clipboard_append(selected_text)
        except tk.TclError:
            pass

    def update_language(self, lang):
        self.lbl_title.configure(text=get_text(lang, "dash_title"))
        self.lbl_device.configure(text=get_text(lang, "dash_device"))
        
        self.btn_wake.configure(text=get_text(lang, "dash_btn_wake"))
        self.btn_sleep.configure(text=get_text(lang, "dash_btn_sleep"))
        self.btn_restart.configure(text=get_text(lang, "dash_btn_restart"))
        
        self.btn_launch_scrcpy.configure(text=get_text(lang, "dash_btn_connect"))

        if self.action_state == "start":
            self.btn_action.configure(text=get_text(lang, "dash_btn_start"))
        elif self.action_state == "working":
            self.btn_action.configure(text=get_text(lang, "dash_btn_working"))
        elif self.action_state == "continue":
            self.btn_action.configure(text=get_text(lang, "dash_btn_continue"))

        if os.path.exists("pause.flag"):
            self.btn_pause.configure(text=get_text(lang, "dash_btn_unpause"))
        else:
            self.btn_pause.configure(text=get_text(lang, "dash_btn_pause"))

        self.btn_stop.configure(text=get_text(lang, "dash_btn_stop"))
        self.btn_export.configure(text=get_text(lang, "dash_btn_save_log"))
        self.btn_send.configure(text=get_text(lang, "dash_btn_send_log"))
        self.btn_clear.configure(text=get_text(lang, "dash_btn_clear_log"))
        
        # Обновляем текст в контекстном меню
        self.context_menu.entryconfigure(0, label=get_text(lang, "ctx_copy"))

    def wake_phone(self):
        self.append_log("[СИСТЕМА] Пробуждение экрана...\n")
        subprocess.Popen(["adb", "shell", "input", "keyevent", "224"], creationflags=0x08000000)
        subprocess.Popen(["adb", "shell", "input", "swipe", "500", "1000", "500", "200"], creationflags=0x08000000)
        try:
            windows = gw.getWindowsWithTitle("HeroWarsBot_Arena")
            if windows:
                win = windows[0]
                if win.isMinimized: win.restore()
                win.activate()
                time.sleep(0.2)
                pyautogui.hotkey('alt', 'shift', 'o')
        except Exception:
            pass

    def sleep_phone(self):
        self.append_log("[СИСТЕМА] Выключаю физический дисплей (игра продолжит работать)...\n")
        try:
            windows = gw.getWindowsWithTitle("HeroWarsBot_Arena")
            if windows:
                win = windows[0]
                if win.isMinimized: win.restore()
                win.activate()
                time.sleep(0.2)
                pyautogui.hotkey('alt', 'o')
                self.append_log("[ИНФО] Экран телефона погашен для экономии батареи!\n")
            else:
                self.append_log("[ОШИБКА] Окно трансляции не найдено.\n")
        except Exception as e:
            self.append_log(f"[ОШИБКА] Не удалось отправить команду: {e}\n")

    def restart_scrcpy(self):
        self.append_log("[ADB] Перезапуск scrcpy...\n")
        os.system("taskkill /f /im scrcpy.exe >nul 2>&1")
        time.sleep(1)
        self.launch_phone()

    def append_log(self, text):
        self.log_box.insert("end", text)
        self.log_box.see("end")

    def clear_log(self):
        self.log_box.delete("1.0", "end")

    def export_log(self):
        log_text = self.log_box.get("1.0", "end")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        default_name = f"gui_log_{timestamp}.txt"
        
        if not os.path.exists("logs"): os.makedirs("logs")
            
        filepath = ctk.filedialog.asksaveasfilename(
            initialdir=os.path.abspath("logs"),
            initialfile=default_name,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("=== ЛОГ ТЕРМИНАЛА (GUI) ===\n")
                f.write(log_text)
            self.append_log(f"\n[СИСТЕМА] Лог терминала сохранен: {filepath}\n")
            return filepath
        return None

    def send_log_to_author(self):
        filepath = self.export_log()
        if not filepath:
            self.append_log("[СИСТЕМА] Сохранение лога отменено.\n")
            return
            
        self.append_log("[СИСТЕМА] Открываю почтовый клиент ОС...\n")
        body = "Привет, Platon! Вот логи сессии.%0A%0A(Пожалуйста, прикрепите файлы gui_log_...txt и battle_log.csv к этому письму)"
        webbrowser.open(f"mailto:Petrunin.platon@gmail.com?subject=HeroWars Bot Log Report&body={body}")

    def start_scrcpy_monitor(self):
        def task():
            while True:
                time.sleep(2)
                try:
                    output = subprocess.check_output('tasklist /FI "IMAGENAME eq scrcpy.exe"', text=True, creationflags=0x08000000)
                    if "scrcpy.exe" not in output:
                        self.action_state = "start"
                        lang = getattr(self.controller, 'current_lang', 'RU')
                        self.after(0, lambda: self.btn_action.configure(text=get_text(lang, "dash_btn_start"), state="disabled", fg_color="transparent", border_width=1, text_color="gray"))
                        self.after(0, lambda: self.btn_launch_scrcpy.configure(state="normal"))
                        if self.bot_process:
                            self.stop_bot()
                        break
                except Exception:
                    break
        threading.Thread(target=task, daemon=True).start()

    def launch_phone(self):
        self.btn_launch_scrcpy.configure(state="disabled")
        os.system("taskkill /f /im scrcpy.exe >nul 2>&1")
        self.append_log("[СИСТЕМА] Вызов scrcpy... Открой игру на телефоне и зайди в коридор.\n")
        def task():
            if launch_scrcpy("HeroWarsBot_Arena"):
                self.after(0, lambda: self.btn_action.configure(state="normal", fg_color="#28a745", border_width=0, text_color="white"))
                self.start_scrcpy_monitor()
            else:
                self.after(0, lambda: self.append_log("[ОШИБКА] Не удалось запустить scrcpy!\n"))
                self.after(0, lambda: self.btn_launch_scrcpy.configure(state="normal"))
        threading.Thread(target=task, daemon=True).start()

    def handle_action_btn(self):
        if self.action_state == "start": 
            self.start_bot()
        elif self.action_state == "continue": 
            self.continue_bot()

    def start_bot(self):
        self.action_state = "working"
        lang = getattr(self.controller, 'current_lang', 'RU')
        self.btn_action.configure(text=get_text(lang, "dash_btn_working"), state="disabled", fg_color="transparent", border_width=1, text_color="gray")
        self.btn_pause.configure(state="normal", fg_color="#d39e00", border_width=0, text_color="white")
        self.btn_stop.configure(state="normal", fg_color="#dc3545", border_width=0, text_color="white")
        
        self.append_log("[СИСТЕМА] Калибровка окна игры...\n")
        calibrate_window("HeroWarsBot_Arena", 956, 457)
        
        bot_env = os.environ.copy()
        bot_env["HEROWARS_LANG"] = lang
        
        self.bot_process = subprocess.Popen(
            [sys.executable, "-X", "utf8", "-u", "main.py"], 
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, encoding='utf-8',
            creationflags=0x08000000,
            env=bot_env
        )
        threading.Thread(target=self.monitor_bot_output, daemon=True).start()

    def continue_bot(self):
        self.action_state = "working"
        lang = getattr(self.controller, 'current_lang', 'RU')
        self.btn_action.configure(text=get_text(lang, "dash_btn_working"), state="disabled", fg_color="transparent", border_width=1, text_color="gray")
        if self.bot_process and self.bot_process.poll() is None:
            self.bot_process.stdin.write("\n")
            self.bot_process.stdin.flush()

    def monitor_bot_output(self):
        while self.bot_process and self.bot_process.poll() is None:
            line = self.bot_process.stdout.readline()
            if line:
                if "[SOS_TRIGGER]" in line:
                    if "TEST_SUCCESS:" in line:
                        json_str = line.split("TEST_SUCCESS:")[1].strip()
                        try: titan_data = json.loads(json_str)
                        except: titan_data = {}
                        self.after(0, lambda td=titan_data: self.trigger_test_validation(td))
                    else:
                        json_str = line.split("[SOS_TRIGGER]")[1].strip()
                        try: 
                            sos_data = json.loads(json_str)
                            if "titans" in sos_data:
                                titan_data = sos_data["titans"]
                                is_manual = sos_data.get("is_manual", False)
                            else:
                                titan_data = sos_data
                                is_manual = False
                        except: 
                            titan_data = {"Неизвестно": 0}
                            is_manual = False
                        self.after(0, lambda td=titan_data, im=is_manual: self.trigger_intervention(td, im))
                    continue
                if "[ПАУЗА ОТЛАДКИ]" in line:
                    self.action_state = "continue"
                    lang = getattr(self.controller, 'current_lang', 'RU')
                    self.after(0, lambda: self.btn_action.configure(text=get_text(lang, "dash_btn_continue"), state="normal", fg_color="#28a745", border_width=0, text_color="white"))
                
                self.after(0, self.append_log, line)
                    
        self.after(0, lambda: self.append_log("\n[СИСТЕМА] Процесс бота завершен.\n"))
        self.after(0, self.reset_buttons)

    def trigger_test_validation(self, titan_data):
        from ui.team_selector import TeamSelectorDialog
        lang = getattr(self.controller, 'current_lang', 'RU')
        
        dialog = ctk.CTkToplevel(self)
        dialog.title(get_text(lang, "test_title"))
        dialog.geometry("450x300")
        dialog.attributes("-topmost", True)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text=get_text(lang, "test_success"), font=ctk.CTkFont(size=18, weight="bold"), text_color="#28a745").pack(pady=(15, 5))
        
        stats_text = ""
        for titan, stats in titan_data.items():
            hp_val = stats.get('hp', 0) if isinstance(stats, dict) else stats
            titan_name = get_text(lang, f"titan_{titan}")
            stats_text += f"{titan_name.capitalize()}: {hp_val}% HP\n"
            
        ctk.CTkLabel(dialog, text=f"{get_text(lang, 'test_remains')}{stats_text}", font=ctk.CTkFont(size=14)).pack(pady=10)
        
        def on_confirm():
            if self.bot_process and self.bot_process.poll() is None:
                self.bot_process.stdin.write("CONFIRM\n")
                self.bot_process.stdin.flush()
            dialog.destroy()
            
        def on_replay():
            def on_team_selected(new_team):
                team_str = ",".join(new_team)
                if self.bot_process and self.bot_process.poll() is None:
                    self.bot_process.stdin.write(f"ROLLBACK:{team_str}\n")
                    self.bot_process.stdin.flush()
            TeamSelectorDialog(self.controller, on_team_selected, room_type="all", context="rollback")
            dialog.destroy()
            
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=15)
        
        ctk.CTkButton(btn_frame, text=get_text(lang, "test_btn_confirm"), fg_color="#28a745", hover_color="#218838", command=on_confirm).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text=get_text(lang, "test_btn_rollback"), fg_color="#ffc107", hover_color="#e0a800", text_color="black", command=on_replay).pack(side="left", padx=10)

    def trigger_intervention(self, titan_data, is_manual=False):
        from ui.intervention_dialog import InterventionDialog
        from ui.team_selector import TeamSelectorDialog
        
        def on_decision(decision_text):
            if decision_text == "rollback":
                # Это срабатывает при нажатии кнопки "Откатить" в GUI на самом ПК
                def on_team_selected(new_team):
                    team_str = ",".join(new_team)
                    if self.bot_process and self.bot_process.poll() is None:
                        self.bot_process.stdin.write(f"ROLLBACK:{team_str}\n")
                        self.bot_process.stdin.flush()
                TeamSelectorDialog(self.controller, on_team_selected, room_type="all", context="rollback")
                
            elif decision_text.startswith("rb_custom:"):
                # НОВАЯ ЛОГИКА ДЛЯ ТЕЛЕГРАМА (ПАРСИНГ ТЕКСТА)
                team_str = decision_text.split(":")[1]
                if self.bot_process and self.bot_process.poll() is None:
                    self.bot_process.stdin.write(f"ROLLBACK:{team_str}\n")
                    self.bot_process.stdin.flush()
                    
            else:
                # Обработка команд MANUAL, STOP, IGNORE
                if self.bot_process and self.bot_process.poll() is None:
                    self.bot_process.stdin.write(f"{decision_text.upper()}\n")
                    self.bot_process.stdin.flush()
                    
        InterventionDialog(self.controller, titan_data=titan_data, callback=on_decision, is_manual=is_manual)

    def toggle_pause(self):
        lang = getattr(self.controller, 'current_lang', 'RU')
        if os.path.exists("pause.flag"):
            os.remove("pause.flag")
            self.btn_pause.configure(text=get_text(lang, "dash_btn_pause"))
            self.append_log("[GUI] Сигнал 'Снять паузу' отправлен боту.\n")
        else:
            with open("pause.flag", "w") as f: f.write("1")
            self.btn_pause.configure(text=get_text(lang, "dash_btn_unpause"))
            self.append_log("[GUI] Сигнал 'Мягкая пауза' отправлен. Бот остановится перед следующей дверью.\n")

    def stop_bot(self):
        if self.bot_process:
            self.bot_process.terminate()
            self.append_log("[GUI] ЭКСТРЕННЫЙ СТОП. Процесс убит.\n")
            if os.path.exists("pause.flag"): os.remove("pause.flag")
            self.reset_buttons()

    def reset_buttons(self):
        self.action_state = "start"
        lang = getattr(self.controller, 'current_lang', 'RU')
        self.btn_action.configure(text=get_text(lang, "dash_btn_start"), state="normal", fg_color="#28a745", border_width=0, text_color="white")
        self.btn_pause.configure(state="disabled", text=get_text(lang, "dash_btn_pause"), fg_color="transparent", border_width=1, text_color="gray")
        self.btn_stop.configure(state="disabled", text=get_text(lang, "dash_btn_stop"), fg_color="transparent", border_width=1, text_color="gray")