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
        self.cached_stats = None  
        
        # Интерактивные стейты и надежное хранение системного ключа периода
        self.current_period_key = "14d"
        self.chart_buckets = []
        self.rendered_hitboxes = [] 
        self.selected_bar_index = None

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
        self.canvas.pack(fill="both", expand=True, padx=10, pady=(0, 20))
        
        self.canvas.bind("<Configure>", lambda e: self.draw_chart())
        self.canvas.bind("<Button-1>", self.on_canvas_click)

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
        self.lbl_chart.configure(text=get_text(lang, "stat_chart_title"))
        self.lbl_manual.configure(text=get_text(lang, "stat_manual_add"))
        self.btn_add_manual.configure(text=get_text(lang, "stat_btn_add"))
        self.btn_reset.configure(text=get_text(lang, "stat_reset"))

        # Обновляем локализацию выпадающего списка
        values = [get_text(lang, f"stat_period_{k}") for k in self.get_period_keys()]
        self.opt_period.configure(values=values)
        self.period_var.set(get_text(lang, f"stat_period_{self.current_period_key}"))

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
            
        self.update_summary_cards()

    def on_period_change(self, selected_text):
        lang = getattr(self.controller, 'current_lang', 'RU')
        # Ищем системный ключ по выбранному локализованному тексту
        for k in self.get_period_keys():
            if get_text(lang, f"stat_period_{k}") == selected_text:
                self.current_period_key = k
                self.period_var.set(selected_text)
                self.selected_bar_index = None 
                self.draw_chart()
                self.update_summary_cards()
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
        self.cached_stats = load_stats()
        self.selected_bar_index = None
        self.update_summary_cards()
        self.draw_chart()

    def update_summary_cards(self):
        if not self.cached_stats: return
        lang = getattr(self.controller, 'current_lang', 'RU')
        
        self.lbl_val_rules.configure(text=str(self.count_rules()))
        self.lbl_title_1_2.configure(text=get_text(lang, "stat_rules"))
        
        today = get_game_date()
        daily_stats = self.cached_stats.get("daily", {}).get(today, {})
        self.lbl_val_tit_today.configure(text=format_number(daily_stats.get("titanite", 0)))
        self.lbl_title_0_1.configure(text=get_text(lang, "stat_today_tit"))

        if self.selected_bar_index is not None and self.selected_bar_index < len(self.chart_buckets):
            bucket = self.chart_buckets[self.selected_bar_index]
            date_label = f" ({bucket['date_str']})"
            
            self.lbl_title_0_0.configure(text=get_text(lang, "stat_total_tit") + date_label)
            self.lbl_val_tit_total.configure(text=format_number(bucket["titanite"]))
            
            self.lbl_title_0_2.configure(text=get_text(lang, "stat_potions") + date_label)
            self.lbl_val_potions.configure(text=format_number(bucket["potions"]))
            
            self.lbl_title_1_0.configure(text=get_text(lang, "stat_rooms") + date_label)
            self.lbl_val_rooms.configure(text=format_number(bucket["rooms"]))
            
            self.lbl_title_1_1.configure(text=get_text(lang, "stat_floors") + date_label)
            self.lbl_val_floors.configure(text=format_number(bucket["floors"]))
        else:
            self.lbl_title_0_0.configure(text=get_text(lang, "stat_total_tit"))
            self.lbl_val_tit_total.configure(text=format_number(self.cached_stats.get("total_titanite", 0)))
            
            self.lbl_title_0_2.configure(text=get_text(lang, "stat_potions"))
            self.lbl_val_potions.configure(text=format_number(self.cached_stats.get("total_potions", 0)))
            
            self.lbl_title_1_0.configure(text=get_text(lang, "stat_rooms"))
            self.lbl_val_rooms.configure(text=format_number(self.cached_stats.get("total_rooms", 0)))
            
            self.lbl_title_1_1.configure(text=get_text(lang, "stat_floors"))
            self.lbl_val_floors.configure(text=format_number(self.cached_stats.get("total_floors", 0)))

    def build_buckets(self, period):
        buckets = []
        daily = self.cached_stats.get("daily", {})
        base_date = get_game_datetime()
        
        if period in ["14d", "1m"]:
            days = 14 if period == "14d" else 30
            for i in range(days-1, -1, -1):
                d = base_date - timedelta(days=i)
                date_str = d.strftime("%Y-%m-%d")
                d_stats = daily.get(date_str, {})
                buckets.append({
                    "label": d.strftime("%d.%m"),
                    "date_str": d.strftime("%d.%m.%Y"),
                    "titanite": d_stats.get("titanite", 0),
                    "rooms": d_stats.get("rooms", 0),
                    "floors": d_stats.get("floors", 0),
                    "potions": d_stats.get("potions", 0)
                })
        elif period in ["3m", "6m"]:
            weeks = 12 if period == "3m" else 26
            for w in range(weeks-1, -1, -1):
                w_tit, w_room, w_fl, w_pot = 0, 0, 0, 0
                start_d = base_date - timedelta(days=w*7 + 6)
                end_d = base_date - timedelta(days=w*7)
                for i in range(7):
                    d = start_d + timedelta(days=i)
                    d_stats = daily.get(d.strftime("%Y-%m-%d"), {})
                    w_tit += d_stats.get("titanite", 0)
                    w_room += d_stats.get("rooms", 0)
                    w_fl += d_stats.get("floors", 0)
                    w_pot += d_stats.get("potions", 0)
                buckets.append({
                    "label": f"{start_d.strftime('%d.%m')} - {end_d.strftime('%d.%m')}",
                    "date_str": f"{start_d.strftime('%d.%m')} - {end_d.strftime('%d.%m')}",
                    "titanite": w_tit, "rooms": w_room, "floors": w_fl, "potions": w_pot
                })
        elif period == "1y":
            for m in range(11, -1, -1):
                target_month = (base_date.month - m - 1) % 12 + 1
                target_year = base_date.year + ((base_date.month - m - 1) // 12)
                m_tit, m_room, m_fl, m_pot = 0, 0, 0, 0
                for date_str, d_stats in daily.items():
                    if date_str.startswith(f"{target_year:04d}-{target_month:02d}"):
                        m_tit += d_stats.get("titanite", 0)
                        m_room += d_stats.get("rooms", 0)
                        m_fl += d_stats.get("floors", 0)
                        m_pot += d_stats.get("potions", 0)
                buckets.append({
                    "label": f"{target_month:02d}.{str(target_year)[2:]}",
                    "date_str": f"{target_month:02d}.{target_year}",
                    "titanite": m_tit, "rooms": m_room, "floors": m_fl, "potions": m_pot
                })
        return buckets

    def get_nice_max(self, val):
        if val <= 150: return 150
        if val <= 500: return 500
        if val <= 1000: return 1000
        if val <= 5000: return 5000
        if val <= 10000: return 10000
        if val <= 50000: return 50000
        return ((val // 10000) + 1) * 10000

    def draw_chart(self):
        self.canvas.delete("all")
        self.rendered_hitboxes.clear()
        
        if getattr(self, 'cached_stats', None) is None:
            return
            
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width <= 1 or height <= 1: return
        
        # Строго используем системный ключ
        self.chart_buckets = self.build_buckets(self.current_period_key)
        
        # ЗАЩИТА ОТ КРАША: Запрещаем деление на 0, если данных нет
        days = max(1, len(self.chart_buckets)) 
        
        real_max = max((b["titanite"] for b in self.chart_buckets), default=0)
        max_val = self.get_nice_max(real_max)
        
        pad_left, pad_right, pad_top, pad_bottom = 50, 20, 20, 25
        chart_w = width - pad_left - pad_right
        chart_h = height - pad_top - pad_bottom
        
        # 1. Отрисовка Оси Y (Сетка)
        lines = 3
        for i in range(lines + 1):
            y = pad_top + chart_h - (i * chart_h / lines)
            val = int(max_val * (i / lines))
            self.canvas.create_line(pad_left, y, width - pad_right, y, fill="#333333", dash=(4, 4))
            if i > 0: 
                self.canvas.create_text(pad_left - 10, y, text=format_number(val), fill="gray", font=("Arial", 9), anchor="e")
        
        # Базовая линия X
        self.canvas.create_line(pad_left, height - pad_bottom, width - pad_right, height - pad_bottom, fill="#666666", width=2)
        
        # 2. Отрисовка баров
        spacing = chart_w / days
        bar_w = spacing * 0.7
        
        for i, bucket in enumerate(self.chart_buckets):
            val = bucket["titanite"]
            x_center = pad_left + spacing * i + spacing / 2
            
            self.rendered_hitboxes.append(x_center)
            
            is_selected = (self.selected_bar_index == i)
            is_dimmed = (self.selected_bar_index is not None and not is_selected)
            
            if val > 0:
                bar_h = (val / max_val) * chart_h
                x1 = x_center - bar_w / 2
                y1 = height - pad_bottom - bar_h
                x2 = x_center + bar_w / 2
                y2 = height - pad_bottom
                
                color = "#28a745" if not is_dimmed else "#1e3d29" 
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")
                
                # Текст значения над баром только при выделении или малом кол-ве баров
                if is_selected or (self.selected_bar_index is None and days <= 14):
                    if bar_w > 15:
                        txt_color = "white" if not is_dimmed else "gray"
                        self.canvas.create_text(x_center, y1 - 10, text=format_number(val), fill=txt_color, font=("Arial", 10, "bold"))
                
            # ЧИСТЫЙ UI: Дата на оси X появляется ТОЛЬКО под выделенным баром
            if is_selected:
                self.canvas.create_text(x_center, height - pad_bottom + 12, text=bucket["label"], fill="white", font=("Arial", 9, "bold"))

    def on_canvas_click(self, event):
        if not self.rendered_hitboxes: return
        
        clicked_idx = None
        width = self.canvas.winfo_width()
        pad_left, pad_right = 50, 20
        
        # Защита от деления на 0 при клике
        hitbox_count = max(1, len(self.rendered_hitboxes))
        spacing = (width - pad_left - pad_right) / hitbox_count
        
        for i, center_x in enumerate(self.rendered_hitboxes):
            if abs(event.x - center_x) <= spacing / 2:
                clicked_idx = i
                break
                
        if clicked_idx is not None and clicked_idx == self.selected_bar_index:
            self.selected_bar_index = None
        else:
            self.selected_bar_index = clicked_idx
            
        self.update_summary_cards()
        self.draw_chart()

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