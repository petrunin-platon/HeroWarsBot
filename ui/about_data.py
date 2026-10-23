"""Что показывает «О программе» (задача 15, шаг 7): адреса и ссылки, кошельки, состояние компонентов,
папка программы, открытие ссылок. Без Tk — проверяется тестами (tests/test_ui_about.py).

Адреса и ссылки — те же, что в старой вкладке ui/about_tab.py (она остаётся для start_old.bat до шага 9).
«Проверить обновления» открывает страницу релизов на GitHub (ваш ответ на вопрос 7.1, 23.10.2026): окно само в интернет не ходит.

Репозиторий (GITHUB_REPO) и почта автора (AUTHOR_EMAIL) — в config.py: бот переехал — меняется одна строка там.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

from config import AUTHOR_EMAIL, GITHUB_REPO

GITHUB_URL = f"https://github.com/{GITHUB_REPO}"
RELEASES_URL = GITHUB_URL + "/releases"
AUTHOR = "Platon Petrunin"
EMAIL = AUTHOR_EMAIL
LICENSE_NAME = "PolyForm Noncommercial 1.0.0"
PROJECT_NAME = "Hero Wars: Knowledge Engine Bot"
STAGE = "Beta"

# Кошельки: (ключ, подпись, полный адрес). На экране и в буфер обмена — полный адрес (ваше решение 23.10.2026)
WALLETS = (
    ("usdt", "USDT · TRC20", "TSK3ozZMWCST1a6gbmZ5AfRvK8XAX2xjin"),
    ("btc", "Bitcoin · BTC", "bc1qsu52cvfn4aqcay3mjasyah4hcx73npqvn5re3p"),
    ("eth", "Ethereum · ETH", "0x1e87D47a6Ae8c49508BCC33F1b74FBC27efCFDD5"),
)

# Донат в Telegram (Tribute): (валюта, ссылка в приложении, ссылка в браузере)
TELEGRAM_DONATE = (
    ("RUB", "https://t.me/tribute/app?startapp=dPqn", "https://web.tribute.tg/d/Pqn"),
    ("EUR", "https://t.me/tribute/app?startapp=dwT2", "https://web.tribute.tg/d/wT2"),
    ("USD", "https://t.me/tribute/app?startapp=dPqo", "https://web.tribute.tg/d/Pqo"),
)

# Прямые переводы: (ключ, ключ надписи в i18n.py, ссылка)
DIRECT_DONATE = (
    ("boosty", "about_btn_boosty", "https://boosty.to/petrunin.platon/donate"),
    ("yoomoney", "about_btn_yoomoney", "https://yoomoney.ru/to/410013614193490"),
)

# Состояние компонентов: (ключ, подпись, значок)
COMPONENTS = (
    ("adb", "ADB", "smartphone"),
    ("scrcpy", "scrcpy", "monitor"),
    ("templates", None, "image"),   # подпись «База шаблонов» — из i18n.py
)


def mail_url():
    return f"mailto:{EMAIL}"


def safe_url(url):
    """Защита от пустых и битых ссылок (как в старой вкладке): без схемы — https, пустая — None."""
    if not url or "ВСТАВЬ" in url:
        return None
    return url if url.startswith(("http", "mailto:")) else "https://" + url


def launch(url, opener=None):
    """Открыть ссылку (или mailto:) в браузере / почтовой программе. True — система приняла команду, False — не получилось:
    нет программы для ссылки (в Windows без почтовой программы mailto: не открывается) или ошибка. Тогда окно кладёт ссылку
    в буфер обмена и пишет об этом."""
    url = safe_url(url)
    if not url:
        return False
    try:
        return bool((opener or webbrowser.open)(url))
    except Exception:
        return False


def program_folder():
    """Папка программы: откуда запущено окно (там profile.yml, bot_data/, assets/ — пути бота относительные)."""
    return os.path.abspath(os.getcwd())


def templates_found(find_spec=importlib.util.find_spec, dirs=None):
    """База картинок-шаблонов бота есть: файл assets_db.py (бот берёт картинки из него) или папка assets/ с картинками."""
    try:
        if find_spec("assets_db") is not None:
            return True
    except (ImportError, ValueError):
        pass
    if dirs is None:
        dirs = (Path("assets"), Path(__file__).resolve().parent.parent / "assets")
    for folder in dirs:
        try:
            if folder.is_dir() and next(folder.glob("*.png"), None) is not None:
                return True
        except OSError:
            continue
    return False


def check_components(which=shutil.which, find_spec=importlib.util.find_spec, dirs=None):
    """Что найдено: {"adb": bool, "scrcpy": bool, "templates": bool}. adb и scrcpy ищем в PATH, как их запускает бот."""
    return {"adb": which("adb") is not None, "scrcpy": which("scrcpy") is not None,
            "templates": templates_found(find_spec, dirs)}


def open_folder(path, platform=None, startfile=None, popen=subprocess.Popen):
    """Открыть папку в проводнике. True — команда ушла, False — не получилось (нет папки, нет проводника)."""
    platform = platform or sys.platform
    if not os.path.isdir(path):
        return False
    try:
        if platform == "win32":
            (startfile or os.startfile)(path)
        else:
            popen(["open" if platform == "darwin" else "xdg-open", path])
        return True
    except (OSError, AttributeError):
        return False
