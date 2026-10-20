# Поддельный `adb shell sh` для tests/test_adb_shell.py: читает команды построчно и отвечает метками,
# как настоящий sh на телефоне ("input tap 1 2; echo __HWB_DONE__7" → печатает "__HWB_DONE__7").
# Аргументы: файл, куда записывать полученные команды; сколько команд выполнить и выйти (0 — без конца);
# "silent" — не отвечать вовсе (телефон завис).
import sys

log_path = sys.argv[1]
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 0
silent = len(sys.argv) > 3 and sys.argv[3] == "silent"
done = 0
for raw in sys.stdin.buffer:
    line = raw.decode("utf-8").strip()
    if not line:
        continue
    command, _, mark = line.partition("; echo ")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(command + "\n")
    if silent:
        continue
    if command.startswith("input bad"):
        sys.stdout.buffer.write(b"Error: Unknown command: bad\n")
    sys.stdout.buffer.write((mark + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()
    done += 1
    if limit and done >= limit:
        break
