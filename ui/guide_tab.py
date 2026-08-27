# ui/guide_tab.py
import customtkinter as ctk
import tkinter as tk
import os
from i18n import get_text

class GuideFrame(ctk.CTkFrame):
    def __init__(self, master, controller, **kwargs):
        super().__init__(master, corner_radius=10, fg_color="transparent", **kwargs)
        self.controller = controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.lbl_title = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=20, weight="bold"))
        self.lbl_title.grid(row=0, column=0, pady=(20, 10), sticky="w")

        self.guide_textbox = ctk.CTkTextbox(self, wrap="word", fg_color="#1e1e1e", text_color="white")
        self.guide_textbox.grid(row=1, column=0, sticky="nsew", pady=(0, 20))
        
        inner_text = self.guide_textbox._textbox
        inner_text.tag_config("h1", font=ctk.CTkFont(size=22, weight="bold"), foreground="#4da6ff")
        inner_text.tag_config("h2", font=ctk.CTkFont(size=18, weight="bold"), foreground="#007bff", spacing3=5)
        inner_text.tag_config("bold", font=ctk.CTkFont(size=14, weight="bold"))
        inner_text.tag_config("normal", font=ctk.CTkFont(size=14))
        inner_text.tag_config("quote", font=ctk.CTkFont(size=14, slant="italic"), foreground="#a6a6a6")
        
        self.setup_readonly_and_menu(self.guide_textbox)

    def setup_readonly_and_menu(self, textbox):
        def prevent_edit(event):
            if event.state & 0x0004 or event.state & 0x0008:
                if event.keysym.lower() in ['c', 'a']:
                    return None
            if event.keysym in ['Up', 'Down', 'Left', 'Right', 'Prior', 'Next', 'Home', 'End']:
                return None
            return "break"
            
        textbox.bind("<Key>", prevent_edit)
        textbox.bind("<<Paste>>", lambda e: "break")
        textbox.bind("<<Cut>>", lambda e: "break")

        self.context_menu = tk.Menu(self, tearoff=False, bg="#2b2b2b", fg="white", activebackground="#007bff")
        lang = getattr(self.controller, 'current_lang', 'RU')
        self.context_menu.add_command(label=get_text(lang, "ctx_copy"), command=lambda: self.copy_text(textbox))

        textbox.bind("<Button-3>", lambda event: self.show_context_menu(event, textbox))

    def show_context_menu(self, event, textbox):
        try:
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
        self.lbl_title.configure(text=get_text(lang, "guide_title"))
        
        file_name = "guide_ru.md" if lang == "RU" else "guide_en.md"
        file_path = os.path.join("docs", file_name)
        
        guide_content = ""
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    guide_content = f.read()
            except Exception as e:
                guide_content = f"## ОШИБКА ЧТЕНИЯ\n\nНе удалось прочитать файл:\n**{e}**"
        else:
            if lang == "RU":
                guide_content = f"## ОШИБКА 404\n\nФайл не найден: **{file_path}**\nСоздайте папку 'docs' в корне проекта и положите туда файлы руководства."
            else:
                guide_content = f"## ERROR 404\n\nFile not found: **{file_path}**\nCreate a 'docs' folder and put the guide files inside."

        self.render_markdown(guide_content)
        self.context_menu.entryconfigure(0, label=get_text(lang, "ctx_copy"))

    def render_markdown(self, text):
        self.guide_textbox.delete("1.0", "end")
        
        for line in text.split('\n'):
            if line.startswith("# "):
                self.guide_textbox.insert("end", line[2:] + "\n", "h1")
            elif line.startswith("## "):
                self.guide_textbox.insert("end", line[3:] + "\n", "h2")
            elif line.startswith("> "):
                self.guide_textbox.insert("end", "┃ " + line[2:] + "\n", "quote")
            elif line.startswith("* "):
                self.guide_textbox.insert("end", "   • ", "normal")
                self._insert_inline_bold(line[2:])
            else:
                self._insert_inline_bold(line)

    def _insert_inline_bold(self, line):
        parts = line.split("**")
        for i, part in enumerate(parts):
            tag = "normal" if i % 2 == 0 else "bold"
            self.guide_textbox.insert("end", part, tag)
        self.guide_textbox.insert("end", "\n", "normal")