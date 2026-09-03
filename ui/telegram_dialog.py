# ui/telegram_dialog.py
import customtkinter as ctk
import tkinter as tk
from i18n import get_text

class TelegramDialog(ctk.CTkToplevel):
    def __init__(self, master, controller, current_data, callback):
        super().__init__(master)
        self.controller = controller
        self.callback = callback
        lang = getattr(self.controller, 'current_lang', 'RU')
        
        self.title(get_text(lang, "tg_title"))
        self.geometry("450x250")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.grab_set()
        
        self.grid_columnconfigure(0, weight=1)
        
        self.active_var = ctk.BooleanVar(value=current_data.get("active", False))
        self.chk_active = ctk.CTkCheckBox(self, text=get_text(lang, "tg_enable"), variable=self.active_var, command=self.toggle_fields)
        self.chk_active.grid(row=0, column=0, pady=(20, 10), padx=20, sticky="w")
        
        self.lbl_token = ctk.CTkLabel(self, text=get_text(lang, "tg_token"), font=ctk.CTkFont(weight="bold"))
        self.lbl_token.grid(row=1, column=0, padx=20, sticky="w")
        
        self.entry_token = ctk.CTkEntry(self, width=410, show="*")
        self.entry_token.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="w")
        
        # =====================================================================
        # ЗАЩИТА ОТ NONE (ИСПРАВЛЕНИЕ ОШИБКИ wrong # args)
        # =====================================================================
        token_val = current_data.get("token")
        safe_token = str(token_val) if token_val is not None else ""
        self.entry_token.insert(0, safe_token)
        
        self.lbl_chat = ctk.CTkLabel(self, text=get_text(lang, "tg_chat"), font=ctk.CTkFont(weight="bold"))
        self.lbl_chat.grid(row=3, column=0, padx=20, sticky="w")
        
        self.entry_chat = ctk.CTkEntry(self, width=410)
        self.entry_chat.grid(row=4, column=0, padx=20, pady=(0, 20), sticky="w")
        
        # Защита от None для Chat ID
        chat_val = current_data.get("chat_id")
        safe_chat = str(chat_val) if chat_val is not None else ""
        self.entry_chat.insert(0, safe_chat)
        # =====================================================================
        
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=5, column=0, pady=(0, 20))
        
        self.btn_apply = ctk.CTkButton(self.btn_frame, text=get_text(lang, "btn_apply"), fg_color="#28a745", hover_color="#218838", command=self.on_apply)
        self.btn_apply.pack(side="left", padx=10)
        
        self.btn_cancel = ctk.CTkButton(self.btn_frame, text=get_text(lang, "btn_cancel"), fg_color="#6c757d", hover_color="#5a6268", command=self.destroy)
        self.btn_cancel.pack(side="left", padx=10)
        
        # МЕНЮ ВСТАВКИ ТЕКСТА (ПРАВЫЙ КЛИК МЫШИ)
        self.active_widget = None
        self.context_menu = tk.Menu(self, tearoff=False, bg="#2b2b2b", fg="white", activebackground="#007bff")
        paste_text_lang = "Вставить (Paste)" if lang == "RU" else "Paste"
        self.context_menu.add_command(label=paste_text_lang, command=self.paste_text)

        self.entry_token.bind("<Button-3>", lambda e: self.show_context_menu(e, self.entry_token))
        self.entry_chat.bind("<Button-3>", lambda e: self.show_context_menu(e, self.entry_chat))
        
        self.toggle_fields()
        
    def show_context_menu(self, event, widget):
        if self.active_var.get():
            self.active_widget = widget
            widget.focus_set()
            self.context_menu.tk_popup(event.x_root, event.y_root)

    def paste_text(self):
        try:
            text = self.clipboard_get()
            if self.active_widget and self.active_var.get():
                self.active_widget.insert("insert", text)
        except Exception:
            pass

    def toggle_fields(self):
        state = "normal" if self.active_var.get() else "disabled"
        self.entry_token.configure(state=state)
        self.entry_chat.configure(state=state)
        
    def on_apply(self):
        data = {
            "active": self.active_var.get(),
            "token": self.entry_token.get().strip(),
            "chat_id": self.entry_chat.get().strip()
        }
        self.callback(data)
        self.destroy()