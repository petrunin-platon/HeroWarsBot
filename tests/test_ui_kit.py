"""Задача 15, шаг 1: основа нового интерфейса — ui/theme.py, ui/icons, ui/widgets.py.

Без Tk проверяется: цвета совпадают с design/theme.py, титаны и иконки на месте, надписи без эмодзи, две буквы имени,
поиск картинок титанов в assets/icons. Витрина ui/demo.py открывается, только если есть tkinter, customtkinter
и экран (в облаке: xvfb-run -a python3.12 -m pytest tests/test_ui_kit.py).
"""
import importlib.util
import os
import re
import sys
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import i18n  # noqa: E402
from ui import theme  # noqa: E402


def load_design_theme():
    spec = importlib.util.spec_from_file_location("design_theme", ROOT / "design" / "theme.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_colors_match_design():
    design = load_design_theme()
    for group in ("COLORS", "TINTS"):
        ours, theirs = getattr(theme, group), getattr(design, group)
        for key, value in theirs.items():
            assert ours[key] == value, f"{group}[{key}]"
    for element, style in design.ELEMENTS.items():
        ours = theme.ELEMENTS[element]
        for key in ("color", "text", "icon", "tint"):
            assert ours[key] == style[key], f"{element}.{key}"
    assert theme.ELEMENTS["mix"] is theme.ELEMENTS["mixed"]
    for key, value in design.FONTS.items():
        assert theme.FONTS[key] == value
    for key, value in design.SIZES.items():
        assert theme.SIZES[key] == value
    assert theme.blend("#FFFFFF", "#000000", 0.5) == design.blend("#FFFFFF", "#000000", 0.5) == "#808080"


def test_no_hex_outside_theme():
    """Цвета пишутся только в ui/theme.py (design/README.md: «не писать hex руками в виджетах»).
    Исключение — служебный «прозрачный» цвет окошек без рамки в ui/widgets.py."""
    for path in ("ui/widgets.py", "ui/demo.py", "ui/icons/__init__.py"):
        text = (ROOT / path).read_text(encoding="utf-8")
        found = set(re.findall(r'"#[0-9A-Fa-f]{6}"', text)) - {'"#010203"'}
        assert not found, f"{path}: {found}"


def test_titans_same_as_old_ui_and_game_pictures():
    """Имена титанов — внутренние: такие же, как в старом окне выбора, в i18n.py и картинки в assets/."""
    old = (ROOT / "ui" / "team_selector.py").read_text(encoding="utf-8")
    for element, titans in theme.TITANS.items():
        assert f'"{element}": {titans}'.replace("'", '"') in old.replace("'", '"')
        for titan in titans:
            assert (ROOT / "assets" / f"{titan}.png").is_file(), titan
            for lang, words in i18n.TRANSLATIONS.items():
                assert f"titan_{titan}" in words, (lang, titan)
    assert theme.element_of("araji") == "fire"
    assert theme.element_of("metis") is None
    assert theme.element_style(None) is theme.UNKNOWN_ELEMENT


def test_used_icons_exist():
    """Каждая иконка, которую называет код интерфейса, лежит в ui/icons; набор тот же, что в design/icons."""
    ours = {p.stem for p in (ROOT / "ui" / "icons").glob("*.png")}
    assert ours == {p.stem for p in (ROOT / "design" / "icons").glob("*.png")}
    pattern = re.compile(r'(?:icon\(|icon_name=|IconButton\([^,]+, |"icon": |icon=)"([a-z0-9-]+)"')
    used = set()
    for path in (ROOT / "ui").glob("*.py"):
        used |= set(pattern.findall(path.read_text(encoding="utf-8")))
    used |= {style["icon"] for style in theme.ELEMENTS.values()} | {theme.UNKNOWN_ELEMENT["icon"]}
    assert used, "шаблон поиска иконок ничего не нашёл"
    assert used <= ours, used - ours


def is_emoji(ch):
    return unicodedata.category(ch) == "So" or ch in "️‍"


def test_plain_text_removes_emoji_in_all_languages():
    assert theme.plain_text("🌿 Земля") == "Земля"
    assert theme.plain_text("⚔️ Смешанная") == "Смешанная"
    assert theme.plain_text("Открыть →") == "Открыть →"
    assert theme.plain_text("Вода") == "Вода"
    for lang, words in i18n.TRANSLATIONS.items():
        for element in ("earth", "water", "fire", "mix", "light", "dark"):
            text = theme.plain_text(words[f"elem_{element}"])
            assert text and not any(is_emoji(ch) for ch in text), (lang, element, text)


def test_initials():
    assert theme.initials("Араджи") == "Ар"
    assert theme.initials("ARAJI") == "Ar"
    assert theme.initials("Ия") == "Ия"
    assert theme.initials("Мор") == "Мо"
    assert theme.initials("") == "?"
    for lang, words in i18n.TRANSLATIONS.items():
        for titans in theme.TITANS.values():
            for titan in titans:
                assert 1 <= len(theme.initials(words[f"titan_{titan}"])) <= 2, (lang, titan)


def test_titan_icon_path(tmp_path):
    """Картинки титанов для оболочки: assets/icons/<титан>.png; нет картинки — None (рисуются две буквы)."""
    assert theme.titan_icon_path("araji", dirs=(tmp_path,)) is None
    (tmp_path / "araji.png").write_bytes(b"png")
    (tmp_path / "amon.webp").write_bytes(b"webp")
    assert theme.titan_icon_path("araji", dirs=(tmp_path,)) == tmp_path / "araji.png"
    assert theme.titan_icon_path("amon", dirs=(tmp_path / "nothing", tmp_path)) == tmp_path / "amon.webp"
    assert theme.TITAN_ICON_DIRS[0] == Path("assets") / "icons"


def test_assets_icons_folder_is_invisible_to_bot():
    """Бот берёт титанов для слотов только из картинок в корне assets/ (vision.list_root_asset_names: os.path.isfile),
    поэтому папка assets/icons/ с картинками оболочки ему не мешает."""
    code = (ROOT / "vision.py").read_text(encoding="utf-8")
    assert "os.path.isfile(os.path.join(ASSETS_DIR, f))" in code


def _gui_available():
    try:
        import tkinter  # noqa: F401
        import customtkinter  # noqa: F401
    except ImportError:
        return False
    return sys.platform == "win32" or bool(os.environ.get("DISPLAY"))


@pytest.mark.skipif(not _gui_available(), reason="нет tkinter/customtkinter или экрана")
def test_demo_window_builds(monkeypatch):
    """Витрина собирается из всех виджетов без ошибок, на русском и на немецком (самые длинные надписи)."""
    monkeypatch.chdir(ROOT)
    import customtkinter as ctk
    from ui import demo, icons, widgets

    for lang in ("RU", "DE"):
        icons.clear_cache()
        widgets._titan_picture.cache_clear()
        app = demo.Demo(lang)
        app.update()
        assert len(app.fields) == 4 and app.fields[2].error
        assert not app.fields[3].enabled
        avatar = widgets.TitanAvatar(app, "araji", lang=lang)
        assert avatar.label.cget("text") == theme.initials(widgets.titan_name(lang, "araji"))
        assert widgets.titan_name(lang, "metis") == "Metis"
        dialog = widgets.ConfirmDialog(app, "?", "text", "OK", lang=lang, on_confirm=lambda: None)
        app.update()
        dialog._finish("cancel")
        toast = widgets.Toast(app, "text")
        toast.close()
        app.destroy()
    assert isinstance(ctk.CTk, type)
