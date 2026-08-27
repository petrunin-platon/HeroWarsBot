def evaluate_battle(team_status, current_room):
    """
    Анализирует состояние команды и возвращает решение.
    """
    # Твоё правило: Если Ригель просел ниже 40% (или умер)
    if "rigel" in team_status:
        hp = team_status["rigel"]["hp"]
        if hp < 40:
            return {
                "action": "rollback", 
                "reason": f"ХП Ригеля критическое ({hp}%)!"
            }
            
    # В будущем сюда можно добавить правила для других комнат и титанов
    
    return {
        "action": "accept", 
        "reason": "Все показатели в норме."
    }