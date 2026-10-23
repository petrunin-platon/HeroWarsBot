"""Задача 15, шаг 8: картинки титанов в окне программы (assets/icons, assets_db.py, ui/theme.py, ui/widgets.py).

Без окна:
- все 29 титанов (28 и Метида) имеют картинку в assets/icons: PNG, читается, не раздувает assets_db.py и .exe;
- источник: сначала папка (замену видно сразу), потом assets_db.py с ключом «icons/имя.png» (так кладёт pack_assets.py);
  корневой «имя.png» из assets_db.py — это шаблон бота (иконка в слоте), окно его не берёт;
- assets_db.py читается один раз и только если в папке картинки нет; нет файла или он повреждён — просто нет картинки;
- бот картинки из icons/ не берёт (и из assets_db.py тоже).
На виртуальном экране (xvfb-run -a python3.12 -m pytest tests/test_ui_titan_icons.py):
- квадрат титана (TitanAvatar, TitanTile) берёт картинку из assets_db.py, битая картинка — две буквы, окно не падает;

"""
import base64
import io
import os
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image  # noqa: E402

from ui import theme  # noqa: E402

ALL_TITANS = [name for names in theme.TITANS.values() for name in names] + theme.ELARITE_ONLY
MAX_ICON_BYTES = 512 * 1024      # картинки уходят в assets_db.py (base64, +33%) и в .exe — до 256–512 пикселей, ~100 КБ


def png_bytes(color, size=(40, 40), fmt="PNG"):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, fmt)
    return buffer.getvalue()


def b64(data):
    return base64.b64encode(data).decode("ascii")


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    """assets_db.py читается один раз на процесс — каждому тесту свой запас."""
    monkeypatch.setattr(theme, "_ICON_DB", None)


# ── Без окна ─────────────────────────────────────────────────────────────────
def test_every_titan_has_a_picture_in_assets_icons():
    """Картинки лежат в репозитории (assets/ в .gitignore: новые добавляют git add -f assets/icons/имя.png)."""
    assert len(ALL_TITANS) == 29
    for titan in ALL_TITANS:
        path = theme.titan_icon_path(titan, dirs=(ROOT / "assets" / "icons",))
        assert path is not None, titan
        assert path.suffix == ".png" and path.stat().st_size <= MAX_ICON_BYTES, (titan, path.stat().st_size)
        with Image.open(path) as picture:                    # pack_assets.py берёт .png и .jpg, не webp
            assert picture.format == "PNG" and min(picture.size) >= 64, (titan, picture.size)


def test_folder_wins_over_assets_db(tmp_path, monkeypatch):
    (tmp_path / "araji.png").write_bytes(png_bytes("red"))
    monkeypatch.setattr(theme, "_icon_db", lambda: {"icons/araji.png": b64(png_bytes("blue"))})
    key, stamp = theme.titan_icon_source("araji", dirs=(tmp_path,))
    assert key == str(tmp_path / "araji.png") and stamp == (tmp_path / "araji.png").stat().st_mtime
    assert theme.open_titan_icon(key).convert("RGB").getpixel((5, 5)) == (255, 0, 0)


def test_assets_db_is_used_when_there_is_no_folder(tmp_path, monkeypatch):
    """Собранный .exe: папки assets/icons нет, картинки — в assets_db.py с ключом «icons/имя.png» (так кладёт pack_assets.py)."""
    db = {"icons/araji.png": b64(png_bytes("blue")), "icons/amon.jpg": b64(png_bytes("green", fmt="JPEG")),
          "icons\\mor.png": b64(png_bytes("red"))}           # ключ с обратной чертой — на всякий случай
    monkeypatch.setattr(theme, "_icon_db", lambda: db)
    key, stamp = theme.titan_icon_source("araji", dirs=(tmp_path / "нет",))
    assert key == "db:icons/araji.png" and stamp == 0
    assert theme.open_titan_icon(key).convert("RGB").getpixel((5, 5)) == (0, 0, 255)
    assert theme.titan_icon_source("amon", dirs=(tmp_path,))[0] == "db:icons/amon.jpg"
    assert theme.titan_icon_source("mor", dirs=(tmp_path,))[0] == "db:icons\\mor.png"
    assert theme.titan_icon_source("sigurd", dirs=(tmp_path,)) is None            # нет нигде — две буквы


def test_root_template_in_assets_db_is_not_a_picture(tmp_path, monkeypatch):
    """«araji.png» в корне assets_db.py — шаблон бота (иконка в слоте, с рамкой и звёздами), в окне ему не место."""
    monkeypatch.setattr(theme, "_icon_db", lambda: {"araji.png": b64(png_bytes("red")),
                                                    "RU/araji.png": b64(png_bytes("red"))})
    assert theme.titan_icon_source("araji", dirs=(tmp_path,)) is None


def test_assets_db_is_read_once_and_only_when_needed(tmp_path, monkeypatch):
    reads = []

    class FakeDb(types.ModuleType):
        @property
        def ASSETS(self):
            reads.append(1)
            return {"icons/araji.png": b64(png_bytes("blue"))}

    monkeypatch.setitem(sys.modules, "assets_db", FakeDb("assets_db"))
    (tmp_path / "amon.png").write_bytes(png_bytes("red"))
    assert theme.titan_icon_source("amon", dirs=(tmp_path,))[0] == str(tmp_path / "amon.png")
    assert reads == []                                       # картинка в папке — assets_db.py не трогаем
    assert theme.titan_icon_source("araji", dirs=(tmp_path,))[0] == "db:icons/araji.png"
    assert theme.titan_icon_source("araji", dirs=(tmp_path,))[0] == "db:icons/araji.png"
    assert len(reads) == 1                                   # прочитан один раз на процесс


def test_no_assets_db_or_broken_one_is_just_no_picture(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "assets_db", None)      # так «файла нет» выглядит для import
    assert theme._icon_db() == {} and theme.titan_icon_source("araji", dirs=(tmp_path,)) is None
    monkeypatch.setattr(theme, "_ICON_DB", None)
    monkeypatch.setitem(sys.modules, "assets_db", types.SimpleNamespace(ASSETS="не словарь"))
    assert theme._icon_db() == {}


def test_bot_does_not_take_icons_from_assets_db_or_folder(monkeypatch):
    """Бот ищет титанов для слотов среди «имя.png» в корне: ключ «icons/имя.png» и папка icons/ ему не мешают."""
    pytest.importorskip("cv2")
    sys.modules.setdefault("pygetwindow", types.ModuleType("pygetwindow"))
    import vision
    monkeypatch.setattr(vision, "ASSETS", {"newtitan.png": "x", "icons/newicon.png": "x", "icons\\newicon.png": "x",
                                           "icons/newtitan.png": "x"})
    monkeypatch.setattr(vision, "ASSETS_DIR", str(ROOT / "assets"))
    names = vision.list_root_asset_names()
    assert "newtitan" in names and "araji" in names
    assert not any("icons" in name or "/" in name or "\\" in name for name in names)
    assert "newicon" not in names and "angus" in names


# ── На виртуальном экране ────────────────────────────────────────────────────
def _gui_available():
    try:
        import tkinter  # noqa: F401
        import customtkinter  # noqa: F401
    except ImportError:
        return False
    return sys.platform == "win32" or bool(os.environ.get("DISPLAY"))


needs_gui = pytest.mark.skipif(not _gui_available(), reason="нет tkinter/customtkinter или экрана")


@pytest.fixture
def root():
    import customtkinter as ctk
    from ui import widgets
    for cached in (widgets._titan_pixels, widgets._titan_picture, widgets._tile_picture):
        cached.cache_clear()
    window = ctk.CTk()
    window.withdraw()
    yield window
    window.destroy()


def only_db(monkeypatch, db, folder=None):
    """В папке картинок нет (или она — folder), остальное — в assets_db.py."""
    original = theme.titan_icon_source
    monkeypatch.setattr(theme, "titan_icon_source",
                        lambda titan: original(titan, dirs=(folder or Path("/нет/такой/папки"),)))
    monkeypatch.setattr(theme, "_icon_db", lambda: db)


@needs_gui
def test_avatar_and_tile_take_the_picture_from_assets_db(root, monkeypatch):
    from ui import widgets
    only_db(monkeypatch, {"icons/araji.png": b64(png_bytes((250, 0, 0), size=(60, 90)))})
    avatar = widgets.TitanAvatar(root, "araji", lang="RU")
    tile = widgets.TitanTile(root, "araji", lang="RU")
    assert avatar.label.cget("text") == "" and avatar.label.cget("image")
    assert tile.cget("text") == "" and tile.cget("image")
    source = widgets.titan_source("araji")
    assert source == ("db:icons/araji.png", 0)
    picture = widgets._tile_picture("araji", 36, 2, "#1B1D26", *source)
    assert picture.getpixel((18, 18))[:3] == (250, 0, 0)                      # в середине — картинка (вырезан квадрат)
    assert max(abs(a - b) for a, b in zip(picture.getpixel((0, 0))[:3], (0x1B, 0x1D, 0x26))) <= 4   # уголок — фон
    assert picture.getpixel((18, 0))[:3] != (250, 0, 0)                        # сверху — рамка цветом стихии
    other = widgets.TitanTile(root, "sigurd", lang="RU")                       # в базе его нет — две буквы
    assert other.cget("text") == "Си" and widgets.titan_source("sigurd") is None


@needs_gui
def test_broken_picture_gives_two_letters_not_a_crash(root, monkeypatch, tmp_path):
    from ui import widgets
    (tmp_path / "amon.png").write_bytes("это не картинка".encode())
    only_db(monkeypatch, {"icons/araji.png": b64("тоже не картинка".encode()), "icons/mor.png": "это не base64 !!!"}, tmp_path)
    for titan, letters in (("amon", "Ам"), ("araji", "Ар"), ("mor", "Мо")):
        avatar = widgets.TitanAvatar(root, titan, lang="RU")
        tile = widgets.TitanTile(root, titan, lang="RU")
        assert widgets.titan_source(titan) is None
        assert avatar.label.cget("text") == letters and tile.cget("text") == letters, titan


@needs_gui
def test_replaced_picture_is_read_again(root, monkeypatch, tmp_path):
    from ui import widgets
    only_db(monkeypatch, {}, tmp_path)
    path = tmp_path / "araji.png"
    path.write_bytes(png_bytes((250, 0, 0)))
    first = widgets.titan_source("araji")
    assert widgets._tile_picture("araji", 36, 2, "#1B1D26", *first).getpixel((18, 18))[:3] == (250, 0, 0)
    path.write_bytes(png_bytes((0, 250, 0)))
    os.utime(path, (first[1] + 5, first[1] + 5))                               # файл заменили позже
    second = widgets.titan_source("araji")
    assert second != first
    assert widgets._tile_picture("araji", 36, 2, "#1B1D26", *second).getpixel((18, 18))[:3] == (0, 250, 0)


@needs_gui
def test_cached_picture_is_not_spoiled_by_squares(root):
    """Картинка декодируется один раз на всех: квадраты разных размеров не портят общую (скругление — на копии)."""
    from ui import widgets
    source = widgets.titan_source("araji")
    whole = widgets._titan_pixels(*source)
    before = whole.copy()
    for size in (20, 26, 36, 72):
        widgets._square_picture(*source, size * 4, 16)
        widgets._tile_picture("araji", size, 2, "#1B1D26", *source)
    assert whole.tobytes() == before.tobytes() and widgets._titan_pixels(*source) is whole


@needs_gui
def test_real_pictures_fill_the_square_inside_the_border(root):
    """Настоящие картинки из assets/icons: рамка цветом стихии, внутри не фон-подложка, а титан."""
    from ui import widgets
    for titan in ("araji", "sigurd", "angus", "amon", "mor", "metida"):
        source = widgets.titan_source(titan)
        assert source is not None, titan
        tile = widgets._tile_picture(titan, 72, 4, "#1B1D26", *source)
        color = theme.element_style(theme.element_of(titan))["color"]
        rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
        assert max(abs(a - b) for a, b in zip(tile.getpixel((36, 2))[:3], rgb)) < 40, titan   # рамка
        assert tile.getpixel((36, 36))[:3] != tuple(int(theme.element_style(theme.element_of(titan))["tint"][i:i + 2], 16)
                                                    for i in (1, 3, 5)), titan                  # внутри — картинка


@needs_gui
def test_dropdown_field_shows_titan_picture(root, monkeypatch):
    from ui import widgets
    only_db(monkeypatch, {"icons/araji.png": b64(png_bytes((250, 0, 0)))})
    items = [("araji", "Араджи"), ("sigurd", "Сигурд")]
    menu = widgets.Dropdown(root, items, "araji", titans=True, lang="RU", width=200)
    menu.grid()
    root.update()
    label = menu._icon_label
    assert menu._label.cget("text") == "Араджи" and label.cget("text") == "" and label.cget("image")
    assert label.winfo_manager() == "grid"
    before = label.cget("image")
    menu.set("sigurd")                                                          # картинки нет — две буквы
    assert menu._label.cget("text") == "Сигурд" and label.cget("text") == "Си" and label.cget("image") != before
    menu.set("araji")
    assert label.cget("text") == "" and label.cget("image") == before
    # наведение меняет только цвет: картинка и текст те же, фон — под уголками
    photo, text = label.cget("image"), label.cget("text")
    menu._hovering = True
    menu._paint()
    assert label.cget("bg") == theme.TINTS["hover_elevated"]
    assert (label.cget("image"), label.cget("text")) == (photo, text)
    # уголки квадрата прозрачные — при наведении под ними цвет рамки, а не «дырка» цвета фона
    source = widgets.titan_source("araji")
    clear = widgets._tile_picture("araji", 26, 2, None, *source)
    assert clear.getpixel((0, 0))[3] == 0 and clear.getpixel((13, 13))[3] == 255
    menu.destroy()


@needs_gui
def test_dropdown_without_titans_flag_keeps_element_icons(root):
    from ui import widgets
    menu = widgets.Dropdown(root, [("earth", "Земля")], "earth", icons={"earth": ("leaf", theme.ELEMENTS["earth"]["color"])},
                            width=200)
    menu.grid()
    root.update()
    assert menu._icon_label.cget("image") and menu._icon_label.cget("text") == ""
    menu.destroy()
