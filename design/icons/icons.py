"""Иконки интерфейса для CustomTkinter.

В папке лежат белые PNG 64×64 (набор Lucide, лицензия ISC — см. LICENSE-lucide.txt).
Функция icon() перекрашивает белую иконку в нужный цвет и отдаёт CTkImage.

Пример:
    from design.icons.icons import icon
    btn = ctk.CTkButton(parent, text="Сохранить лог", image=icon("save", "#A9AFC2"), compound="left")
"""
from functools import lru_cache
from pathlib import Path

import customtkinter as ctk
from PIL import Image

ICON_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=512)
def _colored(name: str, color: str) -> Image.Image:
    src = Image.open(ICON_DIR / f"{name}.png").convert("RGBA")
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    out = Image.new("RGBA", src.size, (r, g, b, 255))
    out.putalpha(src.getchannel("A"))
    return out


@lru_cache(maxsize=512)
def icon(name: str, color: str = "#A9AFC2", size: int = 18) -> ctk.CTkImage:
    """name — имя файла без .png (например 'house', 'play-filled'); color — #RRGGBB."""
    img = _colored(name, color.upper())
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
