# Vollständiges Benutzerhandbuch: Hero Wars RPA Bot v1.0

Hallo! Willkommen beim Automatisierungssystem für das Spiel Hero Wars. 

Lass uns gleich eines klarstellen: Dieser Bot ist kein stumpfes Tool, das einfach nur planlos auf den Bildschirm klickt. Er ist dein persönlicher, intelligenter Assistent (RPA-Agent). Er kann das Spielgeschehen auf dem Bildschirm „sehen“, die HP deiner Titanen analysieren, Statistiken erfassen und während der Dungeon-Säuberung taktische Entscheidungen in Echtzeit treffen.

Gehen wir Schritt für Schritt durch, wie du alles einrichtest, damit das Farmen mühelos, sicher und maximal ertragreich wird.



## Abschnitt 1. Smartphone und PC miteinander verbinden

Der Bot steuert das Spiel über ein spezielles Bildschirmübertragungsprogramm (scrcpy). Damit der Bot die Steuerung übernehmen kann, musst du dein Smartphone einmalig einrichten.

* **Aktiviere „USB-Debugging“:** Gehe auf deinem Android-Gerät zu Einstellungen -> Entwickleroptionen und aktiviere den Punkt „USB-Debugging“. Falls das Menü „Entwickleroptionen“ ausgeblendet ist, tippe 7-mal auf die „Build-Nummer“ im Bereich „Über das Telefon“.
* **Kabel anschließen:** Verbinde Smartphone und PC mit einem hochwertigen USB-Kabel. Auf dem Smartphone erscheint die Abfrage „USB-Debugging von diesem Computer immer zulassen?“. Setze dort das Häkchen und tippe auf „OK“.
* **Spiel starten:** Öffne Hero Wars, gehe in den Dungeon und bleibe im Korridor stehen (dort, wo die nächste Tür zu sehen ist).
* **Bot verbinden:** Klicke im Fenster unseres Programms auf die Schaltfläche „1. Telefon verbinden“. Auf deinem Monitor erscheint nun ein Fenster mit dem Bildschirm deines Smartphones.

**➡ DIE WICHTIGSTE REGEL:** Der Bot „sieht“ das Spiel genau wie du – mit seinen digitalen Augen. Das Übertragungsfenster des Spiels muss auf dem Monitor immer vollständig sichtbar sein! Es darf weder minimiert, noch von einem Browser überdeckt oder über den Bildschirmrand hinausgeschoben werden. Wird das Fenster verdeckt, stoppt der Bot und wartet, bis du ihm wieder freie Sicht verschaffst.

**➡ Farmen über Nacht:** Wenn du den Bot über Nacht laufen lassen möchtest, ohne das Display deines Smartphones einzubrennen, nutze die Taste „Bildschirm AUS“ im Control Panel. Das Smartphone-Display schaltet sich ab (wird schwarz), das Spiel läuft im Hintergrund jedoch weiter und der Bot sieht weiterhin alles!



## Abschnitt 2. Sitzungsziele (Control Panel)

Du kannst dem Bot genaue Anweisungen geben wie: „Grabe, bis du das Gilden-Soll erreicht hast, und mach dann Feierabend.“ Gehe dazu in den Reiter „Regel-Master“ und wähle dein Ziel:

* Nach Titanit-Menge (z. B. bei 150 stoppen).
* Nach Raumanzahl (z. B. genau 10 Türen abschließen).
* Nach Etagen (z. B. 2 Etagen durchqueren).
* Nach Zeit (z. B. genau 30 Minuten farmen).

Sobald die Limits festgelegt sind, gehst du zurück zum Hauptreiter und klickst auf „2. Farmen starten“. Der Bot passt die Fenstergröße automatisch an, stellt das benötigte Team zusammen und zieht in den Kampf.



## Abschnitt 3. Regel-Master (Dem Bot das Denken beibringen)

Im Dungeon gibt es 4 Raumtypen: Erde, Wasser, Feuer und Gemischt. Damit der Bot nicht einfach nur Klicks ausführt, sondern wie ein erfahrener Spieler agiert, kannst du die Logik für jedes Element individuell anpassen.

**1. Basis-Team (Standard-Aufstellung)**

Das ist dein Hauptteam, das der Bot standardmäßig einsetzt. Zu Beginn sind alle Slots leer.

* Klicke auf den blauen Button des gewünschten Elements (z. B. „Wasser“).
* Wähle im geöffneten Fenster 3 bis 5 Titanen aus (meistens wird ein volles 5er-Team gewählt – z. B. Hyperion, Sigurd, Tethys, Nova, Mairi).
* Klicke auf den grünen Button „Übernehmen“.

Solange im Spiel alles nach Plan läuft und die Lebenspunkte im grünen Bereich sind, wird der Bot immer mit dieser Aufstellung kämpfen.

**2. Regel-Baukasten (Bedingungen & Eingriffe)**

Manchmal geraten Situationen außer Kontrolle. Genau dafür sind Regeln da (Button **„+ Bedingung“**). Der Bot analysiert die Lage vor jeder Tür und kann bei Bedarf die Kontrolle übernehmen und das Team wechseln. Den Namen der Regel denkst du dir selbst aus – er dient rein deiner Orientierung.

Bedingungen unterteilen sich in drei Typen:

* **Nach Lebenspunkten (HP):** Dein Tank Sigurd verliert beispielsweise oft viel Leben. Du erstellst die Regel: *„Wenn Sigurds HP unter 35 % fallen, wähle ein Team mit Heiler (Iyari)“*. Wichtigste Grundregel: Erstelle den Rettungsbefehl **genau in dem Element, in dem dieser Titan geheilt werden kann!** (Für Sigurd ist das ein Wasser- oder Gemischter Raum).

* **Nach Energie:** Extrem wichtig für „schnelle“ Teams. Wenn dein Angus beispielsweise in einem Erd-Raum mit einer einzigen Ulti alle Gegner in Sekunden vernichtet, darf er vorher keinen Schaden nehmen. Dafür muss er den Kampf aber voll aufgeladen betreten. Erstelle die Regel: *„Wenn Angus' Energie unter 97 % liegt – Bot anhalten“*. Der Bot erreicht den Erd-Raum, gibt einen Signalton ab und pausiert, damit du manuell in einen Gemischten Raum gehen und Energie für Angus aufladen kannst.

* **Nach Gegnern (Anti-Teams / Konter-Packs):** Wenn du den gegnerischen Araji absolut nicht ausstehen kannst (weil er das ganze Team wegbrennt), erstelle eine Regel: „Wenn unter den Gegnern Araji ist, setze mein spezielles Anti-Team ein“.

**3. Smarte Optionen (Skip & Einspielen)**

Im Regel-Baukasten gibt es Optionen, die deine Titanen vor unnötigen Toden bewahren:

* **Raum betreten verbieten (Skip):** Angenommen, Sigurd hat nur noch 10 % HP und vor dem Bot liegt ein Gemischter Raum. Geht er dort hinein, stirbt Sigurd. Du setzt das Häkchen bei „Skip“ (Betreten verbieten), wenn die HP unter 20 % liegen. Der Bot erkennt den angeschlagenen Sigurd, ignoriert den Gemischten Raum und sucht stattdessen nach einem Wasser-Raum, um ihn hochzuheilen.

* **Titanen-Einspielen verlangen:** Ein unverzichtbares Feature für den Start in einen neuen Spieltag! Morgens haben alle Titanen 100 % HP, aber 0 % Energie. Schickt man sie direkt in einen schweren Gemischten Raum, fallen sie oft um, bevor sie ihre Ulti zünden können. Das Häkchen bei „Einspielen“ weist den Bot an: „Dieser Titan muss zuerst mindestens einen leichten Kampf in seinem Heimatelement bestreiten, um Energie aufzubauen – erst danach darf er in Gemischten Räumen eingesetzt werden.“

**4. Prioritäten: Wer hat Vorrang?**

Was soll der Bot tun, wenn Sigurd niedrige HP hat, auf der Gegenseite aber gleichzeitig der gefürchtete Araji steht?
Der Bot verarbeitet deine Regelliste **strikt von oben nach unten**, genau wie ein menschlicher Spieler.

Klicke auf den grauen Button **„Aktive Regeln anzeigen/löschen“**. Dort siehst du die genaue Entscheidungslogik des Bots. Er strukturiert sie folgendermaßen:

1. **Zuerst „Skip“-Regeln** (angeschlagene Titanen vor Kämpfen schützen).
2. **Danach Rettungsregeln nach HP und Energie**.
3. **Anschließend Konter-Teams (nach Gegnern)**.
4. **Ganz am Ende das Basis-Team**, falls keine Gefahren vorliegen.

In diesem Fenster kannst du die Regeln mit den Pfeiltasten (Hoch/Runter) verschieben. Je weiter oben eine Regel steht, desto höher ist ihre Priorität für den Bot. Wenn du die Reihenfolge geändert hast, klicke unbedingt auf den grünen Button **„Änderungen speichern“**.

**5. WICHTIG: Wie der Bot Einstellungen speichert**

Das Interface des Bots ist darauf ausgelegt, blitzschnell zu arbeiten und deine Festplatte nicht mit permanenten Schreibvorgängen zu belasten.

1. Wenn du Regeln anpasst, klicke auf dem Hauptbildschirm immer auf den **lila Button „Profil speichern“**.
2. Sobald du auf „Farmen“ klickst, liest der Bot alle Regeln **einmalig** aus und lädt sie direkt in den Arbeitsspeicher.
3. Wenn der Bot bereits farmt und du währenddessen Regeln änderst und speicherst, bekommt der Bot das NICHT mit! Du musst auf „Stopp“ klicken und das „Farmen“ neu starten, damit der Bot die neuen Einstellungen einliest.

**➡ Button „Wiederherstellen / Reset“:** Sollte die Einstellungsdatei nach einem plötzlichen Stromausfall oder Systemabsturz beschädigt sein, klicke einfach VOR dem Start des Farmens auf diesen roten Button. Der Bot stellt automatisch das Backup deiner Einstellungen wieder her.

**6. Globale Angus-Kontrolle**

Der Schalter **„Manuelle Kontrolle der Angus-Ulti (Global)“** befindet sich aus gutem Grund auf dem Hauptbildschirm. Der Bot spielt Angus präziser als viele Menschen: Er wartet exakt 1,8 Sekunden ab, damit die Wurzeln maximalen Schaden anrichten, und bricht die Ulti danach sofort manuell ab. Ist das Häkchen aktiv, wendet der Bot diesen Trick **in absolut allen Kämpfen** an, an denen Angus beteiligt ist – egal ob im Basis-Team oder bei einem Regeleingriff. Vergewissere dich vor dem Aktivieren dieser Option jedoch, dass Angus' Energie zu 100 % aufgeladen ist.

**Entwickler-Geheimtipp: Warum pausiert der Bot so oft und wie wird er zu 100 % autonom?**

Ein häufiges Phänomen bei den ersten Durchläufen: Die Titanen haben optisch noch massig Leben, aber der Bot pausiert ständig das Spiel, öffnet ein SOS-Fenster und fragt, was zu tun ist. Es wirkt, als würde er grundlos in Panik geraten.

Das liegt an der Einstellung **„HP-Verlust-Delta“** (auf dem Hauptbildschirm).
Das Delta ist ein Schutzmechanismus gegen plötzlichen, massiven Burst-Schaden innerhalb eines einzelnen Kampfes. Steht das Delta beispielsweise bei 30 % und dein Titan betritt den Raum mit 100 % HP, verlässt ihn aber mit 69 % (31 % Verlust), stoppt der Bot sofort – selbst wenn 69 % noch tiefgrün und absolut unkritisch sind.

**Wie du SOS-Meldungen reduzierst und den Bot vollkommen selbstständig machst:**

1. **Delta lockern (für Bequeme):** Wenn dich häufige Unterbrechungen stören und du deinen Titanen vertraust, erhöhe das „HP-Verlust-Delta“ einfach auf bis zu 100 % (was es praktisch deaktiviert). In diesem Fall ignoriert der Bot den Schaden pro Einzelkampf und orientiert sich *ausschließlich* an der „HP-Panikschwelle“ – er stoppt also erst dann, wenn die HP wirklich ein kritisches Minimum erreichen (z. B. unter 25 %).

2. **Pausen als Erfahrung nutzen:** Jedes SOS-Fenster ist eine Gelegenheit, in den Regel-Master zu gehen und eine Bedingung zu erstellen, damit der Bot diesen Schaden beim nächsten Mal eigenständig verhindert.

3. **Analytics nutzen (Der Weg zur vollen Autonomie):** Das ist der wichtigste Punkt! Gehe nach jeder Session in den Reiter „Analytik“ und starte die Log-Analyse. Der Bot erkennt Muster und schlägt dir **„Goldene Regeln“** vor (bewährte Sieger-Teams). Klicke einfach auf „Implementieren“.

**Fazit:** Je mehr solcher „Goldenen Regeln“ und manuellen Bedingungen der Bot lernt, desto seltener muss er nachfragen. Mit der Zeit baut er eine perfekte Wissensdatenbank auf, die exakt auf den Entwicklungsstand deiner Titanen zugeschnitten ist – und wird **zu 100 % autonom**!



## Abschnitt 4. Schutz vor Niederlagen (HP- & SOS-Einstellungen)

Der Bot wird deine Titanen niemals leichtfertig opfern. Nach jedem Gefecht überprüft er akribisch die Lebensbalken. Im Reiter „Regel-Master“ findest du zwei zentrale Sicherheitseinstellungen:

* **HP-Panikschwelle (z. B. 40 %):** Das absolute Minimum. Hat ein beliebiger Titan nach dem Kampf weniger als 40 % Leben, schlägt der Bot Alarm.
* **HP-Verlust-Delta (z. B. 30 %):** Schutz vor Burst-Schaden. Betritt ein Titan den Kampf mit 100 % HP und beendet ihn mit 60 %, hat er 40 % verloren (das Delta). Wenn du maximal 30 % Verlust pro Kampf erlaubt hast, pausiert der Bot das Spiel – selbst wenn die Rest-HP noch hoch sind.

**Das SOS-System (Rettungsmenü):**
Wird die Panikschwelle oder das Delta überschritten oder stirbt ein Titan, pausiert der Bot das Spiel und bietet dir drei Optionen:
* **Manuell abschließen:** Der Bot zieht sich zurück, setzt den Kampf zurück und du spielst den Raum selbst zu Ende.
* **Kampf zurücksetzen:** Der Bot bricht den Kampf ab, sodass du ein anderes Team für einen neuen Versuch wählen kannst.
* **Ignorieren:** Du signalisierst dem Bot: „Alles in Ordnung, dieser Verlust ist eingeplant – weiter zum nächsten Raum.“



## Abschnitt 5. Telegram-Benachrichtigungen

Du kannst dir entspannt einen Kaffee kochen oder spazieren gehen, während der Bot farmt. Droht deinen Titanen das Aus, schickt dir der Bot einen Screenshot samt Steuerungs-Buttons direkt auf dein Telegram!

* **Schritt 1:** Suche in Telegram nach dem offiziellen Bot **@BotFather**. Sende ihm den Befehl `/newbot`, gib deinem Bot einen Namen und kopiere den langen `Token`.
* **Schritt 2:** Suche nach dem Bot **@getmyid_bot**. Klicke auf Start und kopiere deine Zahlenfolge bei `Your user ID`.
* **Schritt 3:** Gehe zurück in den Chat mit deinem neu erstellten Bot aus Schritt 1 und klicke zwingend auf **„START“**.
* **Schritt 4:** Öffne in unserem Programm den Reiter „Regel-Master“ und klicke auf **„Telegram einrichten“**. Füge Token und Chat-ID ein, klicke auf „Übernehmen“ und anschließend auf „Profil speichern“.



## Abschnitt 6. Analytik und Selbstlernen

Der Bot führt im Hintergrund ein detailliertes Tagebuch über jeden einzelnen Kampf: Wer gegen wen angetreten ist und wie viele HP übrig blieben.

Gehe in den Reiter „Analytik“ und klicke auf „Log-Analyse starten“. Der Bot berechnet deine Winrate (Siegquote) für jede Team-Zusammenstellung. Findet er eine Aufstellung, die bestimmte Gegner konstant mit einer Wahrscheinlichkeit von 80 %+ besiegt, deklariert er dies als **„Goldene Regel“**.
Klicke auf „Implementieren“ – und der Bot speichert diese Siegertaktik dauerhaft ab!



## Abschnitt 7. Statistiken und Synchronisation

Der Bot liefert übersichtliche Statistiken: Er zeichnet Diagramme, zählt Titanit, abgeschlossene Räume und Tränke.

**Wichtig zur Spielzeit:** 
Ein neuer Spieltag beginnt in Hero Wars standardmäßig um 05:00 Uhr morgens. Trage deine „Reset-Stunde“ unbedingt im Regel-Master ein, damit der Bot Abend- und Nachtkämpfe nicht verwechselt.

**Smarte Synchronisation:**
Angenommen, du hast morgens manuell auf dem Smartphone gespielt und 60 Titanit gesammelt. Am Abend startest du den Bot. Wie behält der Bot das Gesamtbild im Auge?
Ganz einfach! Gehe in den Reiter „Statistik“, wähle den Tag (Heute) und trage in das Feld die **GESAMT-Titanit-Menge** ein, die dir im Spiel angezeigt wird (z. B. 150). Der Bot denkt mit: Er weiß, dass er selbst 90 erfarmt hat, zieht diese von 150 ab und bucht deine 60 manuellen Punkte sauber in die Statistik ein – inklusive der entsprechenden Räume und Tränke. Ein Fehleingabeschutz ist integriert: Der Bot verhindert, dass du einen niedrigeren Wert eingibst, als er selbst bereits erspielt hat.



## Abschnitt 8. PC-Hotkeys

* **Strg + Q (Sanfte Pause):** Der Bot bricht das Spiel nicht mitten im Gefecht ab. Er beendet den aktuellen Kampf sauber, holt die Belohnung ab, bleibt vor der nächsten Tür stehen und wartet auf dich.
* **Strg + Umschalt + Q (Not-Aus):** Beendet den Bot sofort und ohne Verzögerung. Nutze diese Tastenkombination, wenn etwas völlig schiefläuft.