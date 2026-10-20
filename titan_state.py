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


# Насколько ХП с экрана должно отличаться от памяти, чтобы считать, что память была неверной (полоски читаются ±2%)
SCREEN_HP_TOLERANCE = 5


def screen_reading(memory, bars):
    """ХП и энергия с экрана выбора команды (задача 9в) против того, что бот помнит.
    memory — {титан: {"hp", "energy"}}; bars — {титан: {"hp": %, "energy": %}}, None — не прочиталось.
    Возвращает (обновления для памяти, строка для лога, кого память не знала или знала неверно).
    Не прочиталось ХП — титана не трогаем. Не прочиталась энергия — оставляем ту, что помним."""
    updates, parts, fixed = {}, [], []
    for titan in sorted(bars):
        hp, energy = bars[titan].get("hp"), bars[titan].get("energy")
        old = memory.get(titan) or {}
        if hp is None:
            parts.append(f"{titan.upper()} не прочиталось")
            continue
        state = {"hp": hp}
        if energy is None:
            energy = old.get("energy")
        if energy is not None:
            state["energy"] = energy
        updates[titan] = state

        text = f"{titan.upper()} {hp}%" + (f" ⚡{energy}%" if energy is not None else "")
        if "hp" not in old:
            text += " (бот не знал)"
            fixed.append(titan)
        elif abs(old["hp"] - hp) >= SCREEN_HP_TOLERANCE:
            text += f" (бот помнил {old['hp']}%)"
            fixed.append(titan)
        parts.append(text)
    return updates, ", ".join(parts), fixed
