# ui/statistics_tab.py
import customtkinter as ctk
import os
import yaml
from datetime import datetime, timedelta
from stats_manager import load_stats, add_metric, reset_stats, get_game_date, get_game_datetime
from i18n import get_text

def format_number(num):
    """Превращает 150000 в 150K, а 1500000 в 1.5M"""
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M".replace('.0M', 'M')
    elif num >= 10_000:
        return f"{num / 1_000:.1f}K".replace('.0K', 'K')
    return str(num)

class StatisticsFrame(ctk.CTkFrame):
    def __init__(self, master, controller, **kwargs):
        super().__init__(master, corner_radius=10, fg_color="transparent", **kwargs)
        self.controller = controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # --- ЗАГОЛОВОК И СЕЛЕКТОР ---
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(15, 10), padx=5)
        
        self.lbl_title = ctk.CTkLabel(header_frame, text="", font=ctk.CTkFont(size=24, weight="bold"))
        self.lbl_title.pack(side="left")
        
        self.period_var = ctk.StringVar(value="14d")
        self.opt_period = ctk.CTkOptionMenu(
            header_frame, 
            values=[], 
            variable=self.period_var,
            width=120,
            command=self.on_period_change
        )
        self.opt_period.pack(side="right", padx=10)

        # --- КАРТОЧКИ СТАТИСТИКИ (2 ряда по 3) ---
        self.cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.cards_frame.grid(row=1, column=0, sticky="ew", padx=5)
        self.cards_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.lbl_val_tit_total = self.create_card(self.cards_frame, 0, 0, "stat_total_tit", "#28a745")
        self.lbl_val_tit_today = self.create_card(self.cards_frame, 0, 1, "stat_today_tit", "#28a745")
        self.lbl_val_potions = self.create_card(self.cards_frame, 0, 2, "stat_potions", "#9b59b6")
        
        self.lbl_val_rooms = self.create_card(self.cards_frame, 1, 0, "stat_rooms", "#17a2b8")
        self.lbl_val_floors = self.create_card(self.cards_frame, 1, 1, "stat_floors", "#17a2b8")
        self.lbl_val_rules = self.create_card(self.cards_frame, 1, 2, "stat_rules", "#ffc107")

        # --- ГРАФИК (Native Canvas) ---
        chart_container = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=8)
        chart_container.grid(row=2, column=0, sticky="nsew", padx=5, pady=10)
        
        self.lbl_chart = ctk.CTkLabel(chart_container, text="", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_chart.pack(pady=10)
        
        self.canvas = ctk.CTkCanvas(chart_container, bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.canvas.bind("<Configure>", lambda e: self.draw_chart())

        # --- ПОДВАЛ (Синхронизация по времени и Сброс) ---
        footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        footer_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=(0, 15))
        footer_frame.grid_columnconfigure(4, weight=1)
        
        self.sync_date_var = ctk.StringVar()
        self.opt_sync_date = ctk.CTkOptionMenu(footer_frame, values=[], variable=self.sync_date_var, width=190)
        self.opt_sync_date.grid(row=0, column=0, padx=(0, 10), sticky="w")
        
        self.lbl_manual = ctk.CTkLabel(footer_frame, text="", font=ctk.CTkFont(weight="bold"))
        self.lbl_manual.grid(row=0, column=1, padx=(0, 10), sticky="w")
        
        self.entry_manual = ctk.CTkEntry(footer_frame, width=90)
        self.entry_manual.grid(row=0, column=2, padx=(0, 10), sticky="w")
        
        self.btn_add_manual = ctk.CTkButton(footer_frame, text="", fg_color="#007bff", hover_color="#0056b3", command=self.sync_manual_titanite)
        self.btn_add_manual.grid(row=0, column=3, sticky="w")
        
        self.btn_reset = ctk.CTkButton(footer_frame, text="", fg_color="transparent", border_width=1, border_color="#dc3545", text_color="#dc3545", hover_color="#4a151b", command=self.do_reset)
        self.btn_reset.grid(row=0, column=5, sticky="e")

    def create_card(self, parent, row, col, text_key, color):
        frame = ctk.CTkFrame(parent, fg_color="#1e1e1e", corner_radius=8)
        frame.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
        lbl_title = ctk.CTkLabel(frame, text=text_key, text_color="gray", font=ctk.CTkFont(size=12))
        lbl_title.pack(pady=(10, 0))
        setattr(self, f"lbl_title_{row}_{col}", lbl_title)
        
        lbl_val = ctk.CTkLabel(frame, text="0", text_color=color, font=ctk.CTkFont(size=22, weight="bold"))
        lbl_val.pack(pady=(0, 10))
        return lbl_val

    def get_period_keys(self):
        return ["14d", "1m", "3m", "6m", "1y"]

    def update_language(self, lang):
        self.lbl_title.configure(text=get_text(lang, "stat_title"))
        self.lbl_title_0_0.configure(text=get_text(lang, "stat_total_tit"))
        self.lbl_title_0_1.configure(text=get_text(lang, "stat_today_tit"))
        self.lbl_title_0_2.configure(text=get_text(lang, "stat_potions"))
        self.lbl_title_1_0.configure(text=get_text(lang, "stat_rooms"))
        self.lbl_title_1_1.configure(text=get_text(lang, "stat_floors"))
        self.lbl_title_1_2.configure(text=get_text(lang, "stat_rules"))
        
        self.lbl_chart.configure(text=get_text(lang, "stat_chart_title"))
        self.lbl_manual.configure(text=get_text(lang, "stat_manual_add"))
        self.btn_add_manual.configure(text=get_text(lang, "stat_btn_add"))
        self.btn_reset.configure(text=get_text(lang, "stat_reset"))

        # 1. Локализация периода графика
        current_val = self.period_var.get()
        values = [get_text(lang, f"stat_period_{k}") for k in self.get_period_keys()]
        self.opt_period.configure(values=values)
        
        for k in self.get_period_keys():
            if k == current_val:
                self.period_var.set(get_text(lang, f"stat_period_{k}"))
                break

        # 2. ДИНАМИЧЕСКАЯ ГЕНЕРАЦИЯ 7 ДНЕЙ ДЛЯ СИНХРОНИЗАЦИИ
        base_date = get_game_datetime()
        sync_dates = []
        for i in range(7):
            d = base_date - timedelta(days=i)
            date_str = d.strftime("%Y-%m-%d")
            if i == 0:
                val = f"{get_text(lang, 'stat_today')} ({date_str})"
            elif i == 1:
                val = f"{get_text(lang, 'stat_yesterday')} ({date_str})"
            else:
                val = date_str
            sync_dates.append(val)
            
        self.opt_sync_date.configure(values=sync_dates)
        
        current_sync = self.opt_sync_date.get()
        if not current_sync or current_sync not in sync_dates:
            self.opt_sync_date.set(sync_dates[0])

    def on_period_change(self, selected_text):
        lang = getattr(self.controller, 'current_lang', 'RU')
        for k in self.get_period_keys():
            if get_text(lang, f"stat_period_{k}") == selected_text:
                self.period_var.set(k)
                self.draw_chart()
                self.period_var.set(selected_text)
                self.opt_period._current_value = k 
                break

    def count_rules(self):
        count = 0
        for r_id in ["earth", "water", "fire", "mix"]:
            path = f"rules/{r_id}.yml"
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f) or {}
                        count += len(data.get("rules", []))
                except: pass
        return count

    def refresh_data(self):
        stats = load_stats()
        today = get_game_date()
        daily_stats = stats.get("daily", {}).get(today, {})
        
        self.lbl_val_tit_total.configure(text=format_number(stats.get("total_titanite", 0)))
        self.lbl_val_potions.configure(text=format_number(stats.get("total_potions", 0)))
        self.lbl_val_rooms.configure(text=format_number(stats.get("total_rooms", 0)))
        self.lbl_val_floors.configure(text=format_number(stats.get("total_floors", 0)))
        
        self.lbl_val_tit_today.configure(text=format_number(daily_stats.get("titanite", 0)))
        self.lbl_val_rules.configure(text=str(self.count_rules()))
        
        self.draw_chart()

    def draw_chart(self):
        self.canvas.delete("all")
        stats = load_stats()
        daily = stats.get("daily", {})
        
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width <= 1 or height <= 1: return
        
        raw_val = getattr(self.opt_period, '_current_value', "14d")
        days_map = {"14d": 14, "1m": 30, "3m": 90, "6m": 180, "1y": 365}
        days = days_map.get(raw_val, 14)
        
        base_date = get_game_datetime()
        
        dates = [(base_date - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days-1, -1, -1)]
        values = [daily.get(d, {}).get("titanite", 0) for d in dates]
        labels = [(base_date - timedelta(days=i)).strftime("%d.%m") for i in range(days-1, -1, -1)]
        
        max_val = max(values) if values and max(values) > 0 else 150
        
        pad_x, pad_y = 30, 20
        chart_w = width - 2 * pad_x
        chart_h = height - 2 * pad_y
        spacing = chart_w / days
        bar_w = spacing * 0.8
        
        self.canvas.create_line(pad_x, height - pad_y, width - pad_x, height - pad_y, fill="#555555", width=2)
        
        for i, val in enumerate(values):
            x_center = pad_x + spacing * i + spacing / 2
            
            if val > 0:
                bar_h = (val / max_val) * (chart_h - 20)
                x1 = x_center - bar_w / 2
                y1 = height - pad_y - bar_h
                x2 = x_center + bar_w / 2
                y2 = height - pad_y
                
                color = "#28a745" if val >= 150 else "#007bff"
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")
                
                if bar_w > 20:
                    self.canvas.create_text(x_center, y1 - 10, text=format_number(val), fill="white", font=("Arial", 10, "bold"))
                
            if spacing > 25 or i % max(1, days // 10) == 0:
                self.canvas.create_text(x_center, height - pad_y + 10, text=labels[i], fill="gray", font=("Arial", 9))

    def calc_rewards(self, titanite):
        if titanite <= 60:
            rooms = titanite // 6
            potions = rooms * 25
        else:
            rooms = 10 + (titanite - 60) // 12
            potions = 250 + ((titanite - 60) // 12) * 50
        floors = rooms // 5
        return rooms, floors, potions

    def sync_manual_titanite(self):
        val = self.entry_manual.get()
        if val.isdigit():
            new_total = int(val)
            
            date_selection = self.opt_sync_date.get()
            
            # Умное извлечение даты, поддерживает и "Сегодня (2026-08-25)", и просто "2026-08-23"
            if "(" in date_selection:
                target_date = date_selection.split("(")[-1].strip(")")
            else:
                target_date = date_selection.strip()
            
            stats = load_stats()
            daily_stats = stats.get("daily", {}).get(target_date, {})
            
            current_daily = daily_stats.get("titanite", 0)
            bot_baseline = daily_stats.get("bot_titanite", 0)
            
            if new_total < bot_baseline:
                self.controller.frames["dash"].append_log(
                    f"[СТАТИСТИКА] ОШИБКА: За {target_date} бот сам собрал {bot_baseline} титанита. Нельзя указать значение меньше этой суммы!\n"
                )
                return
                
            delta_titanite = new_total - current_daily
            
            if delta_titanite != 0:
                curr_r, curr_f, curr_p = self.calc_rewards(current_daily)
                new_r, new_f, new_p = self.calc_rewards(new_total)
                
                d_rooms = new_r - curr_r
                d_floors = new_f - curr_f
                d_potions = new_p - curr_p
                
                add_metric("titanite", delta_titanite, date_str=target_date)
                if d_rooms != 0: add_metric("rooms", d_rooms, date_str=target_date)
                if d_floors != 0: add_metric("floors", d_floors, date_str=target_date)
                if d_potions != 0: add_metric("potions", d_potions, date_str=target_date)
                
                sign = "+" if delta_titanite > 0 else ""
                self.controller.frames["dash"].append_log(
                    f"[СТАТИСТИКА] Данные за {target_date} синхронизированы! Дельта: {sign}{delta_titanite} тит., {sign}{d_rooms} комн., {sign}{d_potions} зелий.\n"
                )
            else:
                self.controller.frames["dash"].append_log("[СТАТИСТИКА] Синхронизация не требуется. Данные актуальны.\n")
                
            self.entry_manual.delete(0, 'end')
            self.refresh_data()

    def do_reset(self):
        reset_stats()
        self.refresh_data()
        self.controller.frames["dash"].append_log("[СТАТИСТИКА] Вся история полностью сброшена!\n")