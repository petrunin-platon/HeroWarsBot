# telegram_agent.py
import requests
import time
import threading
import json
import re
import os
from i18n import get_text
import telegram_report

BASE_TITANS = [
    "hyperion", "sigurd", "tidus", "nova", "mairi", "orm",
    "angus", "avalon", "eden", "silva", "verdok", "pallant",
    "araji", "ignis", "acheron", "vulcan", "moloch", "alecto",
    "rigel", "iyari", "lumira", "solaris", "amon",
    "mor", "tenebris", "brustar", "umbra", "keros"
]

# Все запросы к Telegram — с ограничением по времени (задача 13): без интернета бот и окно программы не зависают.
# (секунды на соединение, секунды на ответ). Тесты подменяют API_URL на поддельный сервер.
API_URL = "https://api.telegram.org"
TIMEOUT = (5, 15)
POLL_SECONDS = 5  # сколько Telegram держит запрос getUpdates, если нажатий нет
# Начало пояснения, когда до Telegram не достучались (нет интернета, обрыв). Только такие сообщения стоит отправлять снова
NETWORK_ERROR = "сбой связи с Telegram"
# Сообщение бота не ушло из-за связи — пробуем снова через столько секунд (всего ~18 мин). Сессия 10: интернет пропал
# на несколько минут, и сообщение «откат не удался» потерялось с первой же попытки
ALERT_RETRY_S = (30, 60, 120, 300, 600)


def _hide_token(text, token):
    """Ошибка requests содержит адрес запроса, а в нём токен. В лог (и потом в logs/ на GitHub) токен попасть не должен."""
    text = str(text)
    return text.replace(token, "***") if token else text


def call_api(token, method, data=None, files=None, timeout=None):
    """Один запрос к Telegram. Возвращает (ответ Telegram или None, пояснение ошибки или None). Ошибок не бросает."""
    url = f"{API_URL}/bot{token}/{method}"
    try:
        if files:
            resp = requests.post(url, data=data, files=files, timeout=timeout or TIMEOUT)
        else:
            resp = requests.post(url, json=data or {}, timeout=timeout or TIMEOUT)
        result = resp.json()
    except Exception as e:
        return None, f"{NETWORK_ERROR}: {_hide_token(e, token)}"
    if not isinstance(result, dict) or not result.get("ok"):
        desc = result.get("description", result) if isinstance(result, dict) else result
        return None, f"Telegram ответил ошибкой: {_hide_token(desc, token)}"
    return result, None


def _post_text_or_photo(token, chat_id, text, image_path=None, reply_markup=None, html=False):
    """Сообщение или скриншот с подписью. Подпись длиннее 1024 знаков: скриншот отдельно, текст отдельно."""
    extra = {"parse_mode": "HTML"} if html else {}
    if reply_markup is not None:
        extra["reply_markup"] = json.dumps(reply_markup)
    if image_path and os.path.exists(image_path):
        long_text = len(text) > telegram_report.CAPTION_LIMIT
        data = {"chat_id": chat_id, **({} if long_text else {"caption": text, **extra})}
        try:
            with open(image_path, "rb") as f:
                result, error = call_api(token, "sendPhoto", data=data, files={"photo": f})
        except OSError as e:
            result, error = None, f"не удалось открыть скриншот: {e}"
        if not long_text or error:
            return result, error
    data = {"chat_id": chat_id, "text": text[:telegram_report.MESSAGE_LIMIT], **extra}
    if "reply_markup" in data:
        data["reply_markup"] = reply_markup
    return call_api(token, "sendMessage", data=data)


def read_telegram_settings(profile_path="profile.yml"):
    """(token, chat_id, пояснение). Токен и chat_id — только из profile.yml. Нет настроек — token пустой."""
    try:
        import yaml
        with open(profile_path, "r", encoding="utf-8") as f:
            tg = ((yaml.safe_load(f) or {}).get("settings", {}) or {}).get("telegram", {}) or {}
    except Exception as e:
        return "", "", f"не удалось прочитать {profile_path}: {e}"
    if not tg.get("active", False):
        return "", "", "Telegram выключен в настройках"
    token, chat_id = str(tg.get("token", "") or ""), str(tg.get("chat_id", "") or "")
    if not token or not chat_id or "YOUR_" in token or "YOUR_" in chat_id or chat_id == "None":
        return "", "", "в настройках Telegram нет токена или chat_id"
    return token, chat_id, ""


def send_alert(text, image_path=None, profile_path="profile.yml", html=False):
    """Присылает в Telegram простое сообщение (со скриншотом, если он есть), без кнопок и без ожидания ответа.
    Токен и chat_id берёт из profile.yml. html=True — текст из telegram_report (жирный шрифт, значки).
    Ошибок не бросает и не ждёт дольше TIMEOUT: возвращает (удалось, пояснение для лога)."""
    token, chat_id, why = read_telegram_settings(profile_path)
    if not token:
        return False, why
    result, error = _post_text_or_photo(token, chat_id, text, image_path, html=html)
    if error:
        return False, error
    return True, "отправлено"


def send_alert_retrying(text, image_path=None, profile_path="profile.yml", html=False, delays=ALERT_RETRY_S,
                        sleep=time.sleep, on_retry=None):
    """Как send_alert, но если до Telegram не достучались (нет интернета), ждёт и пробует снова: паузы delays (секунды).
    Ошибки самого Telegram (неверный токен и т. п.) и выключенный Telegram не повторяются.
    on_retry(пояснение, через сколько секунд) — перед каждой паузой (для лога). Возвращает (удалось, пояснение)."""
    sent, note = send_alert(text, image_path, profile_path, html)
    tries = 1
    for delay in delays:
        if sent or not note.startswith(NETWORK_ERROR):
            break
        if on_retry:
            on_retry(note, delay)
        sleep(delay)
        sent, note = send_alert(text, image_path, profile_path, html)
        tries += 1
    if sent and tries > 1:
        note = f"отправлено с {tries}-й попытки"
    return sent, note


def send_alert_in_background(text, image_path=None, html=False, log=print, prefix="[TELEGRAM]", profile_path="profile.yml",
                             delays=ALERT_RETRY_S):
    """Сообщение в Telegram в фоне, с повторами при обрыве связи (send_alert_retrying): бот не ждёт и работает дальше.
    Итог пишет в лог строкой «<prefix> Сообщение в Telegram: ...». Возвращает поток."""
    def retry_note(note, delay):
        log(f"{prefix} Сообщение в Telegram не ушло ({note}). Пробую снова через {delay} с.")

    def run():
        sent, note = send_alert_retrying(text, image_path, profile_path, html, delays=delays, on_retry=retry_note)
        log(f"{prefix} Сообщение в Telegram: {note}")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


class TelegramAgent:
    def __init__(self, token, chat_id, lang=None):
        self.token = token
        self.chat_id = chat_id
        self.is_active = False
        self.last_update_id = 0
        
        self.lang = lang or os.environ.get("HEROWARS_LANG", "RU")
        
        self.titan_dict = {
            "hyp": "hyperion", "sig": "sigurd", "tid": "tidus", "nov": "nova", "mai": "mairi", "orm": "orm",
            "ang": "angus", "ava": "avalon", "ede": "eden", "sil": "silva", "ver": "verdok", "pal": "pallant",
            "ara": "araji", "ign": "ignis", "ach": "acheron", "vul": "vulcan", "mol": "moloch", "ale": "alecto",
            "rig": "rigel", "iya": "iyari", "lum": "lumira", "sol": "solaris", "amo": "amon",
            "mor": "mor", "ten": "tenebris", "bru": "brustar", "umb": "umbra", "ker": "keros"
        }
        
        for t in BASE_TITANS:
            loc_name = get_text(self.lang, f"titan_{t}").lower()
            self.titan_dict[loc_name] = t
            if len(loc_name) >= 3:
                self.titan_dict[loc_name[:3]] = t
        
        self.tg_state = "IDLE"
        self.temp_pack = []
        self.main_msg_id = None
        self.prompt_msg_id = None
        # Почему не ушло последнее окно SOS / проверки пака (None — ушло). По нему окно программы решает, повторять ли:
        # повторяет, только если не было связи (NETWORK_ERROR), как тревоги бота (задача 15, шаг 3)
        self.last_error = None
        
        # 🛡 Убиваем старые клики при каждом запуске агента!
        self._clear_history()

    def _call(self, method, data=None, files=None, timeout=None):
        """Запрос к Telegram с ограничением по времени. Ответ Telegram или None (ошибку печатает в лог)."""
        result, error = call_api(self.token, method, data, files, timeout)
        if error:
            print(f"[TELEGRAM] {method}: {error}")
        return result

    def _clear_history(self):
        """Прочитывает и стирает все зависшие нажатия кнопок на сервере Telegram"""
        resp = self._call("getUpdates", {"timeout": 0})
        if resp and resp["result"]:
            self.last_update_id = resp["result"][-1]["update_id"]
            # Отправляем подтверждение, что мы всё прочитали
            self._call("getUpdates", {"offset": self.last_update_id + 1, "timeout": 0})

    def delete_message(self, msg_id):
        if msg_id:
            self._call("deleteMessage", {"chat_id": self.chat_id, "message_id": msg_id})

    def send_message(self, text, reply_markup=None, html=False):
        data = {"chat_id": self.chat_id, "text": text}
        if html:
            data["parse_mode"] = "HTML"
        if reply_markup:
            data["reply_markup"] = reply_markup
        resp = self._call("sendMessage", data)
        return resp["result"]["message_id"] if resp else None

    def update_keyboard(self, msg_id, reply_markup):
        payload = {"chat_id": self.chat_id, "message_id": msg_id}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        self._call("editMessageReplyMarkup", payload)

    def parse_titans(self, text):
        words = re.split(r'[,\s\.\-、，]+', text.lower())
        found = []
        for w in words:
            if not w: continue
            if w in self.titan_dict:
                t = self.titan_dict[w]
                if t not in found: found.append(t)
                continue
            if len(w) >= 3:
                prefix = w[:3]
                if prefix in self.titan_dict:
                    t = self.titan_dict[prefix]
                    if t not in found: found.append(t)
        return found

    def _send_photo(self, image_path, caption, reply_markup):
        """Скриншот с подписью (HTML) и цветными кнопками. Возвращает номер сообщения или None."""
        if not self.token or not self.chat_id: return None
        result, error = _post_text_or_photo(self.token, self.chat_id, caption, image_path, reply_markup, html=True)
        self.last_error = error
        if error:
            print(f"[TELEGRAM] Сбой отправки: {error}")
            return None
        self.main_msg_id = result["result"]["message_id"]
        return self.main_msg_id

    def send_sos(self, image_path, text, is_manual=False, can_rollback=True):
        """Окно SOS в Telegram. text — подпись из telegram_report.sos_report (HTML)."""
        return self._send_photo(image_path, text, telegram_report.sos_keyboard(is_manual, can_rollback, self.lang))

    def send_test_result(self, image_path, text):
        """Проверяемый пак выиграл. text — подпись из telegram_report.test_report (HTML)."""
        return self._send_photo(image_path, text, telegram_report.test_keyboard(self.lang))

    def _chosen_label(self, action):
        """Подпись кнопки «✅ Выбрано: …» на вашем языке, а не MANUAL/IGNORE."""
        keys = {"manual": "tg_bot_manual", "ignore": "tg_bot_ignore", "stop": "tg_bot_stop"}
        return get_text(self.lang, "tg_bot_selected").format(action=get_text(self.lang, keys[action]))

    def _ask_pack(self):
        """Просим написать пак текстом."""
        self.tg_state = "WAITING_TEXT"
        txt = "✍️ " + telegram_report.esc(get_text(self.lang, "tg_bot_wait_text"))
        self.prompt_msg_id = self.send_message(txt, html=True)

    def start_polling(self, message_id, callback):
        # Защита от утечки потоков и дублирования запросов (Race Condition / API Ban)
        if self.is_active:
            print("[TELEGRAM] Поллинг уже запущен, игнорирую повторный вызов.")
            return
            
        self.is_active = True
        self.main_msg_id = message_id

        def poll():
            while self.is_active:
                params = {"offset": self.last_update_id + 1, "timeout": POLL_SECONDS}
                resp = self._call("getUpdates", params, timeout=(TIMEOUT[0], POLL_SECONDS + TIMEOUT[1]))
                if resp is None:
                    # ЭТАЛОННАЯ ЗАЩИТА ОТ API BAN (МЕХАНИЗМ BACKOFF)
                    print("[TELEGRAM] Включаю механизм защиты от бана. Принудительная пауза 5 сек...")
                    time.sleep(5)
                    continue

                try:
                    for update in resp["result"]:
                        self.last_update_id = update["update_id"]
                        if not self.is_active:
                            return  # окно уже закрыли (бот решил сам): нажатие не обрабатываем

                        if "callback_query" in update:
                            cq = update["callback_query"]
                            action = cq["data"]
                            self._call("answerCallbackQuery", {"callback_query_id": cq["id"]})

                            if action in ("rollback", "test_retry"):
                                self.update_keyboard(self.main_msg_id, {"inline_keyboard": []})
                                self._ask_pack()
                                continue

                            elif action == "test_confirm":
                                self.is_active = False
                                btn_text = get_text(self.lang, "tg_bot_selected").format(
                                    action=get_text(self.lang, "tg_bot_btn_confirm"))
                                self.update_keyboard(self.main_msg_id, telegram_report.chosen(btn_text))
                                callback("CONFIRM")
                                return

                            elif action == "confirm_pack":
                                self.tg_state = "IDLE"
                                self.delete_message(self.prompt_msg_id)
                                self.update_keyboard(self.main_msg_id,
                                                     telegram_report.chosen(get_text(self.lang, "tg_bot_rollback_ok")))
                                self.is_active = False
                                callback(f"rb_custom:{','.join(self.temp_pack)}")
                                return

                            elif action == "retry_pack":
                                self.delete_message(self.prompt_msg_id)
                                self._ask_pack()
                                continue

                            elif action in ["manual", "ignore", "stop"]:
                                self.is_active = False
                                self.update_keyboard(self.main_msg_id, telegram_report.chosen(self._chosen_label(action)))
                                callback(action)
                                return

                        elif "message" in update and "text" in update["message"]:
                            text = update["message"]["text"]
                            user_msg_id = update["message"]["message_id"]

                            if self.tg_state == "WAITING_TEXT":
                                self.delete_message(user_msg_id) 
                                self.delete_message(self.prompt_msg_id)

                                parsed = self.parse_titans(text)
                                if 3 <= len(parsed) <= 5:
                                    self.temp_pack = parsed
                                    self.tg_state = "CONFIRMING"
                                    names = "\n".join(f"• <b>{telegram_report.esc(telegram_report.titan_name(t, self.lang))}</b>"
                                                      for t in parsed)
                                    txt = "🛡 " + get_text(self.lang, "tg_bot_pack_confirm").format(names=names)
                                    self.prompt_msg_id = self.send_message(
                                        txt, telegram_report.pack_confirm_keyboard(self.lang), html=True)
                                else:
                                    names_str = ", ".join([get_text(self.lang, f"titan_{t}").capitalize() for t in parsed]) if parsed else get_text(self.lang, "tg_bot_none")
                                    txt = get_text(self.lang, "tg_bot_err_count").format(count=len(parsed), names=names_str)
                                    self.prompt_msg_id = self.send_message(txt)

                except Exception as e:
                    print(f"[TELEGRAM] Ошибка разбора ответа Telegram: {_hide_token(e, self.token)}")
                    time.sleep(5)
                
                # Штатная пауза между успешными запросами
                time.sleep(1)

        threading.Thread(target=poll, daemon=True).start()

    def stop(self):
        self.is_active = False
