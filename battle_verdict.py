# battle_verdict.py
# Решение «бой хороший или плохой» после окна результата.
# Без OpenCV и игры, поэтому логику можно проверять тестами (tests/test_battle_verdict.py).


def evaluate_battle(pack, team_status, before_state, critical_hp, allowed_delta,
                    engine=None, room=None, enemies=None):
    """
    Оценивает бой по ХП титанов пака. Возвращает словарь:
      bad          — True, если бой плохой (нужно окно SOS);
      reason       — причина плохого боя (пустая строка, если бой хороший);
      after_state  — {титан: {"hp": ..., "energy": ...}} для титанов, которые дрались;
      max_loss     — наибольшая потеря ХП за бой среди живых титанов, в процентах.

    Плохой бой — это:
      1) кто-то мёртв или иконка титана не найдена (ХП = 0);
      2) у кого-то ХП ниже порога паники critical_hp;
      3) кто-то потерял больше допуска allowed_delta;
      4) сработало правило отхила (titan_hp_below), которое до боя не срабатывало,
         а после боя сработало у титана, который только что дрался.

    Правила по энергии (titan_energy_below) и правила skip на итог боя НЕ влияют:
    они срабатывают перед следующим боем (выбор пака и двери).
    Если передан engine, пункт 4 проверяется, иначе пропускается.
    """
    after_state = {}
    max_loss = 0
    reason = ""

    for titan in pack:
        stats = team_status.get(titan)

        # Титана не было в бою — пропускаем
        if stats and stats.get("status") == "ОТСУТСТВУЕТ":
            print(f"[ЛОГИКА] {titan.upper()} отсутствовал на арене. Пропускаю.")
            continue

        if not stats:
            current_hp = 0
            energy = 0
        else:
            current_hp = stats.get("hp", 100)
            energy = stats.get("energy", 100)

        before_hp = before_state.get(titan, {}).get("hp", 100)
        hp_lost = max(0, before_hp - current_hp)
        max_loss = max(max_loss, hp_lost)

        after_state[titan] = {"hp": current_hp, "energy": energy}

        if reason:
            continue  # причина уже найдена, остальных только записываем в after_state

        if current_hp == 0:
            reason = f"ФАТАЛЬНО! {titan.upper()} мертв (иконка не найдена или ХП=0)!"
        elif current_hp < critical_hp:
            reason = f"Критический порог! {titan.upper()} имеет {current_hp}% ХП (порог: {critical_hp}%)"
        elif hp_lost > allowed_delta:
            reason = f"Превышена Дельта потерь! {titan.upper()} потерял {hp_lost}% ХП (допуск: {allowed_delta}%)"

    if not reason and engine is not None:
        after_full = dict(before_state)
        after_full.update(after_state)
        fired = engine.rescue_rules_fired_by_battle(room, enemies or [], before_state, after_full, set(after_state))
        if fired:
            reason = f"Просадка до порога отхила: {fired}"

    return {"bad": bool(reason), "reason": reason, "after_state": after_state, "max_loss": max_loss}
