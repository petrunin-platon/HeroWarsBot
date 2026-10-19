# stuck_guard.py
# Защита от зависаний: «сторож» (давно не пройдено ни одной комнаты), ограничения времени по состояниям
# и ожидание, пока пользователь проходит комнату руками. Без OpenCV и игры, поэтому проверяется тестами
# (tests/test_stuck_guard.py).
import time

# --- Сторож ---
# Если за столько секунд не пройдено ни одной комнаты — тревога: скриншот, сообщение, умный старт
NO_ROOM_ALARM_S = 300.0
# После стольких тревог подряд (без пройденной комнаты) бот встаёт на мягкую паузу и ждёт вас
ALARMS_BEFORE_PAUSE = 3

# --- Сколько можно ждать в одном состоянии ---
# SET_TEAM — экран выбора команды после «Атаковать»; WAIT_FOR_OK — окно результата после начала боя
STATE_LIMITS_S = {
    "SET_TEAM": 30.0,
    "WAIT_FOR_OK": 180.0,
}

# --- Пройти руками ---
# Коридор должен быть виден столько секунд подряд, чтобы бот продолжил сам
MANUAL_HALLWAY_CONFIRM_S = 2.0

# Что видно на экране (ключи для ManualPlay.observe)
HALLWAY, RESULT, BATTLE, TEAM = "hallway", "result", "battle", "team"


class Watchdog:
    """Сторож: сколько времени не было успехов (пройденной комнаты).

    progress() — комната пройдена или бот долго ждал вас (окно SOS, пауза, ручной бой): отсчёт заново.
    due() — True, если пора поднимать тревогу. После тревоги отсчёт тоже идёт заново,
    поэтому следующая тревога — ещё через limit секунд.
    """

    def __init__(self, clock=time.monotonic, limit=NO_ROOM_ALARM_S, alarms_before_pause=ALARMS_BEFORE_PAUSE):
        self._clock = clock
        self.limit = limit
        self.alarms_before_pause = alarms_before_pause
        self.alarms = 0  # тревог подряд без пройденной комнаты
        self._last = clock()

    def progress(self):
        """Комната пройдена: тревоги сбрасываются."""
        self._last = self._clock()
        self.alarms = 0

    def waited_for_user(self):
        """Бот ждал вас (окно SOS, мягкая пауза, ручной бой): это время не считается."""
        self._last = self._clock()

    def idle_for(self):
        return self._clock() - self._last

    def due(self):
        if self.idle_for() < self.limit:
            return False
        self.alarms += 1
        self._last = self._clock()
        return True

    def should_pause(self):
        """Тревог подряд набралось столько, что дальше пробовать бесполезно: пора на мягкую паузу."""
        return self.alarms >= self.alarms_before_pause


class StateClock:
    """Сколько бот находится в одном состоянии машины. Отсчёт заново при смене состояния и после ожидания вас."""

    def __init__(self, clock=time.monotonic, limits=None):
        self._clock = clock
        self._limits = STATE_LIMITS_S if limits is None else limits
        self._state = None
        self._since = clock()

    def observe(self, state):
        if state != self._state:
            self._state = state
            self._since = self._clock()

    def reset(self):
        self._since = self._clock()

    def elapsed(self):
        return self._clock() - self._since

    def expired(self, state):
        """Предел (секунды), если бот в этом состоянии дольше положенного, иначе None."""
        self.observe(state)
        limit = self._limits.get(state)
        if limit is None:
            return None
        return limit if self.elapsed() >= limit else None


class ManualPlay:
    """После «Пройти руками» в окне SOS бот ничего не нажимает, только смотрит экран.

    Вызывайте observe(что видно) после каждого снимка: HALLWAY, RESULT, BATTLE, TEAM или None (не понял).
    True — вы вернулись в коридор (он виден confirm_s секунд подряд), бот продолжает сам.

    room_cleared — засчитывать ли комнату. Смотрим, какой экран (кроме коридора) был последним:
    - окно результата («ОК» закрыли) — комната пройдена (приняли бой или сыграли заново);
    - бой или выбор команды — вы отступили, комната не пройдена, дверь та же.
    В начале на экране окно результата, из-за которого было окно SOS (или выбор команды, если пака не нашлось).

    replayed — вы переигрывали бой (видели бой или выбор команды). Если нет, а окно результата просто закрыли,
    ХП с этого окна верные и бот их запоминает.
    """

    def __init__(self, clock=time.monotonic, confirm_s=MANUAL_HALLWAY_CONFIRM_S, first_screen=RESULT):
        self._clock = clock
        self._confirm_s = confirm_s
        self.last_screen = first_screen
        self.replayed = first_screen in (BATTLE, TEAM)
        self._hallway_since = None

    @property
    def room_cleared(self):
        return self.last_screen == RESULT

    def observe(self, screen):
        now = self._clock()
        if screen == HALLWAY:
            if self._hallway_since is None:
                self._hallway_since = now
            return now - self._hallway_since >= self._confirm_s
        self._hallway_since = None
        if screen is not None:
            self.last_screen = screen
            if screen in (BATTLE, TEAM):
                self.replayed = True
        return False


# --- Снимок экрана не получается (ПК заблокирован, Win+L) ---
# При блокировке Windows не даёт делать снимки: mss падает с ScreenShotError «BitBlt» (сессия 19.10.2026, 19:50).
# Бот не падает, а ждёт и пробует снова через столько секунд
SCREEN_RETRY_S = 2.0
# Если экран недоступен дольше этого, бот один раз сообщает в Telegram
SCREEN_LONG_WAIT_S = 60.0


def grab_or_wait(grab, errors, sleep=time.sleep, clock=time.monotonic, log=print,
                 on_blocked=None, on_long_wait=None, on_resumed=None,
                 retry_s=SCREEN_RETRY_S, long_wait_s=SCREEN_LONG_WAIT_S):
    """Делает снимок grab(). Если снимок падает с ошибкой из errors — ждёт и пробует снова, пока не получится.

    on_blocked() — снимок впервые не получился; on_long_wait(секунды) — один раз, когда ждём дольше long_wait_s;
    on_resumed(секунды) — снимок снова получился. Возвращает снимок.
    """
    started = None
    warned = False
    while True:
        try:
            shot = grab()
        except errors as e:
            now = clock()
            if started is None:
                started = now
                log(f"[ЭКРАН] Не удаётся сделать снимок экрана ({e}). Похоже, ПК заблокирован (Win+L). "
                    f"Бот ничего не нажимает и пробует снова каждые {retry_s:.0f} с...")
                if on_blocked:
                    on_blocked()
            if not warned and now - started >= long_wait_s:
                warned = True
                if on_long_wait:
                    on_long_wait(now - started)
            sleep(retry_s)
            continue
        if started is not None:
            waited = clock() - started
            log(f"[ЭКРАН] Снимок экрана снова работает (ждали {waited:.0f} с). Продолжаю.")
            if on_resumed:
                on_resumed(waited)
        return shot
