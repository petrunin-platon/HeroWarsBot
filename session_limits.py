# session_limits.py
# Задача 14: этажи по точке сохранения и остановка по лимиту.
# Без OpenCV и без игры, проверяется тестами (tests/test_session_limits.py).
#
# Ваш ответ на вопрос 18: по лимиту (время, титанит, комнаты) лучше дойти до точки сохранения, а не бросать этаж посередине.
# Лимит по этажам и так срабатывает сразу после точки сохранения.

# На этаже 5 комнат. Если лимит достигнут, а точка сохранения не нашлась за столько комнат — останавливаемся как есть,
# чтобы бот не играл бесконечно (например, если «Активировать» не распознаётся).
OVERRUN_ROOMS = 6


class FloorCounter:
    """Сколько точек сохранения бот прошёл («Активировать» → окно награды). Этаж считается здесь, а не как «комнаты ÷ 5»."""

    def __init__(self):
        self._pending = 0

    def claimed(self):
        """Навигация: окно награды за этаж появилось."""
        self._pending += 1

    def take(self):
        """Сколько этажей прошло с прошлого вызова (и обнуляет счётчик)."""
        n, self._pending = self._pending, 0
        return n


FLOORS = FloorCounter()


def limit_reason(max_time, max_rooms, max_floors, target_titanite, elapsed_minutes, rooms, floors, titanite):
    """Какой лимит достигнут: (текст, нужно_дойти_до_точки_сохранения) или None. 0 в лимите — не ограничивать."""
    if max_floors > 0 and floors >= max_floors:
        return f"Пройдено {max_floors} этажей.", False  # точка сохранения только что пройдена
    if max_time > 0 and elapsed_minutes >= max_time:
        return f"Превышен лимит времени ({max_time} мин)", True
    if target_titanite > 0 and titanite >= target_titanite:
        return f"Цель по титаниту достигнута ({titanite}/{target_titanite})", True
    if max_rooms > 0 and rooms >= max_rooms:
        return f"Пройдено {max_rooms} комнат.", True
    return None


class FloorFinish:
    """Лимит достигнут → играем дальше до точки сохранения, потом останавливаемся."""

    def __init__(self):
        self.reason = None
        self._rooms0 = 0
        self._floors0 = 0

    @property
    def active(self):
        return self.reason is not None

    def check(self, found, rooms, floors):
        """found — результат limit_reason(). Возвращает (причина остановки или None, первый ли раз достигнут лимит)."""
        if found is None and not self.active:
            return None, False
        first = False
        if found is not None:
            reason, finish_floor = found
            if not finish_floor:
                return reason, False
            if not self.active:
                self.reason, self._rooms0, self._floors0 = reason, rooms, floors
                first = True
        if floors > self._floors0:
            return f"{self.reason.rstrip('.')}. Дошёл до точки сохранения.", first
        if rooms - self._rooms0 >= OVERRUN_ROOMS:
            return f"{self.reason.rstrip('.')}. Точка сохранения не найдена за {OVERRUN_ROOMS} комнат, остановился как есть.", first
        return None, first
