# Задача 13: итог сессии и красивые сообщения в Telegram, цветные кнопки, поведение без интернета.
# Вместо Telegram — поддельный сервер на этом компьютере (http.server): он записывает запросы,
# отвечает как Telegram или «зависает», как сеть без интернета.
import importlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import session_log
import telegram_report as tr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Поддельный сервер Telegram
# ---------------------------------------------------------------------------
class FakeTelegram:
    def __init__(self, hang=0.0):
        self.hang = hang
        self.requests = []  # (метод, тело запроса в байтах)
        self.updates = []   # что вернёт следующий getUpdates
        self.next_id = 100
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                method = self.path.rsplit("/", 1)[-1]
                fake.requests.append((method, body))
                if fake.hang:
                    time.sleep(fake.hang)
                if method == "getUpdates":
                    result, fake.updates = fake.updates, []
                elif method in ("sendMessage", "sendPhoto"):
                    fake.next_id += 1
                    result = {"message_id": fake.next_id}
                else:
                    result = True
                data = json.dumps({"ok": True, "result": result}).encode()
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except OSError:
                    pass  # клиент уже ушёл по таймауту

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def methods(self):
        return [m for m, _ in self.requests]

    def body(self, method):
        return [b for m, b in self.requests if m == method][-1]

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def tg(tmp_path, monkeypatch):
    """telegram_agent с адресом поддельного сервера и коротким ожиданием."""
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("telegram_agent", None)
    module = importlib.import_module("telegram_agent")
    monkeypatch.setattr(module, "TIMEOUT", (0.5, 0.5))
    yield module
    sys.modules.pop("telegram_agent", None)


@pytest.fixture
def server(tg, monkeypatch):
    fake = FakeTelegram()
    monkeypatch.setattr(tg, "API_URL", fake.url)
    yield fake
    fake.close()


def write_profile(path, token="123:SECRET", chat_id="42"):
    (path / "profile.yml").write_text(
        f"settings:\n  telegram:\n    active: true\n    token: '{token}'\n    chat_id: '{chat_id}'\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Итог сессии
# ---------------------------------------------------------------------------
def report(**over):
    data = {"reason": "Превышен лимит времени (60 мин)", "started": "14:03", "finished": "15:05", "seconds": 3720,
            "rooms": 47, "floors": 9, "titanite": 564, "by_room": {"mix": 20, "fire": 9, "water": 12, "earth": 6},
            "counts": {"sos": 2, "rollbacks": 3, "auto_rollbacks": 2, "stuck": 0},
            "longest": [(37, "fire", 135.0), (12, "mix", 98.0)], "avg_room": 70.0}
    data.update(over)
    return tr.session_report(data)


def test_session_report_limit_is_success():
    text = report()
    assert text.startswith("✅ <b>Фарм завершён</b>")
    assert "Превышен лимит времени (60 мин)" in text
    assert "🚪 Комнат: <b>47</b>" in text and "🏰 Этажей: <b>9</b>" in text and "💎 Титанит: <b>564</b>" in text
    assert "🕐 14:03 → 15:05" in text and "1 ч 02 мин" in text
    assert "🆘 Окон «Требуется вмешательство»: 2" in text
    assert "🔄 Откатов: 3 (бот сам: 2)" in text
    assert "Зависаний" not in text  # нули не показываем
    assert "№37 🔥 Огонь — 2 мин 15 с" in text
    assert text.index("🌀 20") < text.index("💧 12")  # стихии — по числу комнат


def test_session_report_crash_and_problems():
    text = report(reason="Ошибка: ValueError: x < 3", counts={})
    assert text.startswith("⛔ <b>Бот упал с ошибкой</b>")
    assert "x &lt; 3" in text  # HTML не ломается
    assert "👌 Без происшествий" in text
    assert report(reason="Пак не найден в правилах").startswith("⚠️")
    assert report(reason="Ручная остановка пользователем (Ctrl+Q)").startswith("⏹ <b>Бот остановлен вами</b>")
    assert report(reason="Пройдено 10 этажей.").startswith("✅")


def test_report_data_from_session_log():
    now = [0.0]
    log = session_log.SessionLog(clock=lambda: now[0])
    for room_type, seconds in (("fire", 50), ("mix", 90), ("fire", 70)):
        now[0] += seconds
        log.finish_room(len(log.records) + 1, room_type)
    log.count("sos")
    log.set_stop_reason("Пройдено 3 комнат.")
    data = log.report_data(3, 36, 0)
    assert data["rooms"] == 3 and data["titanite"] == 36 and data["floors"] == 0
    assert data["by_room"] == {"fire": 2, "mix": 1}
    assert data["counts"]["sos"] == 1 and data["seconds"] == 210
    totals = [r["total"] for r in log.records]
    assert data["avg_room"] == pytest.approx(sum(totals) / 3)
    assert data["longest"][0][2] == max(totals) and len(data["longest"]) == 3
    assert "Комнат: <b>3</b>" in tr.session_report(data)


# ---------------------------------------------------------------------------
# SOS и проверка пака
# ---------------------------------------------------------------------------
def test_sos_report_enemies_first():
    # Замечание к задаче 13: главное в SOS — на кого шли. Враги сразу под заголовком, ХП пака — одной строкой ниже
    info = {"room": "fire", "room_no": 54, "enemies": ["angus", "silva", "verdok"],
            "reason": "ARAJI: потерял 45% ХП (допуск 30%)",
            "team": {"araji": {"hp": 55, "energy": 47}, "ignis": {"hp": 0}, "acheron": {"hp": 0, "status": "ОТСУТСТВУЕТ"}},
            "hp_before": {"araji": 100}}
    text = tr.sos_report({"araji": 55}, info)
    assert text.startswith("🆘 <b>Нужна ваша помощь</b>\nкомната 54 · 🔥 Огонь\n\n⚔️ <b>Враги — на кого шли:</b>\n"
                           "   • <b>Ангус</b>\n   • <b>Сильва</b>\n   • <b>Вердок</b>")
    assert text.index("Вердок") < text.index("Араджи: потерял 45% ХП") < text.index("🛡 Наш пак")
    assert "ARAJI" not in text  # причина не как в логе
    assert "🛡 Наш пак: 🟡 Араджи 55%  💀 Игнис 0%  ❔ Ашерон" in text
    assert len(text) <= tr.CAPTION_LIMIT


def test_sos_report_without_info_and_no_team():
    text = tr.sos_report({"hyperion": 80}, {})
    assert "🟢 Гиперион 80%" in text and "Враги" not in text
    text = tr.sos_report({}, {"type": "NO_VALID_TEAM", "room": "earth", "enemies": [], "reason": "Нет пака"},
                         can_rollback=False)
    assert "Нет подходящего пака" in text and "не распознаны" in text and "🌿 Земля" in text


def test_sos_info_file_round_trip_and_stale(tmp_path):
    path = str(tmp_path / "bot_data" / "sos_info.json")
    tr.write_sos_info(path, {"room": "mix", "enemies": ["eden"]}, now=1000)
    assert tr.read_sos_info(path, now=1050)["enemies"] == ["eden"]
    assert tr.read_sos_info(path, now=1000 + tr.SOS_INFO_MAX_AGE_S + 1) == {}  # от прошлого окна SOS
    assert tr.read_sos_info(str(tmp_path / "нет.json")) == {}


def styles(markup):
    return {b["callback_data"]: b.get("style") for row in markup["inline_keyboard"] for b in row}


def test_buttons_are_colored():
    assert styles(tr.sos_keyboard()) == {"rollback": "success", "manual": "primary", "ignore": None}
    assert styles(tr.sos_keyboard(is_manual=True))["stop"] == "danger"
    assert styles(tr.test_keyboard()) == {"test_confirm": "success", "test_retry": "primary"}
    assert styles(tr.pack_confirm_keyboard()) == {"confirm_pack": "success", "retry_pack": "primary"}


def test_test_report():
    text = tr.test_report({"rigel": {"hp": 90, "energy": 10}})
    assert text.startswith("🧪 <b>") and "🟢 <b>Ригель</b>" in text and "⚡10%" in text


def test_alert_escapes_and_shows_room():
    text = tr.alert("⚠️", "Откат боя не удался", ["пауза <нет>"], room="water", enemies=["tidus"], footer="Бот на паузе")
    assert text.startswith("⚠️ <b>Откат боя не удался</b>")
    assert "пауза &lt;нет&gt;" in text and "💧 Вода" in text and "<i>Бот на паузе</i>" in text
    assert text.index("⚔️ <b>Враги:</b> Тидус") < text.index("пауза")  # враги выше пояснения


# ---------------------------------------------------------------------------
# Отправка на поддельный сервер
# ---------------------------------------------------------------------------
def test_send_alert_html(tg, server, tmp_path):
    write_profile(tmp_path)
    sent, note = tg.send_alert(report(), html=True)
    assert sent, note
    body = json.loads(server.body("sendMessage"))
    assert body["parse_mode"] == "HTML" and body["chat_id"] == "42" and "Фарм завершён" in body["text"]


def test_send_alert_long_caption_goes_as_photo_and_message(tg, server, tmp_path):
    write_profile(tmp_path)
    image = tmp_path / "shot.png"
    image.write_bytes(b"png")
    sent, _ = tg.send_alert("<b>x</b>\n" + "строка\n" * 300, str(image), html=True)
    assert sent and server.methods() == ["sendPhoto", "sendMessage"]


def test_agent_sos_colored_buttons_and_answer(tg, server, tmp_path):
    agent = tg.TelegramAgent("123:SECRET", "42", "RU")
    image = tmp_path / "sos.png"
    image.write_bytes(b"png")
    msg_id = agent.send_sos(str(image), tr.sos_report({"araji": 30}), can_rollback=True)
    assert msg_id
    photo = server.body("sendPhoto")
    assert b'"style": "success"' in photo and b'"style": "primary"' in photo and b"HTML" in photo

    answers = []
    server.updates = [{"update_id": 7, "callback_query": {"id": "c1", "data": "manual"}}]
    agent.start_polling(msg_id, answers.append)
    deadline = time.time() + 5
    while not answers and time.time() < deadline:
        time.sleep(0.05)
    assert answers == ["manual"]
    time.sleep(0.2)
    markup = json.loads(server.body("editMessageReplyMarkup"))["reply_markup"]
    button = markup["inline_keyboard"][0][0]
    assert button["style"] == "success" and "Пройти руками" in button["text"]


# ---------------------------------------------------------------------------
# Без интернета бот не зависает
# ---------------------------------------------------------------------------
def test_send_alert_hanging_server_returns_fast(tg, tmp_path, monkeypatch):
    fake = FakeTelegram(hang=10)
    monkeypatch.setattr(tg, "API_URL", fake.url)
    write_profile(tmp_path)
    try:
        started = time.monotonic()
        sent, note = tg.send_alert("итог", html=True)
        assert sent is False and "сбой связи" in note
        assert time.monotonic() - started < 3
        started = time.monotonic()
        tg.TelegramAgent("123:SECRET", "42", "RU")  # чистка старых нажатий тоже не висит
        assert time.monotonic() - started < 5
    finally:
        fake.close()


def test_no_server_does_not_raise_and_hides_token(tg, tmp_path, monkeypatch):
    monkeypatch.setattr(tg, "API_URL", "http://127.0.0.1:9")  # здесь никто не слушает
    write_profile(tmp_path)
    started = time.monotonic()
    sent, note = tg.send_alert("итог")
    assert sent is False and time.monotonic() - started < 3
    assert "SECRET" not in note and "***" in note  # токен не попадает в лог бота


def test_agent_send_fails_quietly_without_network(tg, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(tg, "API_URL", "http://127.0.0.1:9")
    agent = tg.TelegramAgent("123:SECRET", "42", "RU")
    assert agent.send_message("x") is None
    assert agent.send_sos(str(tmp_path / "нет.png"), "x") is None
    assert "SECRET" not in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Токен — только в profile.yml
# ---------------------------------------------------------------------------
TOKEN_RE = re.compile(rb"\d{6,12}:[A-Za-z0-9_-]{30,}")


def test_no_telegram_token_in_repository():
    try:
        files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git недоступен")
    found = []
    for name in files:
        path = os.path.join(ROOT, name)
        if name.startswith("assets/") or not os.path.isfile(path) or os.path.getsize(path) > 5_000_000:
            continue
        with open(path, "rb") as f:
            content = f.read()
        try:
            content.decode("utf-8")  # картинки и другие двоичные файлы пропускаем
        except UnicodeDecodeError:
            continue
        if TOKEN_RE.search(content):
            found.append(name)
    assert found == []


def test_unknown_room_is_not_shown():
    assert "Комната" not in tr.alert("🧊", "Бот завис", ["x"], room="unknown")
    assert tr.sos_report({"araji": 50}, {"room": "unknown", "room_no": 1}).startswith("🆘 <b>Нужна ваша помощь</b>\nкомната 1\n")


def test_humanize_reason():
    assert tr.humanize("ARAJI: ХП 12% ниже порога, SOS и ОК") == "Араджи: ХП 12% ниже порога, SOS и ОК"
    assert tr.humanize("RIGEL 30%", "EN").startswith("Rigel")
