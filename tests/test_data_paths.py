# Тесты задачи 2: файлы бота лежат в bot_data/, старые файлы копируются один раз и ничего не затирается.
import importlib
import json
import os
import sys

import pytest
import yaml

import data_paths


@pytest.fixture(autouse=True)
def fresh_process_state():
    """data_paths помнит, в какой папке уже проверял bot_data. Для каждого теста — с нуля."""
    data_paths._CHECKED.clear()
    yield
    data_paths._CHECKED.clear()


def write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def make_old_project(root):
    """Папка проекта до переезда: stats.json, правила, история боёв, копия профиля."""
    write(root / "stats.json", '{"total_rooms": 7, "daily": {}}')
    write(root / "profile.yml.bak", "settings: {}\n")
    for room in data_paths.ROOM_TYPES:
        write(root / "rules" / f"{room}.yml", f"default_team: [{room}]\nrules: []\n")
    write(root / "logs" / "battle_log_2026-10-18_13-49-57.jsonl", '{"room": "mix"}\n')
    write(root / "logs" / "battle_log.csv", "2026-10-18 13:49:57,mix,SUCCESS,ok\n")


# ---------------------------------------------------------------------------
# Первый запуск: копирование
# ---------------------------------------------------------------------------
def test_first_run_copies_old_files_and_keeps_originals(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    make_old_project(tmp_path)

    data_paths.ensure_bot_data()

    assert json.loads(read("bot_data/stats.json"))["total_rooms"] == 7
    assert read("bot_data/profile.yml.bak") == "settings: {}\n"
    for room in data_paths.ROOM_TYPES:
        assert read(f"bot_data/rules/{room}.yml") == f"default_team: [{room}]\nrules: []\n"
    assert read("bot_data/logs/battle_log_2026-10-18_13-49-57.jsonl") == '{"room": "mix"}\n'
    assert read("bot_data/logs/battle_log.csv").startswith("2026-10-18")
    # старые файлы остались на месте
    assert os.path.exists("stats.json")
    assert os.path.exists("rules/mix.yml")
    assert os.path.exists("logs/battle_log.csv")
    assert os.path.exists("logs/battle_log_2026-10-18_13-49-57.jsonl")
    assert os.path.exists("profile.yml.bak")


def test_existing_copies_are_not_overwritten(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    make_old_project(tmp_path)
    write(tmp_path / "bot_data" / "stats.json", '{"total_rooms": 999}')
    write(tmp_path / "bot_data" / "rules" / "mix.yml", "default_team: [свой]\n")
    write(tmp_path / "bot_data" / "profile.yml.bak", "новая копия\n")
    write(tmp_path / "bot_data" / "logs" / "battle_log.csv", "уже есть\n")

    data_paths.ensure_bot_data()

    assert json.loads(read("bot_data/stats.json"))["total_rooms"] == 999
    assert read("bot_data/rules/mix.yml") == "default_team: [свой]\n"
    assert read("bot_data/profile.yml.bak") == "новая копия\n"
    assert read("bot_data/logs/battle_log.csv") == "уже есть\n"
    # недостающие файлы при этом докопировались
    assert read("bot_data/rules/water.yml") == "default_team: [water]\nrules: []\n"


def test_second_run_does_not_touch_anything(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    make_old_project(tmp_path)
    data_paths.ensure_bot_data()

    # пользователь поправил рабочую копию, потом процесс запустился заново
    write(tmp_path / "bot_data" / "stats.json", '{"total_rooms": 50}')
    write(tmp_path / "bot_data" / "rules" / "fire.yml", "default_team: [araji]\n")
    data_paths._CHECKED.clear()
    data_paths.ensure_bot_data()

    assert json.loads(read("bot_data/stats.json"))["total_rooms"] == 50
    assert read("bot_data/rules/fire.yml") == "default_team: [araji]\n"


def test_history_is_copied_only_once(tmp_path, monkeypatch):
    """Ротация удалила копию истории — при следующем запуске она не должна вернуться из logs/."""
    monkeypatch.chdir(tmp_path)
    make_old_project(tmp_path)
    data_paths.ensure_bot_data()
    os.remove("bot_data/logs/battle_log_2026-10-18_13-49-57.jsonl")

    data_paths._CHECKED.clear()
    data_paths.ensure_bot_data()

    assert not os.path.exists("bot_data/logs/battle_log_2026-10-18_13-49-57.jsonl")
    assert os.path.exists("logs/battle_log_2026-10-18_13-49-57.jsonl")


def test_clean_install_just_creates_folders(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    data_paths.ensure_bot_data()

    assert os.path.isdir("bot_data/logs")
    assert os.path.isdir("bot_data/rules")
    assert not os.path.exists("bot_data/stats.json")
    assert not os.path.exists("logs")  # пустую logs/ бот не создаёт


def test_works_in_each_folder_separately(tmp_path, monkeypatch):
    first = tmp_path / "first"
    second = tmp_path / "second"
    for folder in (first, second):
        folder.mkdir()
        write(folder / "stats.json", f'{{"total_rooms": {len(folder.name)}}}')

    monkeypatch.chdir(first)
    data_paths.ensure_bot_data()
    monkeypatch.chdir(second)
    data_paths.ensure_bot_data()

    assert json.loads(read(first / "bot_data" / "stats.json"))["total_rooms"] == 5
    assert json.loads(read(second / "bot_data" / "stats.json"))["total_rooms"] == 6


def test_path_helpers_point_into_bot_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert data_paths.stats_file() == "bot_data/stats.json"
    assert data_paths.rules_path("mix") == "bot_data/rules/mix.yml"
    assert data_paths.logs_dir() == "bot_data/logs"
    assert data_paths.profile_backup_file() == "bot_data/profile.yml.bak"
    assert data_paths.temp_sos_file() == "bot_data/temp_sos.png"
    assert data_paths.temp_test_file() == "bot_data/temp_test.png"


# ---------------------------------------------------------------------------
# Статистика
# ---------------------------------------------------------------------------
def test_stats_are_read_and_written_in_bot_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write(tmp_path / "stats.json", json.dumps(
        {"total_titanite": 100, "total_rooms": 7, "total_floors": 1, "total_potions": 0, "daily": {}}))

    import stats_manager
    stats_manager.add_metrics_bulk({"rooms": 1, "titanite": 12}, date_str="2026-10-18", is_bot=True)

    saved = json.loads(read("bot_data/stats.json"))
    assert saved["total_rooms"] == 8                      # старые данные не потерялись
    assert saved["total_titanite"] == 112
    assert saved["daily"]["2026-10-18"]["bot_rooms"] == 1
    # старый stats.json бот больше не меняет, временного файла не осталось
    assert json.loads(read("stats.json"))["total_rooms"] == 7
    assert not os.path.exists("bot_data/stats.json.tmp")
    assert not os.path.exists("stats.json.tmp")


def test_stats_start_from_zero_without_old_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    import stats_manager
    assert stats_manager.load_stats()["total_rooms"] == 0
    stats_manager.add_metrics_bulk({"rooms": 2}, date_str="2026-10-18")

    assert json.loads(read("bot_data/stats.json"))["total_rooms"] == 2
    assert not os.path.exists("stats.json")


# ---------------------------------------------------------------------------
# Правила
# ---------------------------------------------------------------------------
def test_rules_engine_reads_working_copy_and_learns_there(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    make_old_project(tmp_path)
    default_mix = read("rules/mix.yml")
    # рабочая копия отличается от правил по умолчанию — бот должен взять рабочую
    data_paths.ensure_bot_data()
    write(tmp_path / "bot_data" / "rules" / "mix.yml", "default_team: [hyperion, sigurd]\nrules: []\n")

    from rules_engine import RulesEngine
    engine = RulesEngine()
    assert engine.rules_cache["mix"]["default_team"] == ["hyperion", "sigurd"]

    engine.learn_new_rule("mix", ["araji", "nova"], ["hyperion", "sigurd", "iyari"])

    learned = yaml.safe_load(read("bot_data/rules/mix.yml"))
    assert learned["default_team"] == ["hyperion", "sigurd"]
    assert len(learned["rules"]) == 1
    assert learned["rules"][0]["team"] == ["hyperion", "sigurd", "iyari"]
    # rules/ в репозитории — только правила по умолчанию, бот туда не пишет
    assert read("rules/mix.yml") == default_mix


def test_rules_engine_starts_from_default_rules_on_first_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    make_old_project(tmp_path)

    from rules_engine import RulesEngine
    engine = RulesEngine()

    assert engine.rules_cache["earth"]["default_team"] == ["earth"]
    assert os.path.exists("bot_data/rules/earth.yml")


# ---------------------------------------------------------------------------
# История боёв и ротация
# ---------------------------------------------------------------------------
def load_analytics():
    sys.modules.pop("analytics", None)
    return importlib.import_module("analytics")


def test_analytics_writes_history_to_bot_data_and_rotates_only_there(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # ваша папка logs/: история 18.10 и архив сессий — бот их удалять не должен
    write(tmp_path / "logs" / "battle_log_2026-10-18_13-49-57.jsonl", '{"room": "mix"}\n')
    write(tmp_path / "logs" / "session_01-02" / "gui_log.txt", "лог сессии\n")
    for number in range(25):
        write(tmp_path / "logs" / f"user_{number}.txt", "x\n")
    # в bot_data/logs/ накопилось больше 20 файлов — лишние уйдут
    data_paths.ensure_bot_data()
    for number in range(25):
        path = tmp_path / "bot_data" / "logs" / f"old_{number:02d}.jsonl"
        write(path, "{}\n")
        os.utime(path, (1_000_000 + number, 1_000_000 + number))

    analytics = load_analytics()
    analytics.log_battle("mix", ["araji"], ["hyperion"], "SUCCESS", "ok", {"hyperion": {"hp": 90}})

    jsonl_files = [name for name in os.listdir("bot_data/logs") if name.endswith(".jsonl")]
    assert len(jsonl_files) <= 21                           # 20 после ротации + файл этой сессии
    assert "old_00.jsonl" not in jsonl_files               # самые старые удалены
    assert "old_24.jsonl" in jsonl_files
    assert analytics.SESSION_LOG_FILE.startswith("bot_data/logs/battle_log_")
    assert json.loads(read(analytics.SESSION_LOG_FILE))["room"] == "mix"
    assert read(analytics.GUI_LOG_FILE).strip().endswith("mix,SUCCESS,ok")
    # logs/ пользователя не тронута
    assert sorted(os.listdir("logs")) == sorted(
        ["battle_log_2026-10-18_13-49-57.jsonl", "session_01-02"] + [f"user_{n}.txt" for n in range(25)])
    assert read("logs/session_01-02/gui_log.txt") == "лог сессии\n"


def test_analytics_import_does_not_create_logs_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    load_analytics()

    assert not os.path.exists("logs")
    assert os.path.isdir("bot_data/logs")
