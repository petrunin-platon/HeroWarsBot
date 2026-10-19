# Тесты задачи 9: ХП и энергия титанов хранятся в bot_data/titan_state.json в пределах игрового дня.
import json

from titan_state import TitanMemory


class Day:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


def test_state_survives_restart_on_same_day(tmp_path):
    path = str(tmp_path / "bot_data" / "titan_state.json")
    day = Day("2026-10-19")
    memory = TitanMemory(path, day)
    assert memory == {}
    memory.update({"araji": {"hp": 48, "energy": 90}, "rigel": {"hp": 100, "energy": 50}})

    again = TitanMemory(path, day)  # бот перезапущен в тот же игровой день
    assert again["araji"] == {"hp": 48, "energy": 90}
    assert again.saved_at
    assert again.describe() == "araji 48%"


def test_state_from_other_day_is_ignored(tmp_path):
    path = str(tmp_path / "titan_state.json")
    TitanMemory(path, Day("2026-10-18")).update({"araji": {"hp": 48, "energy": 90}})
    assert TitanMemory(path, Day("2026-10-19")) == {}


def test_new_day_while_running_clears_state(tmp_path):
    path = str(tmp_path / "titan_state.json")
    day = Day("2026-10-19")
    memory = TitanMemory(path, day)
    memory.update({"araji": {"hp": 48, "energy": 90}})
    assert not memory.new_day()
    day.value = "2026-10-20"  # 05:00 — сброс дня в игре
    assert memory.new_day()
    assert memory == {}
    saved = json.loads(open(path, encoding="utf-8").read())
    assert saved["game_date"] == "2026-10-20" and saved["titans"] == {}


def test_clear_is_saved(tmp_path):
    path = str(tmp_path / "titan_state.json")
    day = Day("2026-10-19")
    memory = TitanMemory(path, day)
    memory.update({"araji": {"hp": 48, "energy": 90}})
    memory.clear()  # например, после «Пройти руками»
    assert TitanMemory(path, day) == {}


def test_broken_file_is_ignored(tmp_path):
    path = tmp_path / "titan_state.json"
    path.write_text("{сломан", encoding="utf-8")
    assert TitanMemory(str(path), Day("2026-10-19")) == {}
    path.write_text(json.dumps({"game_date": "2026-10-19", "titans": {"araji": "плохо", "rigel": {"hp": 30}}}),
                    encoding="utf-8")
    assert TitanMemory(str(path), Day("2026-10-19")) == {"rigel": {"hp": 30}}


def test_describe():
    memory = TitanMemory.__new__(TitanMemory)
    dict.__init__(memory, {"a": {"hp": 100}, "b": {"hp": 100}})
    assert memory.describe() == "все здоровы (100%)"
