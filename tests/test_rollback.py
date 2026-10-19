# Тесты задачи 5: надёжный откат боя (пауза → «Отступить»).
# Игры и телефона нет, поэтому экран подделываем: Game показывает то, что показала бы игра в каждый момент,
# а FakeTime двигает время только когда бот «спит» или «жмёт».
import importlib
import sys
import types

import pytest

sys.modules.setdefault("pygetwindow", types.ModuleType("pygetwindow"))

import rollback_logic as rl  # noqa: E402


class FakeTime:
    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now

    monotonic = time

    def sleep(self, seconds):
        self.now += seconds


@pytest.fixture
def clock():
    return FakeTime()


class Game:
    """Экран игры после «Ещё раз».

    load_s          — сколько секунд идёт загрузка (на экране ничего знакомого);
    lost_pauses     — сколько первых нажатий паузы игра «теряет» (меню не открывается);
    menu_delay_s    — через сколько секунд после нажатия паузы появляется меню с «Отступить»;
    battle_ends_at  — через сколько секунд после «Ещё раз» ручной бой заканчивается (окно результата без «Ещё раз»);
    menu_closed_at  — когда пользователь нажал в меню «Продолжить» (меню исчезает, бой идёт дальше);
    hallway_delay_s — через сколько секунд после «Отступить» виден коридор (None — никогда);
    never_pause     — кнопка паузы так и не появляется.
    """

    def __init__(self, clock, load_s=3.0, lost_pauses=0, menu_delay_s=0.8, battle_ends_at=None,
                 menu_closed_at=None, hallway_delay_s=1.0, never_pause=False, retreat_works=True):
        self.clock = clock
        self.t0 = clock.now
        self.load_s = load_s
        self.lost_pauses = lost_pauses
        self.menu_delay_s = menu_delay_s
        self.battle_ends_at = battle_ends_at
        self.menu_closed_at = menu_closed_at
        self.hallway_delay_s = hallway_delay_s
        self.never_pause = never_pause
        self.retreat_works = retreat_works
        self.pause_taps = []
        self.retreat_presses = 0
        self.retry_presses = 0
        self.menu_opens_at = None
        self.retreated_at = None
        self.logs = []

    def t(self):
        return self.clock.now - self.t0

    def menu_open(self):
        if self.menu_opens_at is None or self.t() < self.menu_opens_at:
            return False
        # «Продолжить» закрывает только то меню, которое было открыто до этого момента
        closed = self.menu_closed_at is not None and self.menu_opens_at < self.menu_closed_at <= self.t()
        return not closed

    def look(self):
        t = self.t()
        if self.retreated_at is not None:
            if self.hallway_delay_s is not None and self.clock.now - self.retreated_at >= self.hallway_delay_s:
                return rl.HALLWAY
            return None
        if self.battle_ends_at is not None and t >= self.battle_ends_at:
            return rl.OK
        if self.menu_open():
            return rl.RETREAT  # кнопка паузы при этом тоже видна, но «Отступить» важнее
        if t >= self.load_s and not self.never_pause:
            return rl.PAUSE
        return None

    def tap_pause(self):
        self.pause_taps.append(self.t())
        if len(self.pause_taps) > self.lost_pauses and not self.menu_open():
            self.menu_opens_at = self.t() + self.menu_delay_s
        self.clock.sleep(0.15)  # как настоящий click_human

    def press_retreat(self):
        self.retreat_presses += 1
        self.clock.sleep(0.6)
        if self.menu_open() and self.retreat_works:
            self.retreated_at = self.clock.now
            return True
        self.clock.sleep(3.4)  # find_and_click_bulletproof ждал кнопку впустую
        return False

    def press_retry(self):
        self.retry_presses += 1
        self.clock.sleep(0.6)
        return True

    def run(self, pause_flag=lambda: False, **kwargs):
        return rl.retreat_from_battle(
            look=self.look, tap_pause=self.tap_pause, press_retreat=self.press_retreat, press_retry=self.press_retry,
            pause_flag_set=pause_flag, log=self.logs.append, clock=self.clock.monotonic, sleep=self.clock.sleep,
            **kwargs)


# ---------------------------------------------------------------------------
# Основные сценарии
# ---------------------------------------------------------------------------
def test_long_loading_25s_one_pause_tap_then_retreat(clock):
    """Загрузка 25 с: бот ждёт, жмёт паузу ровно один раз, потом «Отступить»."""
    game = Game(clock, load_s=25.0)
    result = game.run()
    assert result.ok and result.code == rl.DONE
    assert len(game.pause_taps) == 1
    assert game.pause_taps[0] >= 25.0
    assert game.retreat_presses == 1


def test_pause_is_not_tapped_while_retreat_is_visible(clock):
    """Пока открыто меню с «Отступить», кнопка паузы тоже видна — по ней жать нельзя."""
    game = Game(clock, load_s=1.0, menu_delay_s=2.5)
    result = game.run()
    assert result.ok
    assert len(game.pause_taps) == 1


def test_menu_not_opened_first_time_pause_tapped_again(clock):
    """Меню паузы открылось только со второго раза: повтор не раньше, чем через PAUSE_MENU_WAIT_S."""
    game = Game(clock, load_s=5.0, lost_pauses=1)
    result = game.run()
    assert result.ok
    assert len(game.pause_taps) == 2
    assert game.pause_taps[1] - game.pause_taps[0] >= rl.PAUSE_MENU_WAIT_S


def test_two_lost_pause_taps(clock):
    game = Game(clock, load_s=5.0, lost_pauses=2)
    result = game.run()
    assert result.ok
    assert len(game.pause_taps) == 3


def test_user_pressed_continue_in_pause_menu_bot_pauses_again(clock):
    """Во время отката в меню паузы нажали «Продолжить»: бот снова ставит паузу и отступает."""
    game = Game(clock, load_s=2.0, menu_closed_at=3.0)
    result = game.run()
    assert result.ok
    assert len(game.pause_taps) == 2
    assert game.retreat_presses >= 1


def test_battle_ended_before_pause_means_no_rollback(clock):
    """Бой закончился раньше: на экране окно результата без «Ещё раз». Откат невозможен — пауза не нажимается."""
    game = Game(clock, load_s=40.0, battle_ends_at=12.0)
    result = game.run()
    assert not result.ok and result.code == rl.BATTLE_ENDED
    assert game.pause_taps == []
    assert "Ещё раз" in result.text


def test_result_window_flicker_right_after_retry_is_ignored(clock):
    """Старое окно результата мелькнуло на одном снимке — это не конец боя."""
    game = Game(clock, load_s=6.0)
    real_look = game.look
    seen = {"n": 0}

    def look():
        seen["n"] += 1
        return rl.OK if seen["n"] == 1 else real_look()

    game.look = look
    result = game.run()
    assert result.ok


def test_pause_never_appears_gives_up_after_60s(clock):
    game = Game(clock, never_pause=True)
    result = game.run()
    assert result.code == rl.PAUSE_TIMEOUT
    assert 60.0 <= game.t() < 61.0
    assert "Кнопка паузы не появилась" in result.text


def test_menu_never_opens_reports_pause_taps(clock):
    game = Game(clock, load_s=2.0, lost_pauses=1000)
    result = game.run()
    assert result.code == rl.PAUSE_TIMEOUT
    assert len(game.pause_taps) >= 10
    assert "«Отступить» не появилась" in result.text


def test_retreat_pressed_but_no_hallway(clock):
    game = Game(clock, load_s=2.0, hallway_delay_s=None)
    result = game.run()
    assert result.code == rl.NO_HALLWAY


def test_retreat_never_works_gives_up(clock):
    """Меню видно, но «Отступить» не нажимается — не бесконечно."""
    game = Game(clock, load_s=1.0, retreat_works=False)
    result = game.run()
    assert result.code in (rl.RETREAT_FAILED, rl.PAUSE_TIMEOUT)
    assert game.retreat_presses <= rl.RETREAT_MAX_PRESSES + 1


def test_soft_pause_stops_rollback(clock):
    game = Game(clock, load_s=3.0)
    result = game.run(pause_flag=lambda: game.t() > 1.0)
    assert result.code == rl.SOFT_PAUSE
    assert game.pause_taps == []


def test_already_in_hallway_is_done(clock):
    game = Game(clock)
    game.look = lambda: rl.HALLWAY
    assert game.run().ok


def test_retry_window_still_on_screen_presses_retry_again_limited(clock):
    game = Game(clock)
    game.look = lambda: rl.RETRY
    result = game.run()
    assert result.code == rl.RETRY_LOST
    assert game.retry_presses == rl.RETRY_MAX_EXTRA


def test_steps_are_logged(clock):
    game = Game(clock, load_s=3.0)
    game.run()
    text = "\n".join(game.logs)
    assert "кнопку паузы" in text and "Отступить" in text and "коридор" in text


def test_result_is_truthy_only_when_done():
    assert rl.RollbackResult(rl.DONE)
    assert not rl.RollbackResult(rl.BATTLE_ENDED, "x")


# ---------------------------------------------------------------------------
# combat.execute_rollback: экраны подделаны на уровне поиска картинок
# ---------------------------------------------------------------------------
@pytest.fixture
def combat(clock, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ("combat", "rules_engine", "analyzer"):
        sys.modules.pop(name, None)
    module = importlib.import_module("combat")
    monkeypatch.setattr(module, "time", clock)
    yield module
    for name in ("combat", "rules_engine", "analyzer"):
        sys.modules.pop(name, None)


def wire_combat(combat, clock, visible):
    """visible() — множество имён картинок, видимых сейчас. Возвращает списки нажатий."""
    taps, pressed = [], []

    def fake_loc(name, rect, sct, threshold):
        return (10, 10) if name in visible() else None

    def fake_bulletproof(name, rect, sct, threshold, timeout=6.0):
        pressed.append(name)
        clock.sleep(0.5)
        return True

    def fake_click(x, y, **kwargs):
        taps.append((x, y))
        clock.sleep(0.15)

    combat.get_match_loc = fake_loc
    combat.find_and_click_bulletproof = fake_bulletproof
    combat.click_human = fake_click
    return taps, pressed


def test_execute_rollback_full_chain(combat, clock):
    t0 = clock.now
    state = {"retreated": None}

    def visible():
        t = clock.now - t0
        if state["retreated"] is not None:
            return {"btn_attack.png"}
        if t < 3.0:
            return set()
        if len(taps) == 0:
            return {"btn_pause.png"}
        return {"btn_pause.png", "btn_retreat.png"}  # меню открыто, кнопка паузы тоже видна

    taps, pressed = wire_combat(combat, clock, visible)
    orig = combat.find_and_click_bulletproof

    def bulletproof(name, *a, **k):
        res = orig(name, *a, **k)
        if name == "btn_retreat.png":
            state["retreated"] = clock.now
        return res

    combat.find_and_click_bulletproof = bulletproof
    result = combat.execute_rollback({"left": 0, "top": 0, "width": 100, "height": 100}, None)
    assert result.ok
    assert pressed == ["btn_retry.png", "btn_retreat.png"]
    assert len(taps) == 1  # пауза нажата один раз


def test_execute_rollback_without_retry_button_fails_at_once(combat, clock):
    taps, pressed = wire_combat(combat, clock, lambda: set())
    combat.find_and_click_bulletproof = lambda *a, **k: False
    result = combat.execute_rollback({"left": 0, "top": 0, "width": 100, "height": 100}, None)
    assert result.code == rl.NO_RETRY


def test_execute_rollback_in_running_battle_does_not_press_retry(combat, clock):
    t0 = clock.now
    state = {"retreated": None}

    def visible():
        if state["retreated"] is not None:
            return {"flag_enter.png"}
        return {"btn_pause.png", "btn_retreat.png"}

    taps, pressed = wire_combat(combat, clock, visible)

    def bulletproof(name, *a, **k):
        pressed.append(name)
        state["retreated"] = clock.now
        return True

    combat.find_and_click_bulletproof = bulletproof
    result = combat.execute_rollback({"left": 0, "top": 0, "width": 100, "height": 100}, None, press_retry=False)
    assert result.ok
    assert pressed == ["btn_retreat.png"]
    assert taps == []


# ---------------------------------------------------------------------------
# telegram_agent.send_alert: сообщение о неудачном откате
# ---------------------------------------------------------------------------
@pytest.fixture
def tg(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("telegram_agent", None)
    module = importlib.import_module("telegram_agent")
    calls = []

    class Resp:
        def __init__(self, data):
            self.data = data

        def json(self):
            return self.data

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return Resp({"ok": True})

    monkeypatch.setattr(module.requests, "post", fake_post)
    module.calls = calls
    yield module
    sys.modules.pop("telegram_agent", None)


def write_profile(tmp_path, active=True, token="123:ABC", chat_id="42"):
    (tmp_path / "profile.yml").write_text(
        f"settings:\n  telegram:\n    active: {str(active).lower()}\n    token: '{token}'\n    chat_id: '{chat_id}'\n",
        encoding="utf-8")


def test_send_alert_with_screenshot(tg, tmp_path):
    write_profile(tmp_path)
    image = tmp_path / "shot.png"
    image.write_bytes(b"png")
    sent, note = tg.send_alert("Откат не удался", str(image))
    assert sent
    url, kwargs = tg.calls[0]
    assert url.endswith("/bot123:ABC/sendPhoto")
    assert kwargs["data"]["chat_id"] == "42"
    assert "Откат не удался" in kwargs["data"]["caption"]


def test_send_alert_without_screenshot_sends_text(tg, tmp_path):
    write_profile(tmp_path)
    sent, _ = tg.send_alert("Привет")
    assert sent and tg.calls[0][0].endswith("/sendMessage")


def test_send_alert_disabled_or_no_token_sends_nothing(tg, tmp_path):
    write_profile(tmp_path, active=False)
    assert tg.send_alert("x")[0] is False
    write_profile(tmp_path, token="")
    assert tg.send_alert("x")[0] is False
    write_profile(tmp_path, token="YOUR_BOT_TOKEN_HERE")
    assert tg.send_alert("x")[0] is False
    assert tg.calls == []


def test_send_alert_no_profile_does_not_raise(tg):
    sent, note = tg.send_alert("x")
    assert sent is False and note


def test_send_alert_network_error_does_not_raise(tg, tmp_path, monkeypatch):
    write_profile(tmp_path)

    def boom(*a, **k):
        raise OSError("нет сети")

    monkeypatch.setattr(tg.requests, "post", boom)
    sent, note = tg.send_alert("x")
    assert sent is False and "нет сети" in note
