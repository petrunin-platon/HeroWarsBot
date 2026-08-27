# ui/about_tab.py
import customtkinter as ctk
import webbrowser
from i18n import get_text

class AboutFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, controller, **kwargs):
        super().__init__(master, corner_radius=10, fg_color="transparent", **kwargs)
        self.controller = controller

        # =====================================================================
        # 🔧 НАСТРОЙКИ МОНЕТИЗАЦИИ
        # =====================================================================
        self.wallet_usdt = "TSK3ozZMWCST1a6gbmZ5AfRvK8XAX2xjin"
        self.wallet_btc  = "bc1qsu52cvfn4aqcay3mjasyah4hcx73npqvn5re3p"
        self.wallet_eth  = "0x1e87D47a6Ae8c49508BCC33F1b74FBC27efCFDD5"

        self.url_boosty   = "https://boosty.to/petrunin.platon/donate"
        self.url_yoomoney = "https://yoomoney.ru/to/410013614193490"

        # Ссылки Telegram Tribute
        self.url_tg_rub_app = "https://t.me/tribute/app?startapp=dPqn"
        self.url_tg_rub_web = "https://web.tribute.tg/d/Pqn"
        
        self.url_tg_eur_app = "https://t.me/tribute/app?startapp=dwT2"
        self.url_tg_eur_web = "https://web.tribute.tg/d/wT2"
        
        self.url_tg_usd_app = "https://t.me/tribute/app?startapp=dPqo"
        self.url_tg_usd_web = "https://web.tribute.tg/d/Pqo"
        # =====================================================================

        self.grid_columnconfigure(0, weight=1)

        # ЗАГОЛОВОК И ОПИСАНИЕ
        self.lbl_title = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=24, weight="bold"))
        self.lbl_title.grid(row=0, column=0, pady=(20, 5), padx=20, sticky="w")
        
        self.lbl_desc = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=14), justify="left", wraplength=700)
        self.lbl_desc.grid(row=1, column=0, pady=(0, 15), padx=20, sticky="w")

        # ИНФОБЛОК (Компактный дизайн)
        info_frame = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=10)
        info_frame.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")
        info_frame.grid_columnconfigure(0, weight=1) 
        info_frame.grid_columnconfigure(1, weight=0) 

        text_subframe = ctk.CTkFrame(info_frame, fg_color="transparent")
        text_subframe.grid(row=0, column=0, sticky="nw", padx=15, pady=8)

        self.lbl_author = ctk.CTkLabel(text_subframe, text="", font=ctk.CTkFont(weight="bold"))
        self.lbl_author.grid(row=0, column=0, pady=1, sticky="w")
        ctk.CTkLabel(text_subframe, text="Platon Petrunin").grid(row=0, column=1, padx=15, pady=1, sticky="w")

        ctk.CTkLabel(text_subframe, text="Email:", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, pady=1, sticky="w")
        ctk.CTkLabel(text_subframe, text="Petrunin.platon@gmail.com").grid(row=1, column=1, padx=15, pady=1, sticky="w")

        self.lbl_license = ctk.CTkLabel(text_subframe, text="", font=ctk.CTkFont(weight="bold"))
        self.lbl_license.grid(row=2, column=0, pady=1, sticky="w")
        self.lbl_license_val = ctk.CTkLabel(text_subframe, text="")
        self.lbl_license_val.grid(row=2, column=1, padx=15, pady=1, sticky="w")

        btn_subframe = ctk.CTkFrame(info_frame, fg_color="transparent")
        btn_subframe.grid(row=0, column=1, sticky="e", padx=15, pady=10)

        self.btn_github = ctk.CTkButton(btn_subframe, text="", width=180, height=30, command=lambda: self.safe_open_url("https://github.com/Platon-Petrunin"))
        self.btn_github.pack(pady=(0, 18))

        self.btn_mail = ctk.CTkButton(btn_subframe, text="", width=180, height=30, fg_color="#28a745", hover_color="#218838", command=lambda: webbrowser.open("mailto:Petrunin.platon@gmail.com"))
        self.btn_mail.pack(pady=(0, 0))

        # БЛОК МОНЕТИЗАЦИИ И ПОДДЕРЖКИ
        self.lbl_support = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=18, weight="bold"), text_color="#ffc107")
        self.lbl_support.grid(row=3, column=0, pady=(0, 5), padx=20, sticky="w")
        
        # ЭТАЖ 1: КРИПТА (Слева) и ТЕЛЕГРАМ (Справа)
        support_top_frame = ctk.CTkFrame(self, fg_color="transparent")
        support_top_frame.grid(row=4, column=0, padx=20, pady=(0, 15), sticky="ew")
        
        support_top_frame.grid_columnconfigure(0, weight=1)
        support_top_frame.grid_columnconfigure(1, weight=0)

        # -- ЛЕВАЯ КОЛОНКА: КРИПТОВАЛЮТА --
        crypto_frame = ctk.CTkFrame(support_top_frame, fg_color="#1e1e1e", corner_radius=10)
        crypto_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        crypto_frame.grid_columnconfigure(1, weight=1)

        self.lbl_crypto_title = ctk.CTkLabel(crypto_frame, text="", font=ctk.CTkFont(weight="bold"))
        self.lbl_crypto_title.grid(row=0, column=0, columnspan=2, pady=(10, 5), padx=15, sticky="w")

        ctk.CTkLabel(crypto_frame, text="USDT (TRC20):").grid(row=1, column=0, padx=(15, 10), pady=5, sticky="w")
        self.entry_usdt = ctk.CTkEntry(crypto_frame, width=260)
        self.entry_usdt.insert(0, self.wallet_usdt)
        self.entry_usdt.configure(state="readonly")
        self.entry_usdt.grid(row=1, column=1, padx=(0, 15), pady=5, sticky="ew")

        ctk.CTkLabel(crypto_frame, text="Bitcoin (BTC):").grid(row=2, column=0, padx=(15, 10), pady=5, sticky="w")
        self.entry_btc = ctk.CTkEntry(crypto_frame, width=260)
        self.entry_btc.insert(0, self.wallet_btc)
        self.entry_btc.configure(state="readonly")
        self.entry_btc.grid(row=2, column=1, padx=(0, 15), pady=5, sticky="ew")

        ctk.CTkLabel(crypto_frame, text="Ethereum (ETH):").grid(row=3, column=0, padx=(15, 10), pady=(5, 15), sticky="w")
        self.entry_eth = ctk.CTkEntry(crypto_frame, width=260)
        self.entry_eth.insert(0, self.wallet_eth)
        self.entry_eth.configure(state="readonly")
        self.entry_eth.grid(row=3, column=1, padx=(0, 15), pady=(5, 15), sticky="ew")

        # -- ПРАВАЯ КОЛОНКА: ТЕЛЕГРАМ --
        tg_frame = ctk.CTkFrame(support_top_frame, fg_color="#1e1e1e", corner_radius=10)
        tg_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        self.lbl_tg_title = ctk.CTkLabel(tg_frame, text="", font=ctk.CTkFont(weight="bold"))
        self.lbl_tg_title.pack(pady=(10, 0), padx=15, anchor="w")

        tg_grid = ctk.CTkFrame(tg_frame, fg_color="transparent")
        tg_grid.pack(padx=15, pady=(5, 15))

        btn_w = 60
        
        # RUB
        ctk.CTkLabel(tg_grid, text="RUB:").grid(row=0, column=0, padx=(0, 10), pady=6, sticky="w")
        self.btn_tg_rub_app = ctk.CTkButton(tg_grid, text="", width=btn_w, height=26, fg_color="#229ED9", hover_color="#1c84b6", command=lambda: self.safe_open_url(self.url_tg_rub_app))
        self.btn_tg_rub_app.grid(row=0, column=1, padx=4, pady=6)
        self.btn_tg_rub_web = ctk.CTkButton(tg_grid, text="", width=btn_w, height=26, fg_color="#444444", hover_color="#555555", command=lambda: self.safe_open_url(self.url_tg_rub_web))
        self.btn_tg_rub_web.grid(row=0, column=2, padx=4, pady=6)

        # EUR
        ctk.CTkLabel(tg_grid, text="EUR:").grid(row=1, column=0, padx=(0, 10), pady=6, sticky="w")
        self.btn_tg_eur_app = ctk.CTkButton(tg_grid, text="", width=btn_w, height=26, fg_color="#229ED9", hover_color="#1c84b6", command=lambda: self.safe_open_url(self.url_tg_eur_app))
        self.btn_tg_eur_app.grid(row=1, column=1, padx=4, pady=6)
        self.btn_tg_eur_web = ctk.CTkButton(tg_grid, text="", width=btn_w, height=26, fg_color="#444444", hover_color="#555555", command=lambda: self.safe_open_url(self.url_tg_eur_web))
        self.btn_tg_eur_web.grid(row=1, column=2, padx=4, pady=6)

        # USD
        ctk.CTkLabel(tg_grid, text="USD:").grid(row=2, column=0, padx=(0, 10), pady=6, sticky="w")
        self.btn_tg_usd_app = ctk.CTkButton(tg_grid, text="", width=btn_w, height=26, fg_color="#229ED9", hover_color="#1c84b6", command=lambda: self.safe_open_url(self.url_tg_usd_app))
        self.btn_tg_usd_app.grid(row=2, column=1, padx=4, pady=6)
        self.btn_tg_usd_web = ctk.CTkButton(tg_grid, text="", width=btn_w, height=26, fg_color="#444444", hover_color="#555555", command=lambda: self.safe_open_url(self.url_tg_usd_web))
        self.btn_tg_usd_web.grid(row=2, column=2, padx=4, pady=6)

        # ЭТАЖ 2: ПРЯМЫЕ ПЕРЕВОДЫ (Растянуты на всю ширину)
        fiat_frame = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=10)
        fiat_frame.grid(row=5, column=0, padx=20, pady=(0, 20), sticky="ew")

        self.lbl_fiat_title = ctk.CTkLabel(fiat_frame, text="", font=ctk.CTkFont(weight="bold"))
        self.lbl_fiat_title.pack(pady=(10, 5), padx=15, anchor="w")

        btns_fiat_frame = ctk.CTkFrame(fiat_frame, fg_color="transparent")
        btns_fiat_frame.pack(fill="x", padx=10, pady=(0, 15))
        btns_fiat_frame.grid_columnconfigure(0, weight=1)
        btns_fiat_frame.grid_columnconfigure(1, weight=1)

        self.btn_boosty = ctk.CTkButton(btns_fiat_frame, text="", height=36, font=ctk.CTkFont(weight="bold"), fg_color="#E05B16", hover_color="#c44d10", command=lambda: self.safe_open_url(self.url_boosty))
        self.btn_boosty.grid(row=0, column=0, padx=(5, 10), sticky="ew")

        self.btn_yoomoney = ctk.CTkButton(btns_fiat_frame, text="", height=36, font=ctk.CTkFont(weight="bold"), fg_color="#8A2BE2", hover_color="#6A1CB7", command=lambda: self.safe_open_url(self.url_yoomoney))
        self.btn_yoomoney.grid(row=0, column=1, padx=(10, 5), sticky="ew")

    # =====================================================================
    # УНИВЕРСАЛЬНЫЙ ХЕЛПЕР (Безопасное открытие ссылок)
    # =====================================================================
    def safe_open_url(self, url):
        """Защита от битых и пустых ссылок"""
        if not url or "ВСТАВЬ" in url:
            return
        if not url.startswith("http"):
            url = "https://" + url
        webbrowser.open(url)
    # =====================================================================

    def update_language(self, lang):
        """Этот метод вызывается автоматически из gui.py при смене языка"""
        self.lbl_title.configure(text=get_text(lang, "about_title"))
        self.lbl_desc.configure(text=get_text(lang, "about_desc"))
        self.lbl_author.configure(text=get_text(lang, "about_author"))
        self.lbl_license.configure(text=get_text(lang, "about_license"))
        self.lbl_license_val.configure(text=get_text(lang, "about_license_val"))
        self.btn_github.configure(text=get_text(lang, "about_btn_github"))
        self.btn_mail.configure(text=get_text(lang, "about_btn_mail"))
        self.lbl_support.configure(text=get_text(lang, "about_support"))
        
        self.lbl_crypto_title.configure(text=get_text(lang, "about_crypto_title"))
        self.lbl_fiat_title.configure(text=get_text(lang, "about_fiat_title"))
        self.lbl_tg_title.configure(text=get_text(lang, "about_tg_title"))

        self.btn_boosty.configure(text=get_text(lang, "about_btn_boosty"))
        self.btn_yoomoney.configure(text=get_text(lang, "about_btn_yoomoney"))
        
        app_text = get_text(lang, "about_btn_app")
        web_text = get_text(lang, "about_btn_web")

        self.btn_tg_rub_app.configure(text=app_text)
        self.btn_tg_rub_web.configure(text=web_text)
        self.btn_tg_eur_app.configure(text=app_text)
        self.btn_tg_eur_web.configure(text=web_text)
        self.btn_tg_usd_app.configure(text=app_text)
        self.btn_tg_usd_web.configure(text=web_text)