# click_logic.py
# Логика надёжных нажатий: когда повторять нажатие, когда дверь «стоит на месте», когда картинка замерла,
# пауза реакции перед нажатием (задача 10).
# Без OpenCV и игры, поэтому проверяется тестами (tests/test_click_logic.py, tests/test_waits.py).
import random
import time

# --- Повторное нажатие кнопки ---
# Жмём снова, только если через столько секунд ПОСЛЕ того, как команда нажатия дошла до телефона, кнопка всё ещё на экране.
# Сессия 05: после нажатия окно часто «думает» (затемнение и кружок загрузки), закрывается в среднем через ~3 с, иногда дольше.
# При 1,5 с бот жал повторно во время загрузки (117 лишних нажатий за 90 комнат), поэтому ждём 4 с.
RETRY_AFTER_S = 4.0
# Если нажатие выполняется дольше этого времени, считаем его выполненным (adb завис, ждать дальше нет смысла)
TAP_HARD_LIMIT_S = 4.0
# Окно уже реагирует (закрывается, двигается): совпадение с картинкой упало на столько...
REACT_SCORE_DROP = 0.10
# ...или кнопка сдвинулась на столько пикселей. Тогда повтор откладывается (но не дольше, чем до 2 × RETRY_AFTER_S)
REACT_MOVE_PX = 6

# --- Дверь в коридоре ---
# Жмём, когда флажок виден в одной точке (±допуск) в стольких снимках подряд...
DOOR_STABLE_SHOTS = 3
DOOR_STABLE_TOL_PX = 3
# ...и это длится не меньше стольких секунд
DOOR_STABLE_MIN_SPAN_S = 0.2
# Если флажок так и не встал на место — жмём всё равно, чтобы не зависнуть
DOOR_STABLE_GIVE_UP_S = 3.0
# После нажатия на дверь ждём окно «Атаковать» столько секунд после того, как команда дошла до телефона
DOOR_REACT_S = 2.0
# Нажимаем в центральную часть зоны под флажком: по 25% с каждого края не трогаем (раньше было 10%)
DOOR_CENTER_MARGIN = 0.25
DOOR_ZONE_W = 165
DOOR_ZONE_H = 245

# --- Переход на новый этаж ---
# После «Забрать» ждём, пока на новом этаже появится флажок двери, но не дольше этого времени.
# Спуск на этаж идёт ~8–10 с, в это время «Активировать» ещё виден — повторно его нажимать нельзя.
FLOOR_FLAG_WAIT_S = 12.0

# --- Начало боя ---
# Сколько раз пробуем начать бой («Авто»), если экран выбора команды не закрылся. Потом бот останавливается
START_BATTLE_ATTEMPTS = 3

# --- Человеческая скорость нажатий (задача 10, ваш ответ на вопрос 13) ---
# Пауза реакции: нажимаем не раньше, чем через столько секунд (случайно) после того, как кнопка ПОЯВИЛАСЬ на экране.
# Если бот и так думал дольше (читал ХП, разбирал двери), лишнего ожидания нет
REACTION_S = (0.3, 0.8)
# И не больше 2 нажатий в секунду
MIN_TAP_INTERVAL_S = 0.5

# --- «Экран замер» (задача 10): вместо фиксированных пауз ---
# Два снимка подряд показывают одно и то же, и между ними не меньше столько секунд (если снимок делается дольше, не ждём)
STILL_INTERVAL_S = 0.3
# Дольше не ждём: берём последний снимок
STILL_TIMEOUT_S = 2.0

# Ответы RetryPolicy.observe
WAIT, RETRY, DONE = "WAIT", "RETRY", "DONE"


class TapWatch:
    """Следит за командой `adb shell input tap`: когда она дошла до телефона."""

    def __init__(self, proc, clock=time.monotonic, hard_limit=TAP_HARD_LIMIT_S):
        self._proc = proc
        self._clock = clock
        self._hard_limit = hard_limit
        self._started = clock()
        self._done_at = None

    def done_time(self):
        """Момент, когда нажатие выполнилось. None — ещё выполняется."""
        if self._done_at is None:
            now = self._clock()
            if self._proc is None or self._proc.poll() is not None:
                self._done_at = now
            elif now - self._started >= self._hard_limit:
                self._done_at = now
        return self._done_at

    def duration(self):
        """Сколько секунд выполнялась команда нажатия. None — ещё выполняется."""
        done = self.done_time()
        return None if done is None else done - self._started


class RetryPolicy:
    """Решает, пора ли нажать кнопку ещё раз. Вызывается после каждого снимка экрана.

    - кнопки на экране нет — DONE (нажатие сработало);
    - команда нажатия ещё выполняется — WAIT;
    - кнопка на месте, но окно уже реагирует (совпадение упало или кнопка сдвинулась) — WAIT дольше;
    - прошло RETRY_AFTER_S после выполнения нажатия, а экран прежний — RETRY.
    """

    def __init__(self, watch, base_score, base_pos, retry_after=RETRY_AFTER_S, clock=time.monotonic):
        self._watch = watch
        self._base_score = base_score
        self._base_pos = base_pos
        self._retry_after = retry_after
        self._clock = clock
        self._hold_until = 0.0

    def tap_duration(self):
        return self._watch.duration()

    def seconds_since_tap(self):
        done = self._watch.done_time()
        return None if done is None else self._clock() - done

    def _reacting(self, score, pos):
        if score is not None and self._base_score is not None and self._base_score - score >= REACT_SCORE_DROP:
            return True
        if pos is not None and self._base_pos is not None:
            return max(abs(pos[0] - self._base_pos[0]), abs(pos[1] - self._base_pos[1])) >= REACT_MOVE_PX
        return False

    def observe(self, seen, score=None, pos=None):
        if not seen:
            return DONE
        done = self._watch.done_time()
        if done is None:
            return WAIT
        now = self._clock()
        if self._reacting(score, pos):
            # Окно закрывается: даём ещё времени, но не дольше 2 × RETRY_AFTER_S после нажатия
            self._hold_until = min(now + self._retry_after, done + 2 * self._retry_after)
        if now - done >= self._retry_after and now >= self._hold_until:
            return RETRY
        return WAIT


class StableTracker:
    """Считает снимки, на которых предмет (флажок двери) стоит на одном месте."""

    def __init__(self, clock=time.monotonic, shots=DOOR_STABLE_SHOTS, tol=DOOR_STABLE_TOL_PX,
                 min_span=DOOR_STABLE_MIN_SPAN_S, give_up=DOOR_STABLE_GIVE_UP_S):
        self._clock = clock
        self._shots = shots
        self._tol = tol
        self._min_span = min_span
        self._give_up = give_up
        self.gave_up = False
        self.reset()

    def reset(self):
        """Предмета на экране нет."""
        self._first_seen = None
        self._streak = []
        self.gave_up = False

    @property
    def first_seen(self):
        """Когда предмет появился на экране (None — его нет). От этого момента считается пауза реакции."""
        return self._first_seen

    def update(self, pos):
        """Новый снимок, на котором предмет найден в точке pos. True — можно нажимать."""
        now = self._clock()
        if self._first_seen is None:
            self._first_seen = now
        anchor = self._streak[0][1] if self._streak else None
        if anchor is not None and max(abs(pos[0] - anchor[0]), abs(pos[1] - anchor[1])) > self._tol:
            self._streak = []
        self._streak.append((now, pos))
        if len(self._streak) >= self._shots and now - self._streak[0][0] >= self._min_span:
            return True
        if now - self._first_seen >= self._give_up:
            self.gave_up = True
            return True
        return False


def door_click_zone(flag_x, flag_y, flag_w, flag_h, scale, margin=DOOR_CENTER_MARGIN):
    """Прямоугольник (x1, y1, x2, y2), куда можно нажимать на дверь: под флажком, ближе к центру двери."""
    door_w = int(DOOR_ZONE_W * scale)
    door_h = int(DOOR_ZONE_H * scale)
    center_x = flag_x + flag_w // 2
    start_x = center_x - door_w // 2
    start_y = flag_y + flag_h
    margin_x = int(door_w * margin)
    margin_y = int(door_h * margin)
    return (start_x + margin_x, start_y + margin_y,
            start_x + door_w - margin_x, start_y + door_h - margin_y)


def door_click_point(flag_x, flag_y, flag_w, flag_h, scale, rng=random):
    """Случайная точка нажатия внутри центральной части двери."""
    x1, y1, x2, y2 = door_click_zone(flag_x, flag_y, flag_w, flag_h, scale)
    return rng.randint(x1, x2), rng.randint(y1, y2)


def after_failed_battle_start(team_screen_visible, attempts, limit=START_BATTLE_ATTEMPTS):
    """Бой не начался за отведённое время. Что делать дальше.

    team_screen_visible — на экране всё ещё выбор команды (кнопка «Авто» не сработала).
    attempts — сколько неудачных запусков боя уже было подряд (без текущего).
    Возвращает (состояние бота, сколько неудачных попыток теперь):
      "SET_TEAM" — вернуться к выбору команды и нажать «Авто» снова;
      "STOP"     — попытки кончились, бот останавливается с понятной причиной;
      "HALLWAY"  — на экране не выбор команды (например, загрузка), смотрим коридор, как раньше.
    """
    if not team_screen_visible:
        return "HALLWAY", 0
    attempts += 1
    if attempts >= limit:
        return "STOP", attempts
    return "SET_TEAM", attempts


class TapPacer:
    """Пауза перед нажатием (задача 10, вопрос 13): реакция человека и не больше 2 нажатий в секунду.

    Реакция считается от того, как кнопка появилась на экране (seen_at), а не от решения бота нажать:
    если бот после появления кнопки ещё думал (читал ХП, разбирал двери), время уже прошло и ждать не нужно."""

    def __init__(self, clock=time.monotonic, rng=random, reaction=REACTION_S, min_interval=MIN_TAP_INTERVAL_S):
        self._clock = clock
        self._rng = rng
        self._reaction = reaction
        self._min_interval = min_interval
        self._last_tap = None

    def wait_before(self, seen_at=None):
        """Сколько секунд подождать перед нажатием. seen_at — когда кнопка появилась (None — только что)."""
        now = self._clock()
        seen_at = now if seen_at is None else seen_at
        wait = self._rng.uniform(*self._reaction) - (now - seen_at)
        if self._last_tap is not None:
            wait = max(wait, self._min_interval - (now - self._last_tap))
        return max(0.0, wait)

    def tapped(self):
        """Нажатие сделано: следующее — не раньше чем через min_interval."""
        self._last_tap = self._clock()


def wait_until_still(read, same, first=None, clock=time.monotonic, sleep=time.sleep,
                     interval=STILL_INTERVAL_S, timeout=STILL_TIMEOUT_S, not_before=None):
    """«Экран замер» (задача 10): читает снимки, пока два подряд не покажут одно и то же.

    read() — новый снимок: то, что сравниваем (например, ХП титанов на окне результата);
    same(a, b) — одинаковы ли два снимка;
    first — (когда сделан, снимок), если первый снимок уже есть.
    not_before — снимок, который принимается, должен быть сделан не раньше этого момента (задача 11: окно результата
    первые 1,5 с ещё проявляется). Ожидание до этого момента в timeout не входит.
    Между снимками не меньше interval секунд (если снимок делается дольше, бот не ждёт). Дольше timeout не ждёт.
    Возвращает (последний снимок, замер ли экран, сколько новых снимков сделано)."""
    started = clock() if not_before is None else max(clock(), not_before)
    shots = 0
    if first is None:
        first = (clock(), read())
        shots = 1
    prev_t, prev = first
    while True:
        rest = interval - (clock() - prev_t)
        if rest > 0:
            sleep(rest)
        now_t = clock()
        now = read()
        shots += 1
        ready = not_before is None or now_t >= not_before
        if ready and same(prev, now):
            return now, True, shots
        if ready and clock() - started >= timeout:
            return now, False, shots
        prev_t, prev = now_t, now


def spots_still(before, now, tol):
    """Предметы (например, кнопки «Атаковать») стоят на месте: каждый из before есть в now (±tol пикселей).
    before и now — списки точек (x, y)."""
    return bool(now) and all(
        any(abs(b[0] - n[0]) <= tol and abs(b[1] - n[1]) <= tol for n in now) for b in before)
