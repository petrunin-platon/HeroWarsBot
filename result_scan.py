# result_scan.py
# Надёжное чтение окна результата: пересканировать, если титаны не нашлись, и имя файла для скриншота SOS.
# Без OpenCV и игры, поэтому логику можно проверять тестами (tests/test_result_scan.py).
import time

# Пак — это те, кого бот сам поставил перед боем (3, 4 или 5 титанов), и все они должны быть на окне результата.
# Поэтому не найденный хотя бы один — это сбой чтения, а не «не дрался». Мёртвого бот находит по иконке и ХП = 0.
MISSING_LIMIT = 1
# Сколько раз пересканировать и сколько ждать между снимками
MAX_RESCANS = 3
RESCAN_PAUSE_S = 0.5


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
