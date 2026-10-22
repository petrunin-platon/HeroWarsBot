"""Поддельный бот для тестов окна (задача 15, шаг 3): печатает строки сценария и отвечает на команды из stdin,
как main.py: тот же протокол ([SOS_TRIGGER], [SOS_CLOSE], [ПАУЗА ОТЛАДКИ], команды одной строкой).

Запуск: python fake_bot.py [сценарий.json] — без пути берётся fake_bot.json в папке запуска (так окно запускает его
той же командой, что настоящего бота: тест кладёт этот файл в папку под именем main.py).
Сценарий: {"steps": [[строки], [строки], ...], "ignore_stop": false, "sos_info": {...}}
- в начале печатается steps[0], после каждой команды — следующий шаг;
- каждая команда печатается строкой «[ТЕСТ] Получено: '<команда>'»;
- STOP — строки [ИТОГ] и выход, как настоящий бот (если не ignore_stop);
- строка «@exit» — выйти, «@sleep N» — подождать N с, «@info» — записать bot_data/sos_info.json из "sos_info".
"""
import json
import os
import sys
import time

path = sys.argv[1] if len(sys.argv) > 1 else "fake_bot.json"
with open(path, encoding="utf-8") as f:
    scenario = json.load(f)
steps = scenario.get("steps", [])


def say(line):
    print(line, flush=True)


def play(lines):
    for line in lines:
        if line == "@exit":
            sys.exit(0)
        if line.startswith("@sleep"):
            time.sleep(float(line.split()[1]))
        elif line == "@info":
            os.makedirs("bot_data", exist_ok=True)
            with open(os.path.join("bot_data", "sos_info.json"), "w", encoding="utf-8") as f:
                json.dump({**scenario.get("sos_info", {}), "saved": time.time()}, f, ensure_ascii=False)
        else:
            say(line)


say(f"10:00:00.000 [ТЕСТ] Язык: {os.environ.get('HEROWARS_LANG')}")
play(steps[0] if steps else [])
step = 1
for raw in sys.stdin:
    command = raw.rstrip("\n")
    say(f"10:00:01.000 [ТЕСТ] Получено: {command!r}")
    if command == "STOP" and not scenario.get("ignore_stop"):
        say("10:00:02.000 [ТАКТИКА] Экстренная остановка по команде пользователя.")
        say("10:00:02.100 [ИТОГ] ========== Итог сессии ==========")
        say("10:00:02.100 [ИТОГ] Причина остановки: Команда STOP из окна SOS")
        say("10:00:02.100 [ИТОГ] Длительность: 5 с | Комнат: 2 | Титанит: 12")
        say("10:00:02.100 [ИТОГ] промахи по двери 0 | повторные нажатия 0 | окна SOS 1 | откаты 0 | из них без вас 0")
        sys.exit(0)
    if step < len(steps):
        play(steps[step])
    step += 1
