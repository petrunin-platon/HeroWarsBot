"""SOS и проверка пака в Telegram из нового окна (задача 15, шаг 3) — с повторами при обрыве связи.

Старое окно (ui/intervention_dialog.py, ui/dashboard.py) слало вопрос один раз: нет интернета — сообщение терялось
(PLAN.md, задача 15, обязательный пункт). Теперь — как тревоги бота (telegram_agent.send_alert_in_background):
не ушло из-за связи — снова через 30 с, 1, 2, 5 и 10 мин (telegram_agent.ALERT_RETRY_S); ошибки самого Telegram
(неверный токен) не повторяются. Сообщение то же, что раньше: скриншот, подпись telegram_report.sos_report или
test_report и цветные кнопки; потом ожидание нажатия (TelegramAgent.start_polling).
Ответили в окне программы, ответили в Telegram или бот решил сам — stop(): повторы и ожидание нажатия прекращаются.
Ответ из Telegram приходит в фоновом потоке: on_answer кладёт его в очередь окна (виджеты Tk из потока не трогаем).
Строки для журнала — через log (тоже в очередь).
Модуль без Tk: проверяется на поддельном сервере Telegram (tests/test_bot_link.py).
"""
import threading

import data_paths
import telegram_agent
import telegram_report

SOS, TEST = "sos", "test"
NAMES = {SOS: "SOS", TEST: "Проверка пака"}


def telegram_ready(profile_path="profile.yml"):
    """Telegram включён и заполнен (то же правило, что у бота)."""
    token, _chat_id, _why = telegram_agent.read_telegram_settings(profile_path)
    return bool(token)


class TelegramQuestion:
    """Один вопрос в Telegram: SOS («Требуется вмешательство», «Нет подходящего пака») или «Пак справился».
    titans — ХП титанов из строки бота; info — bot_data/sos_info.json (комната, враги, причина), прочитанный окном."""

    def __init__(self, kind, titans, lang, on_answer, log, info=None, is_manual=False, can_rollback=True,
                 profile_path="profile.yml", delays=None, on_failed=None):
        self.on_failed = on_failed      # вопрос так и не ушёл (окно программы спросит само)
        self.kind = kind
        self.titans = titans
        self.lang = lang
        self.on_answer = on_answer
        self.log = log
        self.info = info or {}
        self.is_manual = is_manual
        self.can_rollback = can_rollback
        self.profile_path = profile_path
        self.delays = delays
        self.agent = None
        self.sent = False
        self._stopped = threading.Event()

    def start(self):
        threading.Thread(target=self._run, name="tg-question", daemon=True).start()
        return self

    def stop(self):
        """Вопрос больше не нужен: не повторять отправку и не ждать нажатия."""
        self._stopped.set()
        agent = self.agent
        if agent:
            agent.stop()

    @property
    def stopped(self):
        return self._stopped.is_set()

    def _run(self):
        token, chat_id, _why = telegram_agent.read_telegram_settings(self.profile_path)
        if not token or self.stopped:
            return  # Telegram не настроен — как в старом окне, молча
        agent = telegram_agent.TelegramAgent(token, chat_id, self.lang)
        self.agent = agent
        if self.stopped:
            return
        if self.kind == SOS:
            text = telegram_report.sos_report(self.titans, self.info, is_manual=self.is_manual,
                                              can_rollback=self.can_rollback, lang=self.lang)

            def send():
                return agent.send_sos(data_paths.temp_sos_file(), text, is_manual=self.is_manual,
                                      can_rollback=self.can_rollback)
        else:
            text = telegram_report.test_report(self.titans, self.lang)

            def send():
                return agent.send_test_result(data_paths.temp_test_file(), text)

        name = NAMES[self.kind]
        delays = list(telegram_agent.ALERT_RETRY_S if self.delays is None else self.delays)
        tries = 0
        while True:
            msg_id = send()
            tries += 1
            if msg_id:
                break
            error = agent.last_error or ""
            if not error.startswith(telegram_agent.NETWORK_ERROR) or not delays:
                self.log(f"[TELEGRAM] {name} в Telegram не отправлен: {error or 'нет ответа'}\n")
                if self.on_failed and not self.stopped:
                    self.on_failed()
                return
            delay = delays.pop(0)
            self.log(f"[TELEGRAM] {name} в Telegram не ушёл ({error}). Пробую снова через {delay} с.\n")
            if self._stopped.wait(delay):
                return
            agent._clear_history()  # пока не было связи, в Telegram могли остаться старые нажатия — их не берём
        self.sent = True
        self.log(f"[TELEGRAM] {name} отправлен в Telegram" + (f" с {tries}-й попытки" if tries > 1 else "") + ".\n")
        if not self.stopped:
            agent.start_polling(msg_id, self._answer)

    def _answer(self, decision):
        if not self.stopped:
            self.stop()
            self.on_answer(decision)
