# rollback_logic.py
# Логика отката боя: после «Ещё раз» ждём кнопку паузы, жмём её, жмём «Отступить», ждём коридор.
# Без OpenCV и игры, поэтому проверяется тестами (tests/test_rollback.py).
#
# Как устроена игра (ответ на вопрос 6 в docs/questions.md):
# - «Ещё раз» есть только на окне результата АВТОБОЯ. После неё стартует РУЧНОЙ бой, и его надо сразу прервать.
# - Загрузка боя бывает долгой: обычно 7–20 с, раньше было и больше 30 с.
# - Когда пауза нажата, кнопка паузы всё ещё видна (экран лишь темнеет), а посередине появляется узкое окно с «Отступить».
#   Пока окно открыто, по экрану можно жать сколько угодно — оно не закроется.
# - После ручного боя на окне результата «Ещё раз» уже нет, откатить его нельзя.
# - При обрыве связи игра затемняет экран, по нему бежит «гриб», пока связь не вернётся (или игра перезагружается).
import time

# Сколько секунд после «Ещё раз» ждём, пока бот доберётся до «Отступить», если на экране что-то знакомое
# (например, пауза видна, а меню не открывается)
PAUSE_WAIT_S = 60.0
# Если же экран всё это время не узнаётся (загрузка с «грибом», нет связи с сервером), бот не сдаётся через PAUSE_WAIT_S,
# а ждёт игру до стольких секунд от начала отката (сессия 10: связь пропала, бой не загрузился за 60 с, бот встал на паузу,
# а Telegram без интернета тоже не ушёл — бот простоял 2,5 часа). Загрузится бой — пауза и «Отступить», как обычно.
# Дольше не ждём: игра могла перезагрузиться, тогда без вас не обойтись
GAME_WAIT_S = 15 * 60.0
# Пока ждём игру: строка в лог раз в столько секунд, снимок экрана реже (бой, если загрузится, всё равно ставим на паузу сразу)
GAME_WAIT_LOG_S = 60.0
POLL_GAME_WAIT_S = 0.25
# После нажатия паузы ждём «Отступить» столько секунд. Не появилась, а пауза видна — жмём паузу снова
PAUSE_MENU_WAIT_S = 3.0
# После нажатия «Отступить» экран ещё пару секунд может показывать кнопку паузы — по ней не жмём
RETREAT_SETTLE_S = 2.0
# После «Отступить» ждём коридор столько секунд
HALLWAY_WAIT_S = 15.0
# Окно результата без «Ещё раз» считается настоящим, если оно видно на стольких снимках подряд и не меньше стольких секунд
# (в первые мгновения после «Ещё раз» старое окно ещё может мелькать)
RESULT_CONFIRM_SHOTS = 3
RESULT_CONFIRM_SPAN_S = 0.5
# Сколько раз можно нажимать «Отступить» за один откат, и сколько раз — ещё раз «Ещё раз», если нажатие потерялось
RETREAT_MAX_PRESSES = 5
RETRY_MAX_EXTRA = 2
# «Ещё раз» снова на экране, хотя нажатие сработало (бой начал грузиться и сорвался — нет связи): после RETRY_MAX_EXTRA
# повторов жмём не чаще, чем раз в столько секунд, пока ждём игру (GAME_WAIT_S)
RETRY_GAP_S = 30.0
POLL_S = 0.05

# Что сейчас на экране (функция look() возвращает одно из значений)
RETREAT, PAUSE, RETRY, OK, HALLWAY = "retreat", "pause", "retry", "ok", "hallway"

# Итог отката
DONE = "DONE"
NO_RETRY = "NO_RETRY"            # не нашли «Ещё раз»
BATTLE_ENDED = "BATTLE_ENDED"    # ручной бой успел закончиться: откат невозможен
PAUSE_TIMEOUT = "PAUSE_TIMEOUT"  # не добрались до «Отступить» за PAUSE_WAIT_S
RETREAT_FAILED = "RETREAT_FAILED"
NO_HALLWAY = "NO_HALLWAY"        # «Отступить» нажата, а коридор не появился
SOFT_PAUSE = "SOFT_PAUSE"        # во время отката включили мягкую паузу
RETRY_LOST = "RETRY_LOST"        # «Ещё раз» не срабатывает


class RollbackResult:
    """Итог отката: code — одно из значений выше, text — объяснение для лога и Telegram.
    game_wait_s — сколько секунд откат шёл, если бот ждал игру (экран не узнавался дольше обычного), иначе 0."""

    def __init__(self, code, text="", game_wait_s=0.0):
        self.code = code
        self.text = text
        self.game_wait_s = game_wait_s

    @property
    def ok(self):
        return self.code == DONE

    def __bool__(self):
        return self.ok

    def __repr__(self):
        return f"RollbackResult({self.code!r}, {self.text!r})"


def _minutes(seconds):
    """90 → «1 мин 30 с», 45 → «45 с»."""
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds} с"
    return f"{seconds // 60} мин {seconds % 60} с" if seconds % 60 else f"{seconds // 60} мин"


def retreat_from_battle(look, tap_pause, press_retreat, press_retry, pause_flag_set, log,
                        clock=time.monotonic, sleep=time.sleep, wait_s=PAUSE_WAIT_S, game_wait_s=GAME_WAIT_S,
                        on_game_wait=None):
    """Выходит из боя в коридор: пауза → «Отступить». Вызывается сразу после нажатия «Ещё раз» (или посреди боя).

    look()          — что на экране: RETREAT, PAUSE, RETRY, OK, HALLWAY или None. «Отступить» важнее паузы:
                      пока меню паузы открыто, кнопка паузы тоже видна, и по ней жать не надо;
    tap_pause()     — нажать паузу один раз;
    press_retreat() — нажать «Отступить» с проверкой, True — кнопка пропала;
    press_retry()   — нажать «Ещё раз» с проверкой (если окно результата снова на экране), True — кнопка пропала;
    pause_flag_set()— включил ли кто-то мягкую паузу;
    log(текст)      — запись в лог (время добавляется само);
    on_game_wait()  — один раз, когда бот начал ждать игру (например, скриншот для разбора).

    Ждать игру: бой не загрузился за wait_s (или коридор за HALLWAY_WAIT_S после «Отступить»), а экран не узнаётся
    (загрузка, нет связи с сервером) или снова окно с «Ещё раз» — бот не сдаётся, а смотрит экран дальше,
    до game_wait_s от начала отката (сессия 10). Узнаваемый экран, который не меняется (пауза не открывает меню),
    по-прежнему заканчивает откат через wait_s.
    Возвращает RollbackResult.
    """
    started = clock()
    loading_from = started  # с какого момента ждём загрузку боя: с «Ещё раз» и с каждого её повторного нажатия
    pause_tapped_at = None
    pause_taps = 0
    retreat_done_at = None
    retreat_presses = 0
    retry_extra = 0
    retry_lost = 0  # нажатия «Ещё раз», после которых кнопка так и не пропала
    retry_at = None
    ok_since = None
    ok_shots = 0
    game_wait_from = None  # с какого момента ждём игру (None — не ждём)
    game_wait_log_at = None
    game_waited = False

    def since():
        return clock() - started

    def result(code, text=""):
        return RollbackResult(code, text, since() if game_waited else 0.0)

    while True:
        if pause_flag_set():
            return result(SOFT_PAUSE, "Во время отката включили мягкую паузу.")

        now = clock()
        screen = look()
        if screen != OK:
            ok_since, ok_shots = None, 0

        if game_wait_from is not None:
            if screen not in (None, RETRY):
                # Игра вернулась: дальше обычные шаги и обычные сроки — с этого момента
                log(f"Игра снова откликается (ждал {_minutes(now - game_wait_from)}).")
                game_wait_from = None
                if retreat_done_at is None:
                    loading_from = now
                else:
                    retreat_done_at = now
            elif now >= game_wait_log_at:
                log(f"Всё ещё жду игру: прошло {_minutes(now - started)} от начала отката (жду до {_minutes(game_wait_s)}).")
                game_wait_log_at = now + GAME_WAIT_LOG_S

        if screen == HALLWAY:
            log(f"Возврат в коридор подтверждён, прошло {since():.1f} с.")
            return result(DONE)

        if screen == RETREAT:
            retreat_presses += 1
            if retreat_presses > RETREAT_MAX_PRESSES:
                return result(RETREAT_FAILED, f"«Отступить» нажата {RETREAT_MAX_PRESSES} раз, а коридор не появился.")
            log(f"Вижу меню паузы, нажимаю «Отступить» (попытка {retreat_presses}), прошло {since():.1f} с.")
            if press_retreat():
                retreat_done_at = clock()
                log("«Отступить» нажата. Жду коридор...")
            else:
                retreat_done_at = None
                log("«Отступить» не сработала.")
            continue

        if screen == PAUSE:
            settling = retreat_done_at is not None and now - retreat_done_at < RETREAT_SETTLE_S
            if not settling and (pause_tapped_at is None or now - pause_tapped_at >= PAUSE_MENU_WAIT_S):
                pause_taps += 1
                if pause_taps == 1:
                    log(f"Вижу кнопку паузы, жму один раз. Прошло {since():.1f} с после «Ещё раз».")
                else:
                    log(f"Меню паузы не появилось (или его закрыли), жму паузу снова (нажатие {pause_taps}). Прошло {since():.1f} с.")
                tap_pause()
                pause_tapped_at = clock()
                retreat_done_at = None

        elif screen == RETRY:
            # Окно результата с «Ещё раз» снова на экране: нажатие потерялось или бой начал грузиться и сорвался
            # (нет связи). Первые RETRY_MAX_EXTRA раз жмём сразу, потом — не чаще раза в RETRY_GAP_S, пока ждём игру
            if retreat_done_at is None and now - started < game_wait_s and \
                    (retry_extra < RETRY_MAX_EXTRA or now - retry_at >= RETRY_GAP_S):
                retry_extra += 1
                if retry_extra == RETRY_MAX_EXTRA + 1:
                    log(f"Окно с «Ещё раз» возвращается снова и снова: похоже, бой не может загрузиться (нет связи "
                        f"с сервером). Жму «Ещё раз» не чаще раза в {RETRY_GAP_S:.0f} с и жду игру до {_minutes(game_wait_s)} "
                        "от начала отката. Мягкая пауза в окне программы прекращает ожидание.")
                    if not game_waited:
                        game_waited = True
                        if on_game_wait:
                            on_game_wait()
                log(f"Окно результата с «Ещё раз» на месте, нажимаю «Ещё раз» снова (повтор {retry_extra}, "
                    f"прошло {since():.0f} с).")
                if press_retry():
                    loading_from = clock()  # бой грузится заново: кнопку паузы снова ждём wait_s
                else:
                    retry_lost += 1
                    if retry_lost >= RETRY_MAX_EXTRA:
                        return result(RETRY_LOST, "«Ещё раз» нажимается, но бой не начинается.")
                retry_at = clock()

        elif screen == OK:
            # Окно результата без «Ещё раз»: ручной бой закончился, пока мы не успели выйти
            if retreat_done_at is None:
                if ok_since is None:
                    ok_since = now
                ok_shots += 1
                if ok_shots >= RESULT_CONFIRM_SHOTS and now - ok_since >= RESULT_CONFIRM_SPAN_S:
                    return result(
                        BATTLE_ENDED,
                        "Ручной бой успел закончиться: на окне результата нет кнопки «Ещё раз», переиграть комнату нельзя.")

        # Сколько ещё можно ждать
        if retreat_done_at is None:
            phase_s, phase_limit = now - loading_from, wait_s
        else:
            phase_s, phase_limit = now - retreat_done_at, HALLWAY_WAIT_S
        if phase_s >= phase_limit:
            if screen in (None, RETRY) and now - started < game_wait_s:
                # Экран не узнаётся (загрузка, «гриб», нет связи с сервером) или снова «Ещё раз»: не сдаёмся, ждём игру
                if game_wait_from is None:
                    game_wait_from = now
                    game_wait_log_at = now + GAME_WAIT_LOG_S
                    what = "экран не узнаю" if screen is None else "на экране снова окно с «Ещё раз»"
                    step = (f"Бой не загрузился за {_minutes(phase_s)}" if retreat_done_at is None
                            else f"После «Отступить» коридор не появился за {_minutes(phase_s)}")
                    log(f"{step}, {what}: похоже, нет связи с сервером или игра долго грузится. Не сдаюсь: жду игру "
                        f"до {_minutes(game_wait_s)} от начала отката. Загрузится бой — поставлю паузу и отступлю, "
                        "вернётся окно с «Ещё раз» — нажму снова. Мягкая пауза в окне программы прекращает ожидание.")
                    if not game_waited:
                        game_waited = True
                        if on_game_wait:
                            on_game_wait()
            elif retreat_done_at is not None:
                if screen is None:
                    return result(NO_HALLWAY, f"«Отступить» нажата, но коридор не появился: экран не узнаю "
                                              f"{_minutes(phase_s)} (нет связи с сервером или игра перезагрузилась).")
                return result(NO_HALLWAY, f"«Отступить» нажата, но коридор не появился за {HALLWAY_WAIT_S:.0f} с.")
            elif screen == RETRY:
                return result(RETRY_LOST, f"Бой не загружается {_minutes(since())}: на экране снова окно с «Ещё раз» "
                                          f"(нажимал её повторно {retry_extra} раз). Похоже, нет связи с сервером.")
            elif screen is None:
                return result(PAUSE_TIMEOUT, f"Экран не узнаю {_minutes(since())} после «Ещё раз»: бой так и не "
                                             "загрузился (нет связи с сервером или игра перезагрузилась).")
            elif pause_taps == 0:
                return result(PAUSE_TIMEOUT, f"Кнопка паузы не появилась за {wait_s:.0f} с.")
            else:
                return result(PAUSE_TIMEOUT,
                              f"Пауза нажата {pause_taps} раз, но «Отступить» не появилась за {wait_s:.0f} с.")

        sleep(POLL_GAME_WAIT_S if game_wait_from is not None else POLL_S)
