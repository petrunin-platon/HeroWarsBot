# Complete User Guide for Hero Wars RPA Bot v1.0

Hello! Welcome to the automation system for the Hero Wars game. 

Let's get one thing straight: this bot is not just a dumb program that randomly clicks on the screen. It is your personal smart assistant (RPA agent). It can "see" the game screen, evaluate the health of your titans, collect statistics, and make tactical decisions right during the Dungeon run.

Let's break down step by step how to set everything up so that farming becomes easy, safe, and brings maximum resources.

---

## Section 1. How to connect your phone and computer

The bot controls the game through a special screen mirroring program (scrcpy). For the bot to take control, you need to configure your phone once.

* **Enable "USB Debugging":** On your Android phone, go to Settings -> Developer Options and turn on "USB debugging". If the Developer menu is hidden, tap 7 times on the "Build number" in the "About phone" section.
* **Connect the cable:** Connect your phone and PC with a good USB cable. A prompt "Allow USB debugging from this computer?" will appear on your phone. Check the "Always allow" box and click "OK".
* **Enter the game:** Open Hero Wars, enter the Dungeon and stop in the hallway (where you can see the next door).
* **Connect the bot:** In our program window, click the "1. Connect phone" button. A window with your phone's screen broadcast will appear on the monitor.

> **MOST IMPORTANT RULE:** The bot "looks" at the game exactly like you do — with its own digital eyes. The game broadcast window must always be visible on the monitor! It cannot be minimized, overlapped by a browser, or hidden behind the edge of the screen. If the window is covered, the bot will stop and wait until you restore its view.

> **Night Farming:** If you want to leave the bot running overnight without burning out your phone's screen, use the "🌙 Sleep Screen" button in the Control Panel. The phone display will turn off (go black), but the game will continue to run inside, and the bot will still see everything!

---

## Section 2. Session Goals (Dashboard)

You can tell the bot: "Dig until you reach the guild quota, and then take a rest". Go to the "Rules Master" tab and choose a goal:

* By Titanite amount (e.g., stop at 150).
* By Rooms count (e.g., clear exactly 10 doors).
* By Floors (clear 2 floors).
* By Time (farm for exactly 30 minutes).

If limits are set, return to the Main tab and click "2. Start farming". The bot will calibrate the window size, assemble the necessary team, and rush into battle.

---

## Section 3. Rules Master (Teaching the bot to think)

There are 4 types of rooms in the Dungeon: Earth, Water, Fire, and Mix. You can customize the logic for each element individually.

**1. Default Pack**
This is your main titan team for a specific room. For example, in the Water room, you place Hyperion, Sigurd, Nova, Mairi, and Tidus. If everything goes well, the bot will always use this composition.

**2. Creating Intercepts (+ Condition)**
The bot can change the team on the fly if the situation heats up. Let's look at some examples:

* **Example 1 (Rescue):** Your tank Sigurd often takes heavy damage. Create a rule: *"If Sigurd's health is below 35%, change the pack to a team with a healer (e.g., Iyari)"*.
* **Example 2 (Tactics):** You hate it when an enemy Araji appears in the room (he burns the whole team). Create a rule: *"If there is Araji among the enemies, deploy my strongest counter-pack"*.
* **Example 3 (Manual Control):** If a super difficult battle is coming up, choose the action "Stop bot (Soft Pause)" in the rule. The bot will reach this room, beep, and say: "I won't go further, complete it manually."

> **The Angus Trick:** The bot can play Angus better than many humans. It turns on auto-battle itself, waits exactly 1.8 seconds for Angus to deal maximum damage with his roots, and instantly turns off the ultimate! (Option "Manual Angus ult control").

---

## Section 4. Drain Protection (HP Settings and SOS)

The bot will never drain your titans without asking. After every battle, it carefully examines the health bars. In the "Rules Master" tab, there are two main safety settings:

* **HP Panic Threshold (e.g., 40%):** This is the absolute minimum. If after a battle any of your titans has less than 40% health left, the bot sounds the alarm.
* **HP Loss Delta (e.g., 30%):** This protects against sudden damage spikes. If a titan entered the battle with 100% HP and came out with 60% — they lost 40% (this is the delta). If you allowed a maximum loss of 30% per battle, the bot will stop the game, even if there is still plenty of health left.

**SOS System (Rescue Menu):**
If Panic, Delta, or Death occurs, the bot puts the game on pause and shows you a window with three options:
* **🎮 Manual control:** The bot will retreat, resetting the battle, and you will clear the room yourself.
* **🔄 Rollback battle:** The bot will cancel the battle, and you can choose another pack for a retry.
* **➡️ Ignore:** You tell the bot: "Everything is fine, I allow these losses, let's go to the next room."

---

## Section 5. Telegram Notifications

You can go drink tea or take a walk while the bot farms. If the titans are near death, the bot will send a screenshot and control buttons directly to your Telegram!

* **Step 1:** Find the official **@BotFather** in Telegram. Send him the `/newbot` command, come up with a name, and copy the long `Token`.
* **Step 2:** Find the **@getmyid_bot**. Click Start and copy your numbers `Your user ID`.
* **Step 3:** Return to the dialogue with your new bot from Step 1 and make sure to click the **"START"** button.
* **Step 4:** In our program, open the "Rules Master" tab and click **"⚙️ Telegram Setup"**. Paste the Token and Chat ID, click "Apply", and "Save profile".

---

## Section 6. Analytics and Machine Learning

The bot records every single battle in an invisible log: who fought whom, and how much HP was left.

Go to the "Analytics" tab and click "Run log analysis". The bot will calculate your Winrate (percentage of successful battles) for each composition. If it finds a team that consistently defeats specific enemies with an 80%+ chance, it will call it a **"Golden Rule"**.
Click "Apply" — and the bot will remember this winning tactic forever!

---

## Section 7. Statistics and Synchronization

The bot keeps beautiful statistics: it draws charts, counts titanite, rooms, and potions.

**Important regarding Game Time:** 
A new day in the Hero Wars game starts at 05:00 AM. Be sure to specify your local "Day reset hour" in the Rules Master so the bot doesn't mix up evening and night battles.

**Smart Synchronization:**
Imagine you played manually on your phone in the morning and collected 60 titanite. In the evening, you launched the bot. How does the bot understand the big picture?
Very simple! Go to the "Statistics" tab, select the day (Today), and enter the **TOTAL titanite number** you see in the game (e.g., 150) in the field. The bot is smart: it knows it farmed 90 itself, will subtract that from 150, and neatly add your 60 manual points to the statistics, calculating the rooms and potions for them. Error protection is built-in — the bot won't let you enter a number smaller than what it farmed itself.

---

## Section 8. PC Hotkeys

* **Ctrl + Q (Soft Pause):** The bot will not abandon the game mid-battle. It will carefully finish off the enemies, collect the reward, stop before the next door, and wait.
* **Ctrl + Shift + Q (Emergency STOP):** Instantly turns off the bot. Use this if something goes horribly wrong.