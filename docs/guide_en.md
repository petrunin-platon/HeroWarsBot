# Comprehensive User Guide for Hero Wars RPA Bot v1.0

Hello! Welcome to the automation system for Hero Wars.

Let's make one thing clear right away: this bot is not just a dumb program that mindlessly clicks on the screen. It is your personal smart assistant (RPA agent). It can "see" the game screen, evaluate your titans' health, collect statistics, and make tactical decisions directly while clearing the Dungeon.

Let's break down step-by-step how to set everything up so farming becomes easy, safe, and yields maximum resources.

---

## Section 1. How to Connect Your Phone and PC

The bot controls the game via a special screen mirroring program (scrcpy). To let the bot take control, you need to configure your phone once.

* **Enable "USB Debugging":** On your Android phone, go to Settings -> Developer Options and enable "USB Debugging". If the "Developer Options" menu is hidden, tap 7 times on the "Build Number" in the "About Phone" section.
* **Connect the cable:** Connect your phone and PC with a high-quality USB cable. A prompt will appear on your phone asking "Allow USB debugging from this computer?". Check the "Always allow" box and tap "OK".
* **Enter the game:** Open Hero Wars, enter the Dungeon, and stop in the hallway (where the next door is visible).
* **Connect the bot:** In our program window, click the "1. Connect phone" button. A window showing your phone screen will appear on the monitor.

> **THE MOST IMPORTANT RULE:** The bot "looks" at the game exactly the same way you do — with its digital eyes. The game broadcast window must always be visible on the monitor! It cannot be minimized, overlapped by a browser, or hidden off-screen. If the window is blocked, the bot will stop and wait for you to restore its vision.

> **Night farming:** If you want to leave the bot running overnight without burning out your phone screen, use the "🌙 Sleep" button in the Control Panel. The phone display will turn off (go black), but the game itself will continue running inside, and the bot will still see everything!

---

## Section 2. Session Goals (Control Panel)

You can tell the bot: "Dig until you collect the guild quota, then go rest". Go to the "Rules Master" tab and select a goal:

* By Titanite amount (e.g., stop at 150).
* By Rooms amount (e.g., clear exactly 10 doors).
* By Floors (clear 2 floors).
* By Time (farm for exactly 30 minutes).

If the limits are set, return to the Main tab and click "2. Start farming". The bot will automatically adjust the window size, assemble the necessary team, and rush into battle.

---

## Section 3. Rules Master (Teaching the Bot to Think)

There are 4 types of rooms in the Dungeon: Earth, Water, Fire, and Mix. You can configure the logic for each element individually.

**1. Base Pack (Default Team)**
This is your main titan team for a specific room. For example, in the Water room, you place Hyperion, Sigurd, Nova, Mairi, and Tidus. If everything goes well, the bot will always use this composition.

**2. Creating Intercepts (+ Condition)**
The bot can change the composition on the fly if the situation heats up. Let's look at some examples:

* **Example 1 (Rescue):** Your tank Sigurd often takes heavy damage. Create a rule: *«If Sigurd's health is below 35%, change the pack to a team with a healer (e.g., Iyari)»*.
* **Example 2 (Tactics):** You hate it when an enemy Araji appears in the room (he burns your entire team). Create a rule: *«If Araji is among the enemies, deploy my strongest anti-pack»*.
* **Example 3 (Manual Control):** If a super-hard battle is coming up, choose the action "Stop bot (Soft Pause)" in the rule. The bot will reach this room, ping you, and say: "I won't go any further, clear it manually".

**3. Advanced Tactics (New Bot Features)**
We've taught the bot not only to heal but also to prevent fatal mistakes.

* **Example 4 (Forbid Entry / Skip):** Your Sigurd has 10% health left. If he enters a Mix room, he will die. Create a rule in the Mix room: *«If Sigurd's health is below 20%, Forbid room entry (Skip)»*. Now the bot will see the Mix room door, realize Sigurd can't go there, and will pick a different door!
* **What if there's only one door? (Blacklist):** If there is no other choice, the bot will still enter the Mix room but will **add Sigurd to the room's Blacklist**. The bot will reject any packs containing Sigurd (even the Default one!) and save his life.
* **Example 5 (Titan Warm-up / Require Fought):** Moloch is low on health and needs to be healed by Sigurd and Iyari in a Mix room. But if Sigurd and Iyari haven't *fought even once* today, they will enter the battle with 0 energy and die before they can charge their ultimates to heal. Check the **"Require titan warm-up"** box and select Sigurd and Iyari. The bot won't let them save Moloch until they have survived at least one safe battle and charged their energy!

> **How the bot reads rules (Smart Priorities):**
> You DO NOT NEED to sort rules manually. The bot thinks for itself:
> 1. First, it checks **Skip/Forbid** rules. All dying titans are added to the "Blacklist".
> 2. Next, it looks for **Rescue** rules (Who has low HP/Energy?). If rescuing requires a blacklisted titan, the bot cancels that pack.
> 3. Then, it looks for **Tactical** rules (Based on enemies).
> 4. If nothing fits, it deploys the **Base pack**.

> **The Angus Feature:** The bot plays Angus better than many humans. It automatically turns on manual battle, waits exactly 1.8 seconds for Angus to deal maximum root damage, and instantly turns off the ultimate! (The "Manual Angus ult control" option, which applies globally across all rooms).

---

## Section 4. Drain Protection (HP Settings and SOS)

The bot will never let your titans die without permission. After every battle, it carefully inspects the health bars. In the "Rules Master" tab, there are two main safety settings:

* **HP Panic Threshold (e.g., 40%):** This is the absolute minimum. If any of your titans drop below 40% health after a battle, the bot sounds the alarm.
* **HP Loss Delta (e.g., 30%):** This protects against sudden burst damage. If a titan enters a battle with 100% HP and leaves with 60% — they lost 40% (this is the delta). If you allowed a maximum loss of 30% per battle, the bot will stop the game, even if there is still plenty of health left.

**SOS System (Rescue Menu):**
If Panic, Delta, a titan death occurs, or **the bot has no working rules left** (all packs are forbidden due to dying titans), the bot pauses the game and shows you a window:
* **🎮 Manual control:** The bot retreats, resets the battle, and you clear the room yourself.
* **🔄 Rollback battle:** The bot cancels the battle, and you can select a different pack for a retry.
* **➡️ Ignore:** You tell the bot: "Everything is fine, I allow these losses, proceed to the next room".
* 🚨 **Assemble new pack:** If the bot couldn't find a safe team before entering a room, it will ask you to assemble a new composition right in this window. The bot will remember this pack as a new rule and immediately rush into battle!

---

## Section 5. Telegram Notifications

You can go drink tea or take a walk while the bot is farming. If your titans are near death, the bot will send a screenshot and control buttons directly to your Telegram!

* **Step 1:** Find the official **@BotFather** bot in Telegram. Send it the `/newbot` command, choose a name, and copy the long `Token`.
* **Step 2:** Find the **@getmyid_bot** bot. Click Start and copy your number sequence `Your user ID`.
* **Step 3:** Return to the chat with your new bot from Step 1 and be sure to click the **"START"** button.
* **Step 4:** In our program, open the "Rules Master" and click **"⚙️ Telegram Setup"**. Paste the Token and Chat ID, click "Apply", and "Save profile".

---

## Section 6. Analytics and Learning

The bot records every battle in an invisible log: who fought whom, and how much HP was left.

Go to the "Analytics" tab and click "Run log analysis". The bot will calculate your Winrate (percentage of successful battles) for each composition. If it finds a team that consistently defeats specific enemies with an 80%+ success rate, it calls this a **"Golden Rule"**.
Click "Apply" — and the bot will permanently remember this winning tactic!

---

## Section 7. Statistics and Synchronization

The bot maintains beautiful statistics: draws charts, counts titanite, rooms, and potions.

**Important about Game Time:**
A new day in Hero Wars starts at 05:00 AM. Be sure to specify your "Day reset hour" in the Rules Master so the bot doesn't confuse evening and night battles.

**Smart Synchronization:**
Imagine you played manually on your phone in the morning and collected 60 titanite. In the evening, you launched the bot. How does the bot understand the big picture?
It's very simple! Go to the "Statistics" tab, select the day (Today), and enter the **TOTAL titanite number** you see in the game (e.g., 150) in the field. The bot is smart: it knows it farmed 90 itself, subtracts that from 150, and neatly adds your 60 manual points to the stats, calculating the rooms and potions for them. Error protection is built-in — the bot won't let you enter a number lower than what it farmed itself.

---

## Section 8. PC Hotkeys

* **Ctrl + Q (Soft pause):** The bot won't abandon the game mid-battle. It will carefully finish off the enemies, claim the reward, stop before the next door, and wait.
* **Ctrl + Shift + Q (Emergency STOP):** Instantly turns off the bot. Use this if something goes wrong.