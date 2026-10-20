# Задача 14: этажи по точке сохранения и остановка по лимиту (вопрос 18: дойти до точки сохранения).
import session_limits as sl


def reason(finish, **kw):
    args = dict(max_time=0, max_rooms=0, max_floors=0, target_titanite=0, elapsed_minutes=0, rooms=0, floors=0, titanite=0)
    args.update(kw)
    found = sl.limit_reason(args["max_time"], args["max_rooms"], args["max_floors"], args["target_titanite"],
                            args["elapsed_minutes"], args["rooms"], args["floors"], args["titanite"])
    return finish.check(found, args["rooms"], args["floors"])


def test_floor_counter_counts_checkpoints_and_resets():
    counter = sl.FloorCounter()
    assert counter.take() == 0
    counter.claimed()
    counter.claimed()
    assert counter.take() == 2
    assert counter.take() == 0


def test_no_limits_never_stops():
    assert reason(sl.FloorFinish(), rooms=500, floors=100, titanite=9999, elapsed_minutes=999) == (None, False)


def test_floor_limit_stops_right_after_checkpoint():
    assert reason(sl.FloorFinish(), max_floors=3, floors=2) == (None, False)
    stop, first = reason(sl.FloorFinish(), max_floors=3, floors=3, rooms=15)
    assert stop == "Пройдено 3 этажей." and first is False


def test_floors_are_not_rooms_divided_by_five():
    # Бот начал с середины этажа: 3 комнаты пройдено, этаж один раз закончен
    assert reason(sl.FloorFinish(), max_floors=1, rooms=3, floors=0) == (None, False)
    assert reason(sl.FloorFinish(), max_floors=1, rooms=7, floors=1)[0] == "Пройдено 1 этажей."


def test_room_limit_plays_on_until_checkpoint():
    finish = sl.FloorFinish()
    stop, first = reason(finish, max_rooms=12, rooms=12, floors=2)
    assert stop is None and first is True            # лимит достигнут, играем дальше
    assert finish.active
    assert reason(finish, max_rooms=12, rooms=13, floors=2) == (None, False)
    stop, first = reason(finish, max_rooms=12, rooms=14, floors=3)
    assert stop == "Пройдено 12 комнат. Дошёл до точки сохранения." and first is False


def test_time_and_titanite_limits_also_finish_the_floor():
    stop, first = reason(sl.FloorFinish(), max_time=90, elapsed_minutes=91, rooms=4, floors=0)
    assert stop is None and first is True
    finish = sl.FloorFinish()
    reason(finish, target_titanite=120, titanite=120, floors=1)
    stop, _ = reason(finish, target_titanite=120, titanite=132, floors=2)
    assert stop == "Цель по титаниту достигнута (120/120). Дошёл до точки сохранения."


def test_limit_message_printed_once():
    finish = sl.FloorFinish()
    assert reason(finish, max_rooms=5, rooms=5)[1] is True
    assert reason(finish, max_rooms=5, rooms=6)[1] is False


def test_checkpoint_not_found_stops_after_overrun():
    finish = sl.FloorFinish()
    reason(finish, max_rooms=10, rooms=10, floors=1)
    for extra in range(1, sl.OVERRUN_ROOMS):
        assert reason(finish, max_rooms=10, rooms=10 + extra, floors=1)[0] is None
    stop, _ = reason(finish, max_rooms=10, rooms=10 + sl.OVERRUN_ROOMS, floors=1)
    assert "Точка сохранения не найдена" in stop
