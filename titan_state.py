# titan_state.py
# ХП и энергия титанов после последнего боя. Хранятся в bot_data/titan_state.json в пределах игрового дня:
# после перезапуска бота в тот же день они не теряются. В игре они тоже держатся весь день,
# а в момент сброса (reset_hour в профиле, обычно 05:00) у всех снова 100% ХП и 0% энергии.
# Без OpenCV и игры, проверяется тестами (tests/test_titan_state.py).
import json
import os
from datetime import datetime


class TitanMemory(dict):
    """Словарь {титан: {"hp": ..., "energy": ...}}, который сам сохраняется в файл.
    today() — текущий игровой день строкой ("2026-10-19"). Состояние из файла берётся, только если день тот же.
    update() и clear() сразу записывают файл. Ошибка записи бота не останавливает."""

    def __init__(self, path, today):
        super().__init__()
        self.path = path
        self.today = today
        self.day = today()
        self.saved_at = None
        dict.update(self, self._read())

    def _read(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict) or data.get("game_date") != self.day:
            return {}
        self.saved_at = data.get("saved_at")
        titans = data.get("titans")
        if not isinstance(titans, dict):
            return {}
        return {t: s for t, s in titans.items() if isinstance(s, dict) and "hp" in s}

    def save(self):
        try:
            folder = os.path.dirname(self.path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            tmp = f"{self.path}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"game_date": self.day, "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                           "titans": dict(self)}, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except OSError as e:
            print(f"[СОСТОЯНИЕ] Не удалось сохранить состояние титанов: {e}")

    def update(self, *args, **kwargs):
        dict.update(self, *args, **kwargs)
        self.save()

    def clear(self):
        dict.clear(self)
        self.save()

    def new_day(self):
        """Наступил новый игровой день: забыть всех (у всех снова 100% ХП). True, если день сменился."""
        today = self.today()
        if today == self.day:
            return False
        self.day = today
        self.clear()
        return True

    def describe(self):
        """Короткая строка для лога: кто ранен. Пусто, если состояние неизвестно."""
        if not self:
            return ""
        hurt = [f"{t} {s.get('hp')}%" for t, s in sorted(self.items()) if s.get("hp", 100) < 100]
        return ", ".join(hurt) if hurt else "все здоровы (100%)"
