# click_logic.py
# Логика надёжных нажатий: когда повторять нажатие, когда дверь «стоит на месте», когда картинка замерла.
# Без OpenCV и игры, поэтому проверяется тестами (tests/test_click_logic.py).
import random
import time

import numpy as np

# --- Повторное нажатие кнопки ---
# Жмём снова, только если через столько секунд ПОСЛЕ того, как команда нажатия дошла до телефона, кнопка всё ещё на экране
RETRY_AFTER_S = 1.5
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
# Коридор «замер»: средняя разница между кадрами (шкала 0–255) меньше этого значения в стольких сравнениях подряд
STILL_MAX_DIFF = 2.0
STILL_SHOTS = 3
# Дольше этого не ждём (раньше была фиксированная пауза 4 с)
STILL_MAX_WAIT_S = 4.0

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


class StillnessWatcher:
    """Определяет, что картинка перестала двигаться: несколько кадров подряд почти не отличаются."""

    def __init__(self, shots=STILL_SHOTS, max_diff=STILL_MAX_DIFF):
        self._shots = shots
        self._max_diff = max_diff
        self._prev = None
        self._calm = 0

    def update(self, frame):
        """frame — уменьшенный серый кадр (numpy). True — картинка замерла."""
        if self._prev is not None:
            diff = float(np.mean(np.abs(frame.astype(np.int16) - self._prev.astype(np.int16))))
            self._calm = self._calm + 1 if diff < self._max_diff else 0
        self._prev = frame
        return self._calm >= self._shots


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
