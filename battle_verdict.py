# battle_verdict.py
# Решение «бой хороший или плохой» после окна результата.
# Без OpenCV и игры, поэтому логику можно проверять тестами (tests/test_battle_verdict.py).


def evaluate_battle(pack, team_status, before_state, critical_hp, allowed_delta,
                    engine=None, room=None, enemies=None, group_loss=None, titan_critical_hp=None):
    """
    Оценивает бой по ХП титанов пака. Возвращает словарь:
      bad          — True, если бой плохой (нужно окно SOS или откат);
      reason       — причина плохого боя (пустая строка, если бой хороший);
      after_state  — {титан: {"hp": ..., "energy": ...}} для титанов, которые дрались;
      max_loss     — наибольшая потеря ХП за бой среди живых титанов, в процентах.

    Плохой бой — это:
      1) кто-то мёртв или иконка титана не найдена (ХП = 0);
      2) у кого-то ХП ниже порога паники: личного (titan_critical_hp, {титан: %}) или общего critical_hp;
      3) кто-то потерял больше допуска allowed_delta;
      4) общие потери пака: group_loss = (N, X) — N титанов и больше потеряли по X% ХП и больше.
         None или N = 0 — проверка выключена;
      5) сработало правило отхила (titan_hp_below), которое до боя не срабатывало,
         а после боя сработало у титана, который только что дрался.

    Правила по энергии (titan_energy_below) и правила skip на итог боя НЕ влияют:
    они срабатывают перед следующим боем (выбор пака и двери).
    Если передан engine, пункт 5 проверяется, иначе пропускается.
    """
    titan_critical_hp = titan_critical_hp or {}
    after_state = {}
    losses = {}
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
        losses[titan] = hp_lost

        after_state[titan] = {"hp": current_hp, "energy": energy}

        if reason:
            continue  # причина уже найдена, остальных только записываем в after_state

        panic = titan_critical_hp.get(titan, critical_hp)
        if current_hp == 0:
            reason = f"ФАТАЛЬНО! {titan.upper()} мертв (иконка не найдена или ХП=0)!"
        elif current_hp < panic:
            kind = "личный порог" if titan in titan_critical_hp else "порог"
            reason = f"Критический порог! {titan.upper()} имеет {current_hp}% ХП ({kind}: {panic}%)"
        elif hp_lost > allowed_delta:
            reason = f"Превышена Дельта потерь! {titan.upper()} потерял {hp_lost}% ХП (допуск: {allowed_delta}%)"

    if not reason:
        reason = group_loss_reason(losses, group_loss)

    if not reason and engine is not None:
        after_full = dict(before_state)
        after_full.update(after_state)
        fired = engine.rescue_rules_fired_by_battle(room, enemies or [], before_state, after_full, set(after_state))
        if fired:
            reason = f"Просадка до порога отхила: {fired}"

    return {"bad": bool(reason), "reason": reason, "after_state": after_state, "max_loss": max_loss}


def group_loss_reason(losses, group_loss):
    """Общие потери пака. losses — {титан: потеря ХП за бой, %}; group_loss — (сколько титанов, сколько %).
    Возвращает причину плохого боя или пустую строку."""
    if not group_loss:
        return ""
    titans_needed, percent = group_loss
    if not titans_needed or titans_needed <= 0:
        return ""
    hurt = [(t, lost) for t, lost in losses.items() if lost >= percent]
    if len(hurt) < titans_needed:
        return ""
    details = ", ".join(f"{t.upper()} {lost}%" for t, lost in hurt)
    return (f"Большие потери пака! По {percent}% ХП и больше потеряли: {details} "
            f"(порог: {titans_needed} и больше титанов)")


def battle_losses(pack, team_status, hp_before):
    """Сколько ХП потерял за бой каждый титан пака: {титан: %}. hp_before — {титан: ХП до боя};
    кого там нет, считаем вошедшим со 100%. Титаны, которых не нашли на окне результата, пропускаются."""
    losses = {}
    for titan in pack:
        stats = (team_status or {}).get(titan)
        if not isinstance(stats, dict) or stats.get("status") == "ОТСУТСТВУЕТ":
            continue
        after = 0 if stats.get("status") == "МЕРТВ" else stats.get("hp", 0)
        before = (hp_before or {}).get(titan)
        losses[titan] = max(0, (100 if before is None else before) - after)
    return losses


def full_hp_reason(pack, team_status, hp_before, critical_hp, allowed_delta, group_loss=None, titan_critical_hp=None):
    """
    Виноваты ли враги (задача 9б): был бы бой плохим, если бы все титаны пака вошли в него со 100% ХП?
    Берётся потеря каждого титана за бой, и с ней проверяются те же пороги, что после боя: порог паники
    (100% − потеря), допуск потерь, общие потери пака. Возвращает причину или пустую строку.
    Пустая строка — враги ни при чём: бой стал плохим, потому что кто-то вошёл в него раненым
    (сессия 07, комната 54: Араджи вошёл в огонь с 36% и упал до 9%, а со 100% осталось бы 73%).
    """
    titan_critical_hp = titan_critical_hp or {}
    losses = battle_losses(pack, team_status, hp_before)
    for titan, lost in losses.items():
        panic = titan_critical_hp.get(titan, critical_hp)
        if 100 - lost < max(1, panic):
            return f"{titan.upper()} потерял {lost}% ХП: даже со 100% осталось бы {100 - lost}% (порог {panic}%)"
        if lost > allowed_delta:
            return f"{titan.upper()} потерял {lost}% ХП (допуск: {allowed_delta}%)"
    return group_loss_reason(losses, group_loss)
