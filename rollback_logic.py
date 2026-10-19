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
import time

# Сколько секунд после «Ещё раз» ждём, пока бот доберётся до «Отступить». Дольше ждать нельзя: игра может перезагрузиться
PAUSE_WAIT_S = 60.0
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
    """Итог отката: code — одно из значений выше, text — объяснение для лога и Telegram."""

    def __init__(self, code, text=""):
        self.code = code
        self.text = text

    @property
    def ok(self):
        return self.code == DONE

    def __bool__(self):
        return self.ok

    def __repr__(self):
        return f"RollbackResult({self.code!r}, {self.text!r})"


def retreat_from_battle(look, tap_pause, press_retreat, press_retry, pause_flag_set, log,
                        clock=time.monotonic, sleep=time.sleep, wait_s=PAUSE_WAIT_S):
    """Выходит из боя в коридор: пауза → «Отступить». Вызывается сразу после нажатия «Ещё раз» (или посреди боя).

    look()          — что на экране: RETREAT, PAUSE, RETRY, OK, HALLWAY или None. «Отступить» важнее паузы:
                      пока меню паузы открыто, кнопка паузы тоже видна, и по ней жать не надо;
    tap_pause()     — нажать паузу один раз;
    press_retreat() — нажать «Отступить» с проверкой, True — кнопка пропала;
    press_retry()   — нажать «Ещё раз» с проверкой (если старое окно результата вдруг осталось);
    pause_flag_set()— включил ли кто-то мягкую паузу;
    log(текст)      — запись в лог (время добавляется само).
    Возвращает RollbackResult.
    """
    started = clock()
    pause_tapped_at = None
    pause_taps = 0
    retreat_done_at = None
    retreat_presses = 0
    retry_extra = 0
    ok_since = None
    ok_shots = 0

    def since():
        return clock() - started

    while True:
        if pause_flag_set():
            return RollbackResult(SOFT_PAUSE, "Во время отката включили мягкую паузу.")

        now = clock()
        screen = look()
        if screen != OK:
            ok_since, ok_shots = None, 0

        if screen == HALLWAY:
            log(f"Возврат в коридор подтверждён, прошло {since():.1f} с.")
            return RollbackResult(DONE)

        if screen == RETREAT:
            retreat_presses += 1
            if retreat_presses > RETREAT_MAX_PRESSES:
                return RollbackResult(RETREAT_FAILED, f"«Отступить» нажата {RETREAT_MAX_PRESSES} раз, а коридор не появился.")
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
            # Окно результата с «Ещё раз» снова на экране: нажатие потерялось
            if retreat_done_at is None:
                if retry_extra >= RETRY_MAX_EXTRA:
                    return RollbackResult(RETRY_LOST, "«Ещё раз» нажимается, но бой не начинается.")
                retry_extra += 1
                log(f"Окно результата с «Ещё раз» на месте, нажимаю «Ещё раз» снова (повтор {retry_extra}).")
                press_retry()

        elif screen == OK:
            # Окно результата без «Ещё раз»: ручной бой закончился, пока мы не успели выйти
            if retreat_done_at is None:
                if ok_since is None:
                    ok_since = now
                ok_shots += 1
                if ok_shots >= RESULT_CONFIRM_SHOTS and now - ok_since >= RESULT_CONFIRM_SPAN_S:
                    return RollbackResult(
                        BATTLE_ENDED,
                        "Ручной бой успел закончиться: на окне результата нет кнопки «Ещё раз», переиграть комнату нельзя.")

        # Сколько ещё можно ждать
        if retreat_done_at is None:
            if now - started >= wait_s:
                if pause_taps == 0:
                    text = f"Кнопка паузы не появилась за {wait_s:.0f} с."
                else:
                    text = f"Пауза нажата {pause_taps} раз, но «Отступить» не появилась за {wait_s:.0f} с."
                return RollbackResult(PAUSE_TIMEOUT, text)
        elif now - retreat_done_at >= HALLWAY_WAIT_S:
            return RollbackResult(NO_HALLWAY, f"«Отступить» нажата, но коридор не появился за {HALLWAY_WAIT_S:.0f} с.")

        sleep(POLL_S)
