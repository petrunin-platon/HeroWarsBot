# telegram_agent.py
import requests
import time
import threading
import json
import re
import os
from i18n import get_text

BASE_TITANS = [
    "hyperion", "sigurd", "tidus", "nova", "mairi", "orm",
    "angus", "avalon", "eden", "silva", "verdok", "pallant",
    "araji", "ignis", "acheron", "vulcan", "moloch", "alecto",
    "rigel", "iyari", "lumira", "solaris", "amon",
    "mor", "tenebris", "brustar", "umbra", "keros"
]

class TelegramAgent:
    def __init__(self, token, chat_id, lang=None):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}"
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
        
        # 🛡 Убиваем старые клики при каждом запуске агента!
        self._clear_history()

    def _clear_history(self):
        """Прочитывает и стирает все зависшие нажатия кнопок на сервере Telegram"""
        try:
            resp = requests.get(f"{self.base_url}/getUpdates?timeout=1").json()
            if resp.get("ok") and resp["result"]:
                self.last_update_id = resp["result"][-1]["update_id"]
                # Отправляем подтверждение, что мы всё прочитали
                requests.get(f"{self.base_url}/getUpdates?offset={self.last_update_id + 1}&timeout=1")
        except Exception:
            pass

    def delete_message(self, msg_id):
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
        payload = {"chat_id": self.chat_id, "message_id": msg_id}
        if reply_markup is not None:
            payload["reply_markup"] = json.dumps(reply_markup)
        requests.post(f"{self.base_url}/editMessageReplyMarkup", json=payload)

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

    def send_sos(self, image_path, text, is_manual=False, can_rollback=True):
        if not self.token or not self.chat_id: return None
        url = f"{self.base_url}/sendPhoto"
        
        if is_manual or not can_rollback:
            btn_middle = {"text": get_text(self.lang, "tg_bot_stop"), "callback_data": "stop"}
        else:
            btn_middle = {"text": get_text(self.lang, "tg_bot_rollback"), "callback_data": "rollback"}

        reply_markup = {
            "inline_keyboard": [
                [{"text": get_text(self.lang, "tg_bot_manual"), "callback_data": "manual"}, btn_middle],
                [{"text": get_text(self.lang, "tg_bot_ignore"), "callback_data": "ignore"}]
            ]
        }

        data = {"chat_id": self.chat_id, "caption": text, "reply_markup": json.dumps(reply_markup)}
        try:
            with open(image_path, "rb") as f:
                result = requests.post(url, data=data, files={"photo": f}).json()
                if result.get("ok"):
                    self.main_msg_id = result["result"]["message_id"]
                    return self.main_msg_id
        except Exception as e: print(f"[TELEGRAM] Сбой отправки: {e}")
        return None

    def send_test_result(self, image_path, text):
        if not self.token or not self.chat_id: return None
        url = f"{self.base_url}/sendPhoto"
        
        reply_markup = {
            "inline_keyboard": [
                [{"text": get_text(self.lang, "test_btn_confirm"), "callback_data": "test_confirm"}],
                [{"text": get_text(self.lang, "test_btn_rollback"), "callback_data": "test_retry"}]
            ]
        }
        
        data = {"chat_id": self.chat_id, "caption": text, "reply_markup": json.dumps(reply_markup)}
        try:
            with open(image_path, "rb") as f:
                result = requests.post(url, data=data, files={"photo": f}).json()
                if result.get("ok"):
                    self.main_msg_id = result["result"]["message_id"]
                    return self.main_msg_id
        except Exception: pass
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

                            if "callback_query" in update:
                                cq = update["callback_query"]
                                action = cq["data"]
                                requests.post(f"{self.base_url}/answerCallbackQuery", json={"callback_query_id": cq["id"]})

                                if action == "rollback":
                                    self.tg_state = "WAITING_TEXT"
                                    self.update_keyboard(self.main_msg_id, {"inline_keyboard": []})
                                    txt = get_text(self.lang, "tg_bot_wait_text")
                                    self.prompt_msg_id = self.send_message(txt)
                                    continue
                                    
                                elif action == "test_retry":
                                    self.tg_state = "WAITING_TEXT"
                                    self.update_keyboard(self.main_msg_id, {"inline_keyboard": []})
                                    txt = get_text(self.lang, "tg_bot_wait_text")
                                    self.prompt_msg_id = self.send_message(txt)
                                    continue

                                elif action == "test_confirm":
                                    self.is_active = False
                                    btn_text = get_text(self.lang, "tg_bot_selected").format(action="CONFIRM")
                                    self.update_keyboard(self.main_msg_id, {"inline_keyboard": [[{"text": btn_text, "callback_data": "noop"}]]})
                                    callback("CONFIRM")
                                    return

                                elif action == "confirm_pack":
                                    self.tg_state = "IDLE"
                                    self.delete_message(self.prompt_msg_id)
                                    kb = {"inline_keyboard": [[{"text": get_text(self.lang, "tg_bot_rollback_ok"), "callback_data": "noop"}]]}
                                    self.update_keyboard(self.main_msg_id, kb)
                                    self.is_active = False
                                    callback(f"rb_custom:{','.join(self.temp_pack)}")
                                    return

                                elif action == "retry_pack":
                                    self.tg_state = "WAITING_TEXT"
                                    self.delete_message(self.prompt_msg_id)
                                    txt = get_text(self.lang, "tg_bot_wait_text")
                                    self.prompt_msg_id = self.send_message(txt)
                                    continue

                                elif action in ["manual", "ignore", "stop"]:
                                    self.is_active = False
                                    btn_text = get_text(self.lang, "tg_bot_selected").format(action=action.upper())
                                    kb = {"inline_keyboard": [[{"text": btn_text, "callback_data": "noop"}]]}
                                    self.update_keyboard(self.main_msg_id, kb)
                                    callback(action)
                                    return

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
                                        names = ", ".join([get_text(self.lang, f"titan_{t}").capitalize() for t in parsed])
                                        txt = get_text(self.lang, "tg_bot_pack_confirm").format(names=names)
                                        kb = {
                                            "inline_keyboard": [
                                                [{"text": get_text(self.lang, "tg_bot_btn_confirm"), "callback_data": "confirm_pack"}],
                                                [{"text": get_text(self.lang, "tg_bot_btn_retry"), "callback_data": "retry_pack"}]
                                            ]
                                        }
                                        self.prompt_msg_id = self.send_message(txt, kb)
                                    else:
                                        names_str = ", ".join([get_text(self.lang, f"titan_{t}").capitalize() for t in parsed]) if parsed else get_text(self.lang, "tg_bot_none")
                                        txt = get_text(self.lang, "tg_bot_err_count").format(count=len(parsed), names=names_str)
                                        self.prompt_msg_id = self.send_message(txt)

                except Exception: pass
                time.sleep(1)

        threading.Thread(target=poll, daemon=True).start()

    def stop(self):
        self.is_active = False