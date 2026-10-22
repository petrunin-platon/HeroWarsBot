"""Настройки самого окна программы (задача 15): то, что нужно только окну, а не боту.

Сейчас это язык окна (ответ пользователя 22.10.2026: запоминать до следующего запуска). Язык окна важен и боту:
окно передаёт его в HEROWARS_LANG, и бот ищет картинки кнопок игры в assets/<язык>/.
Файл bot_data/ui_settings.json (путь — data_paths.ui_settings_file). Бот его не читает.
Модуль без Tk: его проверяют тесты.
"""
import json
import os

import data_paths

DEFAULTS = {"language": "RU"}


def load(path=None):
    """Настройки окна; нет файла или он испорчен — значения по умолчанию (окно всё равно откроется)."""
    path = path or data_paths.ui_settings_file()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    return {**DEFAULTS, **data}


def save(path=None, **changes):
    """Записать изменения (остальные настройки остаются). Сначала во временный файл: обрыв записи не портит файл."""
    path = path or data_paths.ui_settings_file()
    data = load(path)
    data.update(changes)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return data
