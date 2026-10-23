"""Задача 15, шаг 6: «Статистика активности» (ui/stats_page.py, расчёты — ui/stats_data.py).

Без окна (ui/stats_data.py):
- периоды 7, 14, 30 дней и «Всё время» (ваш ответ 6.1); столбиков не больше ~15: 7 и 14 дней — по дням, 30 — по неделям
  (с понедельника, у края — только дни периода), «Всё время» — по дням, неделям или месяцам (ваше замечание);
- плитки — за период, «Всё время» — общие счётчики файла; числа на графике коротко (3.6K, 20K);
- ручная корректировка — как в старой вкладке (нельзя меньше, чем бот собрал сам; комнаты, этажи и зелье по титаниту);
- новые надписи — на 13 языках.
На виртуальном экране (xvfb-run -a python3.12 -m pytest tests/test_ui_stats.py):
- страница как в макете (без нормы и плитки правил), щелчок по столбику — плашка «Показан …», плитки за столбик,
  повторный щелчок и ✕ — снова итоги; дневной столбик подставляется в ручную корректировку, даже старше 7 дней;
- наведение меняет только цвета на холсте, тот же показ страницы ничего не перерисовывает;
- «Применить» пишет stats.json и строку журнала, меньше бота — ошибка без записи; «Сбросить» — только после вопроса;
- «Таблица», смена языка.
"""
import json
from datetime import date, datetime, timedelta

import pytest

from test_ui_rules import ROOT, needs_gui, open_dialog, pump, workdir  # noqa: F401

NEW_KEYS = ["st_hint", "st_period", "st_p_7d", "st_p_14d", "st_p_30d", "st_p_all", "st_titanite", "st_today",
            "st_potions", "st_rooms", "st_floors", "st_chart", "st_by_day", "st_by_week", "st_by_month", "st_table",
            "st_graph", "st_shown_day", "st_shown_week", "st_shown_month", "st_today_mark", "st_per_day",
            "st_per_week", "st_col_date", "st_total", "st_empty", "st_fix", "st_fix_today", "st_fix_yesterday",
            "st_fix_value", "st_apply", "st_reset", "st_fix_bad", "st_fix_below", "st_fix_same", "st_fix_done",
            "st_reset_title", "st_reset_text", "st_reset_done"]
PLACEHOLDERS = {"st_shown_day": "{date}", "st_shown_week": "{date}", "st_shown_month": "{date}",
                "st_fix_today": "{date}", "st_fix_yesterday": "{date}", "st_fix_below": "{n}",
                "st_fix_done": "{total}"}
# Одинаковые с русским по праву: «Титанит» и «График» по-казахски, «Дата» по-украински
SAME_AS_RU = {"KK": {"st_titanite", "st_graph"}, "UK": {"st_col_date"}}

TODAY = date(2026, 10, 22)   # четверг


def day(text):
    return datetime.strptime(text, "%Y-%m-%d").date()


def stats_of(daily, **totals):
    return {"total_titanite": totals.get("titanite", sum(r.get("titanite", 0) for r in daily.values())),
            "total_rooms": totals.get("rooms", sum(r.get("rooms", 0) for r in daily.values())),
            "total_floors": 0, "total_potions": 0, "daily": daily}


# ── Без окна ─────────────────────────────────────────────────────────────────
def test_new_texts_in_all_languages():
    import unicodedata

    import i18n
    ru = i18n.TRANSLATIONS["RU"]
    for lang, words in i18n.TRANSLATIONS.items():
        for key in NEW_KEYS:
            text = words.get(key)
            assert text, (lang, key)
            assert lang == "RU" or text != ru[key] or key in SAME_AS_RU.get(lang, ()), (lang, key)
            assert not any(unicodedata.category(ch) == "So" for ch in text), (lang, key, text)
        for key, mark in PLACEHOLDERS.items():
            assert mark in words[key], (lang, key)


def test_short_numbers():
    from ui.stats_data import compact, full
    assert [compact(v) for v in (0, 850, 1000, 1188, 3588, 20000, 140000, 1_250_000)] == \
        ["0", "850", "1K", "1.2K", "3.6K", "20K", "140K", "1.2M"]
    assert full(7536) == "7 536" and full(105520) == "105 520" and full(0) == "0"


def test_tile_numbers_fit_the_tile():
    """В плитке до 100 000 — полностью, дальше сокращённо (ваше замечание: бывают сотни тысяч и миллионы)."""
    from ui.stats_data import tile_number
    assert [tile_number(v) for v in (0, 7536, 98540, 99999, 100000, 105520, 999_900, 1_000_000, 1_240_000, 25_678_900)] == \
        ["0", "7 536", "98 540", "99 999", "100K", "105.5K", "999.9K", "1M", "1.24M", "25.68M"]
    assert max(len(tile_number(v)) for v in range(0, 100_000_000, 7919)) <= 7    # не длиннее «99 999» / «999.9K»


def test_ticks_cover_the_highest_bar():
    from ui.stats_data import nice_ticks
    for top in (1, 6, 850, 3588, 17236, 140000, 999_999):
        ticks = nice_ticks(top)
        assert ticks[0] == 0 and ticks[-1] >= top and len(ticks) == 5
        assert ticks[-1] <= top * 2 + 4      # не слишком высоко: столбики не прижаты к низу
    assert nice_ticks(0) == [0, 25, 50, 75, 100]


def test_7_and_14_days_by_day():
    from ui.stats_data import buckets
    stats = stats_of({"2026-10-22": {"titanite": 2568, "rooms": 233}, "2026-10-16": {"titanite": 1188},
                      "2026-10-08": {"titanite": 999}})
    week = buckets(stats, "7d", TODAY)
    assert [b["start"] for b in week] == [TODAY - timedelta(days=6 - i) for i in range(7)]
    assert {b["kind"] for b in week} == {"day"} and week[-1]["today"] and not week[0]["today"]
    assert week[0]["titanite"] == 1188 and week[-1]["titanite"] == 2568 and week[-1]["rooms"] == 233
    two = buckets(stats, "14d", TODAY)
    assert len(two) == 14 and two[0]["start"] == day("2026-10-09") and sum(b["titanite"] for b in two) == 3756


def test_30_days_by_week_from_monday():
    from ui.stats_data import buckets
    daily = {(TODAY - timedelta(days=i)).isoformat(): {"titanite": 100} for i in range(40)}
    bars = buckets(stats_of(daily), "30d", TODAY)
    assert {b["kind"] for b in bars} == {"week"} and len(bars) <= 6
    assert bars[0]["start"] == TODAY - timedelta(days=29)                # край периода — только его дни
    assert all(b["start"].weekday() == 0 for b in bars[1:])               # остальные — с понедельника
    assert bars[-1]["start"] == day("2026-10-19") and bars[-1]["end"] == TODAY and bars[-1]["today"]
    assert sum(b["titanite"] for b in bars) == 3000                      # ровно 30 дней
    assert [d for d, _v in bars[-1]["per_day"]] == [day("2026-10-19"), day("2026-10-20"), day("2026-10-21"), TODAY]


@pytest.mark.parametrize("days,kind", [(1, "day"), (14, "day"), (15, "week"), (90, "week"), (200, "month")])
def test_all_time_groups_to_few_bars(days, kind):
    from ui.stats_data import buckets
    daily = {(TODAY - timedelta(days=i)).isoformat(): {"titanite": 12} for i in range(days)}
    daily["2020-01-01"] = {"titanite": 0}    # пустые дни в начале не растягивают график
    bars = buckets(stats_of(daily), "all", TODAY)
    assert {b["kind"] for b in bars} == {kind}
    assert len(bars) <= 15 and sum(b["titanite"] for b in bars) == 12 * days
    assert bars[-1]["end"] == TODAY


def test_all_time_without_data_is_one_day():
    from ui.stats_data import buckets, totals
    bars = buckets(stats_of({}), "all", TODAY)
    assert len(bars) == 1 and bars[0]["titanite"] == 0
    assert totals(stats_of({}), "all", TODAY)["titanite"] == 0


def test_tiles_for_period_and_all_time():
    from ui.stats_data import totals
    stats = stats_of({"2026-10-22": {"titanite": 2568, "rooms": 233, "floors": 44, "potions": 11500},
                      "2026-10-01": {"titanite": 1000}}, titanite=9999, rooms=777)
    week = totals(stats, "7d", TODAY)
    assert (week["titanite"], week["today"], week["rooms"], week["floors"], week["potions"]) == (2568, 2568, 233, 44, 11500)
    everything = totals(stats, "all", TODAY)
    assert (everything["titanite"], everything["rooms"]) == (9999, 777)   # общие счётчики файла, как старая вкладка


def test_manual_correction_like_old_tab():
    from ui.stats_data import calc_rewards, correction, correction_days, parse_total
    stats = stats_of({"2026-10-22": {"titanite": 120, "bot_titanite": 96}})
    assert correction(stats, "2026-10-22", 90) == ("below_bot", 96)
    assert correction(stats, "2026-10-22", 120) == ("same", 0)
    assert calc_rewards(120) == (15, 3, 500) and calc_rewards(60) == (10, 2, 250) and calc_rewards(30) == (5, 1, 125)
    assert correction(stats, "2026-10-22", 180) == ("ok", {"titanite": 60, "rooms": 5, "floors": 1, "potions": 250})
    assert correction(stats, "2026-10-21", 6) == ("ok", {"titanite": 6, "rooms": 1, "potions": 25})
    assert [parse_total(t) for t in ("2568", " 2 568 ", "", "-5", "1.5", "abc")] == [2568, 2568, None, None, None, None]
    days = correction_days(TODAY)
    assert days[0] == TODAY and len(days) == 7
    old = day("2026-09-01")
    assert correction_days(TODAY, old)[-1] == old                      # выбранный на графике день — ваш ответ
    assert correction_days(TODAY, TODAY - timedelta(days=2)) == days    # он уже в списке — не дублируется


# ── На виртуальном экране ────────────────────────────────────────────────────
def write_stats(workdir, stats):
    path = workdir / "bot_data" / "stats.json"
    path.write_text(json.dumps(stats), encoding="utf-8")
    return path


def read_stats(workdir):
    return json.loads((workdir / "bot_data" / "stats.json").read_text(encoding="utf-8"))


@pytest.fixture
def page(workdir, monkeypatch):
    import stats_manager
    from test_ui_rules import Quiet, write_yaml, PROFILE
    import test_ui_app  # noqa: F401
    from ui import app as app_mod
    from ui import icons
    monkeypatch.setattr(stats_manager, "get_game_datetime", lambda: datetime(2026, 10, 22, 12, 0))
    daily = {}
    for i in range(40):
        d = (TODAY - timedelta(days=i)).isoformat()
        daily[d] = {"titanite": 100 * (i % 5 + 1), "rooms": i % 5 + 1, "floors": 1, "potions": 50, "bot_titanite": 60}
    write_stats(workdir, stats_of(daily))
    write_yaml(workdir / "profile.yml", PROFILE)
    icons.clear_cache()
    window = app_mod.App(settings_path=str(workdir / "ui_settings.json"), status_watcher=Quiet(),
                         hotkey_watcher=Quiet())
    window.geometry("1100x720+0+0")
    window.select_frame("stats")
    pump(window, 0.5)
    yield window.frames["stats"]
    if not window._closing:
        window.shutdown()


@needs_gui
def test_page_like_mockup(page):
    assert page.period == "14d" and len(page.bars) == 14
    assert list(page.tiles) == ["titanite", "today", "potions", "rooms", "floors"]   # без нормы и правил (ответы 6.2)
    assert page.tiles["titanite"][1].cget("text") == "4 000"                         # 14 дней
    assert page.tiles["today"][1].cget("text") == "100"
    assert page.hint.winfo_ismapped() and not page.chip.winfo_ismapped()
    assert page.chart.find_withtag("bar") and len(page.chart.find_withtag("bar")) == 14
    assert not page.chart.find_withtag("plate")                                       # чисел над столбиками нет
    page.segments._choose("30d")
    pump(page, 0.2)
    assert page.bars[0]["kind"] == "week" and page.chart_sub.cget("text").endswith(page.text("st_by_week"))
    page.segments._choose("all")
    assert page.tiles["titanite"][1].cget("text") == "12 000"


@needs_gui
def test_big_numbers_are_short_with_full_in_tooltip(page, workdir):
    daily = {"2026-10-22": {"titanite": 1_240_000, "rooms": 105_520, "floors": 98540, "potions": 25_678_900}}
    write_stats(workdir, stats_of(daily, titanite=1_240_000, rooms=105_520))
    page.refresh_data()
    page.segments._choose("7d")
    texts = {name: label.cget("text") for name, (_t, label) in page.tiles.items()}
    assert texts == {"titanite": "1.24M", "today": "1.24M", "potions": "25.68M", "rooms": "105.5K", "floors": "98 540"}
    page.select(6)                                   # выбранный столбик — тоже сокращённо
    assert page.tiles["potions"][1].cget("text") == "25.68M"
    assert page.tile_values["potions"] == 25_678_900  # полное число — для подсказки при наведении


@needs_gui
def test_bar_click_shows_its_numbers(page):
    page.segments._choose("30d")
    pump(page, 0.2)
    last_week = len(page.bars) - 1
    page.select(last_week)
    pump(page, 0.2)
    assert page.chip.winfo_ismapped() and not page.hint.winfo_ismapped()
    assert page.chip_label.cget("text") == "Показана неделя: 19.10–22.10.2026"
    assert page.tiles["titanite"][1].cget("text") == "1 000"                         # 100+500+400+... за 4 дня
    texts = [page.chart.itemcget(i, "text") for i in page.chart.find_withtag("plate") if page.chart.type(i) == "text"]
    assert "По дням" in texts and "19.10" in texts and "22.10" in texts             # у недели — по дням
    fills = {page.chart.itemcget(f"bar{i}", "fill") for i in range(last_week)}
    from ui import theme
    assert fills == {theme.CHART_COLORS["bar_dim"]}                                  # остальные бледнее
    assert page.chart.itemcget(f"bar{last_week}", "fill") == theme.CHART_COLORS["bar_hover"]
    page.chart.on_select(None if last_week == page.selected else last_week)          # повторный щелчок
    assert page.selected is None and page.hint.winfo_ismapped() is not None
    assert not page.chart.find_withtag("plate")
    page.select(1)
    page.chip_label.event_generate("<Button-1>")                                     # ✕ в синей плашке
    pump(page, 0.1)
    assert page.selected is None


@needs_gui
def test_day_bar_goes_to_manual_correction(page):
    page.segments._choose("all")   # 40 дней — по неделям; выберем 14 дней, где по дням
    page.segments._choose("14d")
    page.select(0)                 # 09.10 — старше 7 дней, всё равно подставляется (ваш ответ)
    assert page.fix_day.get() == "2026-10-09"
    assert page.fix_entry.get() == str(page.bars[0]["titanite"])
    assert "2026-10-09" in [k for k, _t in page.fix_day.items]
    page.select(13)
    assert page.fix_day.get() == "2026-10-22" and page.fix_day.items[0][1].startswith("Сегодня")


@needs_gui
def test_hover_changes_only_colors_and_same_data_does_not_redraw(page):
    chart = page.chart
    items = len(chart.find_all())
    drawn = chart._drawn
    calls = []
    original = chart.redraw
    chart.redraw = lambda *a, **k: (calls.append(1), original(*a, **k))[1]
    try:
        chart._hover(3)
        assert chart.itemcget("bar3", "fill") != chart.itemcget("bar2", "fill")
        assert chart.itemcget("tip", "state") == "normal"
        chart._hover(4)
        chart._hover(None)
        assert len(chart.find_all()) == items and chart._drawn == drawn and not calls
        assert chart.itemcget("tip", "state") == "hidden"
        page.refresh_data()                       # страницу показали снова, цифры те же
        pump(page, 0.2)
        assert not calls and len(chart.find_all()) == items
    finally:
        chart.redraw = original
    # Наведение на «Период» — только цвета
    label = page.segments.items["7d"]
    before = label.cget("text"), label.cget("font")
    page.segments._paint("7d", hover=True)
    assert (label.cget("text"), label.cget("font")) == before and label.cget("bg") != page.segments.items["30d"].cget("bg")


@needs_gui
def test_apply_and_errors(page, workdir):
    window = page.winfo_toplevel()
    page.fix_day.set("2026-10-22")
    page._set_entry("abc")
    page.apply_fix()
    assert page._entry_bad and read_stats(workdir)["daily"]["2026-10-22"]["titanite"] == 100
    page._set_entry("50")                         # бот сам собрал 60
    page.apply_fix()
    assert page._entry_bad and read_stats(workdir)["daily"]["2026-10-22"]["titanite"] == 100
    assert "Нельзя указать значение меньше" in window.frames["dash"].log_text()
    page._set_entry("160")
    page.apply_fix()
    data = read_stats(workdir)
    assert data["daily"]["2026-10-22"]["titanite"] == 160 and data["daily"]["2026-10-22"]["bot_titanite"] == 60
    assert "Данные за 2026-10-22 синхронизированы! Дельта: +60 тит." in window.frames["dash"].log_text()
    assert page.tiles["today"][1].cget("text") == "160"          # страница перечитала файл


@needs_gui
def test_reset_asks_first(page, workdir):
    window = page.winfo_toplevel()
    page.ask_reset()
    pump(window, 0.3)
    dialog = open_dialog(window)
    assert dialog is not None
    dialog._finish("cancel")
    assert read_stats(workdir)["total_titanite"] > 0               # отмена — ничего не стёрто
    page.ask_reset()
    pump(window, 0.3)
    open_dialog(window)._finish("confirm")
    assert read_stats(workdir) == {"total_titanite": 0, "total_rooms": 0, "total_floors": 0, "total_potions": 0,
                                   "daily": {}}
    assert page.tiles["titanite"][1].cget("text") == "0"


@needs_gui
def test_table_and_language(page):
    page.toggle_table()
    pump(page, 0.2)
    assert page.table.winfo_ismapped() and not page.chart.winfo_ismapped()
    texts = [w.cget("text") for w in page.table.winfo_children() if hasattr(w, "cget") and "text" in w.keys()]
    assert "Итого" in texts and "22.10.2026 · сегодня" in texts and "4 000" in texts
    page.select(13)
    row = next(cells for index, cells in page.table_rows if index == 13)
    from ui import theme
    assert row[0].cget("bg") == theme.TINTS["blue_on_surface"]
    page.winfo_toplevel().set_language("EN")
    pump(page, 0.2)
    texts = [w.cget("text") for w in page.table.winfo_children() if "text" in w.keys()]
    assert "Total" in texts and page.table_button.cget("text") == "Chart"
    assert page.chip_label.cget("text").startswith("Showing day")
    page.toggle_table()
    pump(page, 0.2)
    assert page.chart.winfo_ismapped() and page.chart.find_withtag("plate")
