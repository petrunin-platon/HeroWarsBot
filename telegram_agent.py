# telegram_agent.py
import requests
import time
import threading
import json
import re

# Словарь для парсинга (хватает первых 3 букв для 100% уникальной идентификации)
TITAN_DICT = {
    "гип": "hyperion", "сиг": "sigurd", "тид": "tidus", "нов": "nova", "маи": "mairi", "май": "mairi", "орм": "orm",
    "анг": "angus", "ава": "avalon", "эде": "eden", "эдэ": "eden", "сил": "silva", "вер": "verdok", "пал": "pallant",
    "ара": "araji", "игн": "ignis", "аше": "acheron", "вул": "vulcan", "мол": "moloch", "але": "alecto",
    "риг": "rigel", "ияр": "iyari", "люм": "lumira", "сол": "solaris", "амо": "amon",
    "мор": "mor", "тен": "tenebris", "бру": "brustar", "умб": "umbra", "кер": "keros"
}

TITAN_RU = {
    "hyperion": "Гиперион", "sigurd": "Сигурд", "tidus": "Тидус", "nova": "Нова", "mairi": "Маири", "orm": "Орм",
    "angus": "Ангус", "avalon": "Авалон", "eden": "Эдем", "silva": "Сильва", "verdok": "Вердок", "pallant": "Паллант",
    "araji": "Араджи", "ignis": "Игнис", "acheron": "Ашерон", "vulcan": "Вулкан", "moloch": "Молох", "alecto": "Алекто",
    "rigel": "Ригель", "iyari": "Ияри", "lumira": "Люмира", "solaris": "Солярис", "amon": "Амон",
    "mor": "Мор", "tenebris": "Тенебрис", "brustar": "Брустар", "umbra": "Умбра", "keros": "Керос"
}

class TelegramAgent:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.is_active = False
        self.last_update_id = 0
        
        # Состояния для общения
        self.tg_state = "IDLE"
        self.temp_pack = []
        self.main_msg_id = None
        self.prompt_msg_id = None

    def delete_message(self, msg_id):
        """Удаляет сообщение из чата (работает и для сообщений бота, и для юзера)"""
        requests.post(f"{self.base_url}/deleteMessage", json={"chat_id": self.chat_id, "message_id": msg_id})

    def send_message(self, text, reply_markup=None):
        data = {"chat_id": self.chat_id, "text": text}
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        resp = requests.post(f"{self.base_url}/sendMessage", json=data).json()
        if resp.get("ok"):
            return resp["result"]["message_id"]
        return None

    def update_keyboard(self, msg_id, reply_markup):
        """Обновляет кнопки под существующим сообщением (без отправки нового)"""
        requests.post(f"{self.base_url}/editMessageReplyMarkup", json={
            "chat_id": self.chat_id,
            "message_id": msg_id,
            "reply_markup": reply_markup
        })

    def parse_titans(self, text):
        """Умный парсер: бьет текст по пробелам и запятым, ищет по префиксу 3 букв"""
        words = re.split(r'[,\s\.\-]+', text.lower())
        found = []
        for w in words:
            if len(w) >= 3:
                prefix = w[:3]
                if prefix in TITAN_DICT:
                    t = TITAN_DICT[prefix]
                    if t not in found:
                        found.append(t)
        return found

    def send_sos(self, image_path, text, is_manual=False):
        if not self.token or not self.chat_id:
            return None

        url = f"{self.base_url}/sendPhoto"
        if is_manual:
            btn_middle = {"text": "🛑 Остановить бота", "callback_data": "stop"}
        else:
            btn_middle = {"text": "🔄 Откатить (Собрать пак)", "callback_data": "rollback"}

        reply_markup = {
            "inline_keyboard": [
                [{"text": "🎮 Пройти руками", "callback_data": "manual"}, btn_middle],
                [{"text": "➡️ Игнорировать (Продолжить)", "callback_data": "ignore"}]
            ]
        }

        data = {
            "chat_id": self.chat_id,
            "caption": text,
            "reply_markup": json.dumps(reply_markup)
        }

        try:
            with open(image_path, "rb") as f:
                files = {"photo": f}
                response = requests.post(url, data=data, files=files)
                result = response.json()
                if result.get("ok"):
                    self.main_msg_id = result["result"]["message_id"]
                    return self.main_msg_id
        except Exception as e:
            print(f"[TELEGRAM] Сбой отправки: {e}")
        return None

    def start_polling(self, message_id, callback):
        self.is_active = True
        self.main_msg_id = message_id

        def poll():
            url = f"{self.base_url}/getUpdates"
            while self.is_active:
                try:
                    params = {"offset": self.last_update_id + 1, "timeout": 5}
                    resp = requests.get(url, params=params, timeout=10).json()

                    if resp.get("ok"):
                        for update in resp["result"]:
                            self.last_update_id = update["update_id"]

                            # --- ОБРАБОТКА НАЖАТИЙ КНОПОК ---
                            if "callback_query" in update:
                                cq = update["callback_query"]
                                action = cq["data"]
                                cq_msg_id = cq.get("message", {}).get("message_id")
                                requests.post(f"{self.base_url}/answerCallbackQuery", json={"callback_query_id": cq["id"]})

                                if action == "rollback":
                                    self.tg_state = "WAITING_TEXT"
                                    kb = {"inline_keyboard": [[{"text": "⌨️ Напишите имена титанов в чат...", "callback_data": "noop"}]]}
                                    self.update_keyboard(self.main_msg_id, kb)
                                    continue

                                elif action == "confirm_pack":
                                    self.tg_state = "IDLE"
                                    self.delete_message(self.prompt_msg_id)
                                    kb = {"inline_keyboard": [[{"text": "✅ Откат запущен!", "callback_data": "noop"}]]}
                                    self.update_keyboard(self.main_msg_id, kb)
                                    
                                    self.is_active = False
                                    callback(f"rb_custom:{','.join(self.temp_pack)}")
                                    return

                                elif action == "retry_pack":
                                    self.tg_state = "WAITING_TEXT"
                                    self.delete_message(self.prompt_msg_id)
                                    continue

                                elif action in ["manual", "ignore", "stop"]:
                                    self.is_active = False
                                    kb = {"inline_keyboard": [[{"text": f"✅ Выбрано: {action.upper()}", "callback_data": "noop"}]]}
                                    self.update_keyboard(self.main_msg_id, kb)
                                    callback(action)
                                    return

                            # --- ОБРАБОТКА ВВОДА ТЕКСТА ---
                            elif "message" in update and "text" in update["message"]:
                                text = update["message"]["text"]
                                user_msg_id = update["message"]["message_id"]

                                if self.tg_state == "WAITING_TEXT":
                                    self.delete_message(user_msg_id) 

                                    if self.prompt_msg_id:
                                        self.delete_message(self.prompt_msg_id)

                                    parsed = self.parse_titans(text)
                                    if 3 <= len(parsed) <= 5:
                                        self.temp_pack = parsed
                                        self.tg_state = "CONFIRMING"
                                        names = ", ".join([TITAN_RU[t] for t in parsed])
                                        txt = f"🎯 Распознан состав:\n{names}\n\nВсе верно?"
                                        kb = {
                                            "inline_keyboard": [
                                                [{"text": "✅ Утвердить пак", "callback_data": "confirm_pack"}],
                                                [{"text": "🔄 Написать другой", "callback_data": "retry_pack"}]
                                            ]
                                        }
                                        self.prompt_msg_id = self.send_message(txt, kb)
                                    else:
                                        txt = f"⚠️ Найдено титанов: {len(parsed)} (нужно от 3 до 5).\nРаспознано: {', '.join([TITAN_RU[t] for t in parsed]) if parsed else 'никого'}\n\nНапишите еще раз (например: гип, сиг, нов, орм, май):"
                                        self.prompt_msg_id = self.send_message(txt)

                except Exception:
                    pass
                time.sleep(1)

        threading.Thread(target=poll, daemon=True).start()

    def stop(self):
        self.is_active = False