"""Задача 15, шаг 7: «О программе» (ui/about_page.py, данные — ui/about_data.py).

Без окна (ui/about_data.py):
- адреса кошельков на экране сокращены, а кнопка копирует полный; адреса и ссылки такие же, как в старой вкладке;
- состояние компонентов: ADB и scrcpy — в PATH, база шаблонов — assets_db.py или папка assets/ с картинками;
- «Папка бота» открывает проводник нужной командой, нет папки — «не получилось»;
- новые надписи — на 13 языках, слоган и описание — те же, что в старом «about_desc».
На виртуальном экране (xvfb-run -a python3.12 -m pytest tests/test_ui_about.py):
- страница как в макете, кнопки открывают нужные ссылки (релизы GitHub — ваш ответ 7.1), копирование кладёт полный адрес
  в буфер, «Папка бота» с ошибкой показывает уведомление;
- проверка компонентов идёт в фоне и обновляется при каждом показе страницы, язык меняется на лету,
  в страницу не попали элементы CustomTkinter с холстами (кроме карточек и кнопок).
"""
import unicodedata
from pathlib import Path

import pytest

from test_ui_rules import ROOT, app, needs_gui, pump, workdir  # noqa: F401

NEW_KEYS = ["ab_slogan", "ab_text", "ab_support_text", "ab_check_updates", "ab_open_folder", "ab_author_license",
            "ab_components", "ab_author", "ab_license", "ab_templates", "ab_found", "ab_not_found", "ab_loaded",
            "ab_not_loaded", "ab_checking", "ab_support_title", "ab_crypto", "ab_tg_donate", "ab_app", "ab_browser",
            "ab_direct", "ab_copy", "ab_copied", "ab_folder_fail"]
# Совпадают с русским по праву: слова одинаковы в украинском и казахском
SAME_AS_RU = {"UK": {"ab_open_folder", "ab_crypto", "ab_browser"}, "KK": {"ab_license", "ab_crypto", "ab_browser"}}


# ── Без окна ─────────────────────────────────────────────────────────────────
def test_wallets_are_shortened_for_screen_but_full_for_copy():
    from ui import about_data
    short = {key: about_data.shorten(address) for key, _label, address in about_data.WALLETS}
    assert short == {"usdt": "TSK3oz…X2xjin", "btc": "bc1qsu…n5re3p", "eth": "0x1e87…fCFDD5"}   # как в макете 07
    assert about_data.shorten("abc") == "abc"
    assert all(len(address) > 20 for _k, _l, address in about_data.WALLETS)


def test_addresses_and_links_same_as_old_tab():
    """Кошельки и ссылки скопированы из старой вкладки без ошибок: каждый есть в её тексте."""
    from ui import about_data
    old = (ROOT / "ui" / "about_tab.py").read_text(encoding="utf-8")
    for _key, _label, address in about_data.WALLETS:
        assert f'"{address}"' in old
    for _currency, app_url, web_url in about_data.TELEGRAM_DONATE:
        assert f'"{app_url}"' in old and f'"{web_url}"' in old
    for _key, _text, url in about_data.DIRECT_DONATE:
        assert f'"{url}"' in old
    assert f'"{about_data.GITHUB_URL}"' in old
    assert about_data.EMAIL in old.lower()
    assert [c for c, _a, _w in about_data.TELEGRAM_DONATE] == ["RUB", "EUR", "USD"]


def test_safe_url():
    from ui import about_data
    assert about_data.safe_url("") is None and about_data.safe_url("ВСТАВЬ ССЫЛКУ") is None
    assert about_data.safe_url("example.com/x") == "https://example.com/x"
    assert about_data.safe_url(about_data.RELEASES_URL) == "https://github.com/petrunin-platon/HeroWarsBot/releases"
    assert about_data.safe_url(about_data.mail_url()) == "mailto:petrunin.platon@gmail.com"


def test_components_found_like_the_bot_looks(tmp_path):
    from ui import about_data
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "btn_ok.png").write_bytes(b"x")
    nothing = lambda _name: None  # noqa: E731
    no_db = lambda _name: None  # noqa: E731
    found = about_data.check_components(which=lambda n: f"/usr/bin/{n}", find_spec=no_db, dirs=[tmp_path / "assets"])
    assert found == {"adb": True, "scrcpy": True, "templates": True}
    found = about_data.check_components(which=lambda n: "/x/adb" if n == "adb" else None, find_spec=no_db,
                                        dirs=[tmp_path / "nope"])
    assert found == {"adb": True, "scrcpy": False, "templates": False}
    assert about_data.check_components(which=nothing, find_spec=no_db, dirs=[tmp_path])["templates"] is False  # нет картинок
    # assets_db.py есть — этого достаточно (бот берёт картинки из него, папка не нужна)
    assert about_data.templates_found(find_spec=lambda _n: object(), dirs=[tmp_path / "nope"])


def test_open_folder(tmp_path):
    from ui import about_data
    started = []
    assert about_data.open_folder(str(tmp_path), platform="win32", startfile=started.append) and started == [str(tmp_path)]
    popen = []
    assert about_data.open_folder(str(tmp_path), platform="linux", popen=popen.append)
    assert popen == [["xdg-open", str(tmp_path)]]
    popen.clear()
    assert about_data.open_folder(str(tmp_path), platform="darwin", popen=popen.append) and popen[0][0] == "open"
    assert not about_data.open_folder(str(tmp_path / "нет такой"), platform="win32", startfile=started.append)

    def broken(_path):
        raise OSError("нет проводника")
    assert not about_data.open_folder(str(tmp_path), platform="win32", startfile=broken)
    assert about_data.program_folder() == str(Path.cwd())


def test_new_texts_in_all_languages():
    import i18n
    ru = i18n.TRANSLATIONS["RU"]
    for lang, words in i18n.TRANSLATIONS.items():
        for key in NEW_KEYS:
            text = words.get(key)
            assert text, (lang, key)
            assert lang == "RU" or text != ru[key] or key in SAME_AS_RU.get(lang, ()), (lang, key)
            assert not any(unicodedata.category(ch) == "So" for ch in text), (lang, key, text)   # в новом окне эмодзи нет
        # слоган, описание и «поддержать» — те же слова, что в старом «about_desc» этого языка
        version, text, support = words["about_desc"].split("\n\n")
        assert words["ab_slogan"] == version.split("\n", 1)[1] and words["ab_text"] == text
        assert words["ab_support_text"] == support


# ── На виртуальном экране ────────────────────────────────────────────────────
@pytest.fixture
def page(app, monkeypatch):
    from ui import about_data, about_page
    opened = []
    monkeypatch.setattr(about_page.webbrowser, "open", lambda url: opened.append(url))
    monkeypatch.setattr(about_data, "check_components",
                        lambda: {"adb": True, "scrcpy": False, "templates": True})
    app.geometry("1100x720+0+0")
    app.select_frame("about")
    pump(app, 0.5)
    result = app.frames["about"]
    result.opened = opened
    return result


def texts_of(page):
    return {key: widget.cget("text") for widget, key in page._texts}


@needs_gui
def test_page_like_mockup(page):
    from config import APP_VERSION
    from ui.about_page import AboutPage
    assert isinstance(page, AboutPage) and page.winfo_viewable()
    texts = texts_of(page)
    assert texts["ab_check_updates"] == "Проверить обновления" and texts["ab_open_folder"] == "Папка бота"
    assert texts["about_btn_mail"] == "Написать автору" and texts["about_btn_github"] == "GitHub проекта"
    assert texts["ab_author_license"] == "Автор и лицензия" and texts["ab_components"] == "Состояние компонентов"
    assert texts["about_btn_boosty"] == "Поддержать на Boosty" and texts["about_btn_yoomoney"] == "ЮMoney (RUB)"  # без эмодзи
    assert texts["ab_slogan"].startswith("Ультимативный автономный RPA-бот") and "Машину состояний" in texts["ab_text"]
    assert list(page.wallet_buttons) == ["usdt", "btc", "eth"] and list(page.donate_buttons) == ["boosty", "yoomoney"]
    assert APP_VERSION == "1.6.1"


@needs_gui
def test_buttons_open_the_right_links(page):
    from ui import about_data
    buttons = {key: widget for widget, key in page._texts if hasattr(widget, "invoke")}
    buttons["ab_check_updates"].invoke()
    buttons["about_btn_mail"].invoke()
    buttons["about_btn_github"].invoke()
    assert page.opened == ["https://github.com/petrunin-platon/HeroWarsBot/releases",
                           "mailto:petrunin.platon@gmail.com", "https://github.com/petrunin-platon/HeroWarsBot"]
    page.opened.clear()
    page.donate_buttons["boosty"].command()
    page.donate_buttons["yoomoney"].command()
    assert page.opened == [url for _k, _t, url in about_data.DIRECT_DONATE]
    page.opened.clear()
    app_buttons = [w for w, key in page._texts if key == "ab_app"]
    web_buttons = [w for w, key in page._texts if key == "ab_browser"]
    for app_button, web_button in zip(app_buttons, web_buttons):
        app_button.invoke()
        web_button.invoke()
    assert page.opened == [url for _c, app_url, web_url in about_data.TELEGRAM_DONATE for url in (app_url, web_url)]


@needs_gui
def test_copy_button_puts_full_address_to_clipboard(page):
    from ui import about_data
    from ui.widgets import Toast
    for key, _label, address in about_data.WALLETS:
        page.wallet_buttons[key].invoke()
        pump(page, 0.1)
        assert page.clipboard_get() == address and len(address) > len(about_data.shorten(address))
    assert Toast._open and Toast._open[-1].top is not None
    Toast.close_all(page.winfo_toplevel())


@needs_gui
def test_folder_button(page, monkeypatch):
    from ui import about_data, about_page
    from ui.widgets import Toast
    calls = []
    monkeypatch.setattr(about_data, "open_folder", lambda path: calls.append(path) or True)
    page.open_folder()
    assert calls == [about_data.program_folder()] and not Toast._open
    monkeypatch.setattr(about_page.about_data, "open_folder", lambda path: False)
    page.open_folder()
    pump(page, 0.1)
    assert Toast._open and Toast._open[-1].top is not None
    Toast.close_all(page.winfo_toplevel())


@needs_gui
def test_components_checked_in_background_on_every_show(app, monkeypatch):
    from ui import about_data
    answers = iter([{"adb": True, "scrcpy": False, "templates": True},
                    {"adb": True, "scrcpy": True, "templates": False}])
    monkeypatch.setattr(about_data, "check_components", lambda: next(answers))
    app.select_frame("about")
    page = app.frames["about"]
    assert page._status["adb"][1].cget("text") == "проверяю…"          # ответа ещё нет
    pump(app, 1.0, until=lambda: page.found is not None)
    status = {key: name.cget("text") for key, (_mark, name) in page._status.items()}
    assert status == {"adb": "найден", "scrcpy": "не найден", "templates": "загружена"}
    app.select_frame("dash")
    app.select_frame("about")                                          # показали снова — проверили снова
    pump(app, 1.0, until=lambda: page.found == {"adb": True, "scrcpy": True, "templates": False})
    status = {key: name.cget("text") for key, (_mark, name) in page._status.items()}
    assert status == {"adb": "найден", "scrcpy": "найден", "templates": "не найдена"}
    assert page._status["scrcpy"][1].cget("fg") != page._status["templates"][1].cget("fg")   # зелёный и красный


@needs_gui
def test_language_changes_everything(page):
    page.update_language("DE")
    texts = texts_of(page)
    assert texts["ab_check_updates"] == "Nach Updates suchen" and texts["ab_open_folder"] == "Bot-Ordner"
    assert page._status["adb"][1].cget("text") == "gefunden"
    app = page.winfo_toplevel()
    app.set_language("EN")
    pump(page, 0.1)
    assert texts_of(page)["ab_components"] == "Component status"
    assert app.title_label.cget("text") == "About"


@needs_gui
def test_rows_do_not_use_customtkinter_canvases(page):
    """Строки и надписи страницы — обычный Tk (прокрутка в Windows без «дорисовки»); холсты CustomTkinter — только
    карточки (2+1+1+2 панели...), кнопки и три кнопки-копирования."""
    import customtkinter as ctk

    def walk(widget):
        yield widget
        for child in widget.winfo_children():
            yield from walk(child)
    ctk_widgets = [w for w in walk(page) if isinstance(w, (ctk.CTkLabel, ctk.CTkEntry, ctk.CTkSwitch))]
    assert not ctk_widgets
    canvases = [w for w in walk(page) if w.__class__.__module__.startswith("customtkinter") and hasattr(w, "_canvas")]
    assert len(canvases) < 40, len(canvases)
