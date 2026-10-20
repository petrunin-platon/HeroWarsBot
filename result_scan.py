# result_scan.py
# Надёжное чтение окна результата: пересканировать, если титаны не нашлись, дождаться, пока полоски ХП замрут
# (задача 10), и имя файла для скриншота SOS.
# Без OpenCV и игры, поэтому логику можно проверять тестами (tests/test_result_scan.py, tests/test_waits.py).
import time

import click_logic

# Пак — это те, кого бот сам поставил перед боем (3, 4 или 5 титанов), и все они должны быть на окне результата.
# Поэтому не найденный хотя бы один — это сбой чтения, а не «не дрался». Мёртвого бот находит по иконке и ХП = 0.
MISSING_LIMIT = 1
# Сколько раз пересканировать и сколько ждать между снимками
MAX_RESCANS = 3
RESCAN_PAUSE_S = 0.5
# Окно результата в начале ещё проявляется (маленькая анимация, ваше замечание к сессии 09) — она может сбить ХП
# и энергию. Ваш совет: окно появилось, когда видна «ОК»; через 1,2 с можно читать титанов (задача 11: чтение
# теперь быстрое и иначе успевало бы во время анимации)
RESULT_ANIMATION_S = 1.2


def wait_window_settled(result_seen, clock=time.monotonic, sleep=time.sleep):
    """Ждёт, пока с появления «ОК» (result_seen) пройдёт RESULT_ANIMATION_S. Если бот увидел «ОК» давно, не ждёт.
    Возвращает, сколько секунд ждал."""
    rest = result_seen + RESULT_ANIMATION_S - clock()
    if rest > 0:
        sleep(rest)
    return max(0.0, rest)


def missing_titans(pack, team_status):
    """Титаны пака, которых нет на окне результата: иконка не найдена (или шаблона нет вовсе)."""
    return [t for t in pack if team_status.get(t, {}).get("status", "ОТСУТСТВУЕТ") == "ОТСУТСТВУЕТ"]


def is_unreadable(pack, team_status):
    """True, если не найден хотя бы один титан пака."""
    return len(missing_titans(pack, team_status)) >= MISSING_LIMIT


def scan_with_retries(scan, pack, sleep=time.sleep, log=print):
    """Сканирует окно результата; при нечитаемом окне ждёт RESCAN_PAUSE_S и сканирует снова, до MAX_RESCANS раз.
    scan() возвращает {титан: {"hp", "energy", "status", "score"}}.
    Возвращает (team_status, unreadable): берётся снимок, где найдено больше всего титанов (при равенстве — последний)."""
    best = scan()
    for attempt in range(1, MAX_RESCANS + 1):
        if not is_unreadable(pack, best):
            break
        log(f"[АНАЛИЗАТОР] Не найдены титаны {missing_titans(pack, best)}. "
            f"Пересканирую через {RESCAN_PAUSE_S} с (попытка {attempt} из {MAX_RESCANS})...")
        sleep(RESCAN_PAUSE_S)
        new = scan()
        if len(missing_titans(pack, new)) <= len(missing_titans(pack, best)):
            best = new
    return best, is_unreadable(pack, best)


# Два снимка окна результата «одинаковые», если ХП и энергия отличаются не больше чем на столько процентов
# (видео scrcpy слегка «дрожит», край полоски может сдвинуться на 1–2 пикселя: при полоске ~85 пикселей это до 3%)
SAME_PERCENT = 3


def same_status(a, b, pack):
    """Одинаковы ли два снимка окна результата для титанов пака (±SAME_PERCENT%)."""
    for t in pack:
        x, y = a.get(t, {}), b.get(t, {})
        if x.get("status") != y.get("status"):
            return False
        if any(abs(x.get(k, 0) - y.get(k, 0)) > SAME_PERCENT for k in ("hp", "energy")):
            return False
    return True


# Сколько раз подряд снимок окна результата должен совпасть с предыдущим: 2 — три одинаковых снимка (~0,6 с).
# Задача 11: после «ОК» полоски иногда ещё заполняются дольше 1,2 с (Араджи на первом снимке 8%, потом 100%)
RESULT_STILL_PAIRS = 2


def wait_bars_still(team_status, pack, reread, scanned_at, clock=time.monotonic, sleep=time.sleep, log=print,
                    pairs=1):
    """Окно результата прочитано (team_status, снимок сделан в scanned_at). Вместо паузы 1,5 с перед чтением
    (задача 10) перечитываем полоски, пока снимки подряд не покажут одно и то же (pairs раз подряд).
    reread() — {титан: {...}} для титанов, чьи иконки нашлись снова (быстро: только рядом с прежним местом);
    кого не нашли — остаётся как было. Возвращает итоговый team_status: у кого полоски двигались — с последнего
    снимка, у остальных — как в первом чтении. Цифры в лог не пишет (их печатает main.py по итогу), только кто двигался."""
    def read():
        merged = dict(last["status"])
        merged.update(reread())
        last["status"] = merged
        return merged

    last = {"status": team_status}
    final, still, shots = click_logic.wait_until_still(
        read, lambda a, b: same_status(a, b, pack), first=(scanned_at, team_status), clock=clock, sleep=sleep,
        pairs=pairs)
    changed = [t for t in pack if not same_status(team_status, final, [t])]
    result = dict(team_status)
    result.update({t: final[t] for t in changed})
    if not still:
        log(f"[ЛОГИКА] Полоски ХП не замерли за {click_logic.STILL_TIMEOUT_S:.0f} с — беру последний снимок.")
    elif changed:
        log(f"[ЛОГИКА] Полоски ХП ещё двигались ({', '.join(t.upper() for t in changed)}) — "
            f"замерли после {shots + 1} снимков.")
    elif shots == 1:
        log("[ЛОГИКА] Полоски ХП замерли: второй снимок такой же.")
    else:
        log(f"[ЛОГИКА] Полоски ХП замерли: {shots + 1} снимка подряд одинаковые.")
    return result


def describe_missing(pack, team_status):
    """Текст для лога: кого не нашли и с каким сходством иконки (порог — в analyzer)."""
    parts = []
    for t in missing_titans(pack, team_status):
        score = team_status.get(t, {}).get("score")
        parts.append(f"{t.upper()} (сходство {score:.2f})" if score is not None else f"{t.upper()} (шаблона нет)")
    return ", ".join(parts)


def debug_shot_name(kind, room_no, room_type, when):
    """Имя файла скриншота в bot_data/debug/: sos_комната12_water_2026-10-19_14-03-21.png"""
    return f"{kind}_комната{room_no}_{room_type}_{when.strftime('%Y-%m-%d_%H-%M-%S')}.png"
