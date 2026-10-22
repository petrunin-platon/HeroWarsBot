"""Иконки интерфейса (задача 15). Копия design/icons: белые PNG 64×64 из набора Lucide (лицензия ISC — LICENSE-lucide.txt).

icon("house", COLORS["blue_text"], 20) перекрашивает белую иконку в нужный цвет и отдаёт CTkImage.
dot(COLORS["success"], 8) — круглая точка (статус «подключено», фильтры стихий): в Tk нет такого виджета.
Картинки запоминаются (lru_cache) и принадлежат одному окну Tk: после закрытия окна и создания нового — clear_cache().
"""
from functools import lru_cache
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageDraw

from ui.theme import COLORS

ICON_DIR = Path(__file__).resolve().parent


def _rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


@lru_cache(maxsize=512)
def _colored(name, color):
    src = Image.open(ICON_DIR / f"{name}.png").convert("RGBA")
    out = Image.new("RGBA", src.size, _rgb(color) + (255,))
    out.putalpha(src.getchannel("A"))
    return out


@lru_cache(maxsize=512)
def icon(name, color=COLORS["text_secondary"], size=18):
    """name — имя файла без .png (например 'house', 'play-filled'); color — #RRGGBB; size — сторона в пикселях."""
    img = _colored(name, color.upper())
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


@lru_cache(maxsize=64)
def dot(color, size=8):
    """Круглая точка нужного цвета. Рисуется в 4 раза крупнее и уменьшается — так края гладкие."""
    big = size * 4
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((0, 0, big - 1, big - 1), fill=_rgb(color.upper()) + (255,))
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


def clear_cache():
    """Забыть готовые картинки (нужно, если окно Tk закрыли и создали новое — например, в тестах)."""
    icon.cache_clear()
    dot.cache_clear()
