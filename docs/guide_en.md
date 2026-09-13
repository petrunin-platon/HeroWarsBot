# Hero Wars RPA Bot v1.0 Complete User Manual

Hey there! Welcome to the automation system for Hero Wars. 

Let’s get one thing straight right off the bat: this bot isn't just some dumb auto-clicker mindlessly tapping your screen. It’s your personal smart assistant (an RPA agent). It can actually "see" the game screen, evaluate your titans' health, track statistics, and make tactical decisions on the fly during Dungeon runs.

Let’s walk through the setup step by step to make your farming smooth, safe, and packed with resources.



## Section 1. Connecting Your Phone to Your PC

The bot controls the game via a dedicated screen mirroring tool (scrcpy). To let the bot take the wheel, you only need to configure your phone once.

* **Enable "USB Debugging":** On your Android phone, go to Settings -> Developer Options and turn on "USB Debugging". If the "Developer Options" menu is hidden, tap "Build Number" 7 times under "About Phone".
* **Plug in the cable:** Connect your phone to your PC using a reliable USB cable. A prompt will pop up on your phone asking "Allow USB debugging from this computer?". Check "Always allow" and tap "OK".
* **Launch the game:** Open Hero Wars, enter the Dungeon, and stop in the hallway (where you can see the next door).
* **Connect the bot:** In our program window, click the "1. Connect Phone" button. A window mirroring your phone screen will appear on your monitor.

**➡ THE GOLDEN RULE:** The bot "looks" at the game just like you do—with its own digital eyes. The game mirror window must remain visible on your monitor at all times! Never minimize it, cover it with a browser, or hide it off-screen. If the window is obstructed, the bot will pause and wait until you restore its field of view.

**➡ Overnight Farming:** Want to leave the bot running overnight without burning in your phone's screen? Use the "Screen OFF" button in the Control Panel. Your phone's display will turn off (go pitch black), but the game will keep running in the background, and the bot will still see everything!



## Section 2. Session Targets (Control Panel)

You can tell the bot: "Keep digging until you hit the guild quota, then take a break." Head over to the "Rule Master" tab and pick a target:

* By Titanite amount (e.g., stop at 150).
* By number of Rooms (e.g., clear exactly 10 doors).
* By Floors (clear 2 floors).
* By Time (farm for exactly 30 minutes).

Once your limits are set, head back to the Main tab and click "2. Start Farming". The bot will resize the window automatically, assemble the required lineup, and charge into battle.



## Section 3. Rule Master (Teaching the Bot to Think)

The Dungeon features 4 room types: Earth, Water, Fire, and Mixed. To make sure the bot doesn't just click mindlessly, but makes decisions like an experienced player, you can customize the logic for each element individually.

**1. Base Lineup (Default Team)**

This is your core squad that the bot runs by default. All slots start empty.

* Click the blue button for the desired element (e.g., "Water").
* In the window that opens, select between 3 and 5 titans (players usually set a full squad of five—e.g., Hyperion, Sigurd, Tidus, Nova, Mairi).
* Click the green "Apply" button.

As long as everything goes according to plan and health remains high, the bot will always run this lineup.

**2. Rule Builder (Overrides)**

Sometimes situations spiral out of control. That’s what rules are for (the **"+ Condition"** button). The bot evaluates the battlefield before each door and can take over, swapping out the lineup. You can name the rule whatever you like—it doesn't affect anything, it's just there to keep you organized.

Conditions fall into three categories:

* **By Health (HP):** For instance, your tank Sigurd is taking heavy hits. You create a rule: *“If Sigurd's HP drops below 35%, pick a lineup with a healer (Iyari)”*. Golden rule: configure healing overrides **specifically for elements where that titan can actually heal!** (For Sigurd, that’s Water or Mixed rooms).

* **By Energy:** Crucial for "speed-clear" teams. For example, your Angus wipes enemies in an Earth room with a single ult in two seconds flat before they can even hit back. But to do that, he needs to enter the fight fully charged. Make a rule: *“If Angus's Energy is below 97% — pause the bot”*. The bot will reach the Earth room, alert you, and stop so you can manually enter a Mixed room and charge Angus's energy.

* **By Enemies (Anti-Teams):** Despise facing enemy Araji because he melts your squad? Set up a rule: "If the enemy team has Araji, deploy my custom anti-lineup."

**3. Smart Options (Skip and Warm-up)**

Inside the Rule Builder, there are toggles designed to save you from stupid wipes:

* **Block Room Entry (Skip):** Picture this: Sigurd is down to 10% HP, and a Mixed room is up next. If the bot steps in, Sigurd is dead meat. Check the "Skip" (Block Entry) box for HP below 20%. The bot will spot low-health Sigurd, bypass the Mixed room, and look for a Water room to patch him up.

* **Require Titan Warm-up:** An absolute game-changer for starting a new game day! In the morning, all titans sit at 100% HP but 0% energy. Throwing them straight into a tough Mixed room will get them wiped before they can even pop an ult. The "Warm-up" toggle tells the bot: "This titan must first fight at least one easy battle in their native element to build up energy before they are allowed into Mixed rooms."

**4. Priorities: Who Takes Precedence?**

What should the bot do if Sigurd is low on HP, but a terrifying Araji is waiting on the enemy side?
The bot reads through your rule list **strictly from top to bottom**, just like a human.

Click the grey **"View/Delete Active Rules"** button. That’s where you can inspect the bot’s logic. It prioritizes things in this order:

1. **"Skip" rules first** (keep bruised titans out of combat).
2. **HP & Energy emergency rescues next**.
3. **Anti-teams (countering specific enemies)**.
4. **Base Lineup dead last**, if no threats are detected.

In this window, you can rearrange rules using the Up/Down arrows. Whichever rule sits higher on the list gets executed first. If you change the order, make sure to click the green **"Save Changes"** button there.

**5. IMPORTANT: How the Bot Handles Memory**

The bot’s interface is designed to run lightning-fast and avoid wearing out your hard drive with constant disk writes.

1. Whenever you configure rules, always click the **purple "Save Profile" button** on the main screen.
2. When you hit "Start Farming", the bot loads all rules into RAM **once**.
3. If the bot is already farming and you tweak and save rules on the fly—the bot will NOT see them! You must hit "Stop" and restart "Farming" so the bot reloads the new settings.

**➡ "Restore / Reset" Button:** If a sudden power outage or system crash corrupts your configuration file, just click this red button BEFORE starting a farm run. The bot will automatically retrieve a backup copy of your settings and fix everything.

**6. Global Angus Control**

The **"Manual Angus Ult Control (Global)"** toggle isn't on the main screen by accident. The bot plays Angus better than most humans: it waits precisely 1.8 seconds so the roots deal maximum damage, then immediately cancels the ult. If this toggle is on, the bot will use this trick **across absolutely every battle** Angus fights in, regardless of whether it's a default lineup or a conditional override. But before enabling this option, make sure your Angus is at 100% energy!

**Developer Pro-Tip: Why does the bot pause so often, and how do you make it 100% autonomous?**

A common scenario during initial runs: titan health looks completely fine visually, yet the bot constantly pauses the game, pops up an SOS window, and asks what to do. It feels like it's panicking over nothing.

The culprit is the **"HP Loss Delta"** setting (found on the main screen).
Delta protects against massive, burst damage taken in a single battle. For example, if your Delta is set to 30%, and a titan enters a room with 100% health but leaves with 69% (a 31% loss), the bot halts immediately—even though 69% is still a safe green bar and nowhere near critical.

**How to stop dealing with SOS popups and achieve full autonomy:**

1. **Loosen the Delta (the easy way):** If the constant interruptions annoy you and you trust your titans, simply bump the "HP Loss Delta" up to 100% (effectively disabling it). In this mode, the bot stops calculating damage spikes per fight and relies *only* on the "Panic HP Threshold"—meaning it will only stop when health drops to a genuinely critical low (e.g., below 25%).

2. **Turn pauses into lessons:** Every SOS prompt is an opportunity to hop into the Rule Master and set up a condition so the bot knows how to avoid that damage next time.

3. **Leverage Analytics (The Path to Full Autonomy):** This is the magic sauce! After every session, make sure to visit the "Analytics" tab and run log analysis. The bot will detect patterns on its own and propose **"Golden Rules"** (proven winning lineups). Just click "Implement".

**The Takeaway:** The more "Golden Rules" and manual conditions you feed the bot, the fewer questions it will ask. Over time, it will build the perfect knowledge base tailored to your titan levels and become **100% autonomous**!



## Section 4. Wipe Protection (HP and SOS Settings)

The bot will never wipe your titans without asking first. After every battle, it closely monitors their health bars. In the "Rule Master" tab, you'll find two core safety settings:

* **Panic HP Threshold (e.g., 40%):** This is the absolute floor. If any of your titans drop below 40% health after a fight, the bot sounds the alarm.
* **HP Loss Delta (e.g., 30%):** Protection against burst damage. If a titan enters battle at 100% HP and exits at 60%—they lost 40% (that’s your delta). If you set the maximum allowed loss to 30% per battle, the bot pauses the game, even if there’s plenty of health left.

**The SOS System (Rescue Menu):**
If Panic, Delta, or a titan death triggers, the bot pauses the game and displays a window with three choices:
* **Manual Clear:** The bot retreats, resets the fight, and lets you clear the room by hand.
* **Rollback Battle:** The bot cancels the battle so you can pick a different lineup and try again.
* **Ignore:** You tell the bot: "All good, I'm fine with these losses—move on to the next room."



## Section 5. Telegram Notifications

Feel free to grab some tea or head out while the bot farms. If your titans find themselves near death, the bot will beam a screenshot and control buttons straight to your Telegram!

* **Step 1:** Look up the official **@BotFather** bot on Telegram. Send it the `/newbot` command, name your bot, and copy the long `Token`.
* **Step 2:** Look up the **@getmyid_bot** bot. Tap Start and copy the numbers from `Your user ID`.
* **Step 3:** Return to your chat with the new bot created in Step 1 and make sure to hit the **"START"** button.
* **Step 4:** In our software, open "Rule Master" and click **"Configure Telegram"**. Paste the Token and Chat ID, then hit "Apply" and "Save Profile".



## Section 6. Analytics and Learning

The bot logs every single battle to an invisible journal: who fought whom, and how much HP remained.

Head over to the "Analytics" tab and click "Run Log Analysis". The bot will calculate your Win Rate (percentage of successful battles) for each lineup. If it identifies a squad that consistently defeats specific enemies with an 80%+ win rate, it flags it as a **"Golden Rule"**.
Click "Implement"—and the bot will lock that winning tactic into memory for good!



## Section 7. Stats and Syncing

The bot tracks comprehensive statistics: plots clean graphs, tracks Titanite, room counts, and potions.

**Important Note on In-Game Time:** 
A new day in Hero Wars resets at 05:00 AM. Be sure to configure your "Daily Reset Hour" in the Rule Master so the bot doesn't mix up evening and late-night battles.

**Smart Sync:**
Imagine you played manually on your phone this morning and collected 60 Titanite. In the evening, you launch the bot. How does it see the full picture?
Very simple! Go to the "Stats" tab, select the date (Today), and enter the **TOTAL Titanite number** you see in the game (e.g., 150). The bot is smart: knowing it farmed 90 points on its own, it subtracts that from 150 and cleanly adds your 60 manual points to the stats, calculating the rooms and potions for them. Built-in error protection will even prevent you from entering a number lower than what the bot farmed itself.



## Section 8. PC Hotkeys

* **Ctrl + Q (Soft Pause):** The bot won't abandon the game mid-battle. It will cleanly finish off enemies, claim the rewards, halt right before the next door, and wait for you.
* **Ctrl + Shift + Q (Emergency STOP):** Instantly terminates the bot. Use this if anything goes wrong.