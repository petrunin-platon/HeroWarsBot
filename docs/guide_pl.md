# Pełny podręcznik użytkownika Hero Wars RPA Bot v1.0

Cześć! Witaj w systemie automatyzacji dla gry Hero Wars. 

Ustalmy jedno na starcie: ten bot to nie jest zwykły, głupi program, który bezmyślnie klika w ekran. To Twój osobisty, inteligentny asystent (agent RPA). Potrafi on „widzieć” ekran gry, oceniać stan zdrowia Twoich tytanów, zbierać statystyki i podejmować decyzje taktyczne bezpośrednio podczas czyszczenia Lochów.

Przejdźmy krok po kroku przez cały proces konfiguracji, aby farmienie stało się łatwe, bezpieczne i przynosiło maksimum zasobów.



## Rozdział 1. Jak zaprzyjaźnić telefon z komputerem

Bot steruje grą za pomocą specjalnego programu do klonowania ekranu (scrcpy). Aby bot mógł przejąć kontrolę, musisz jednorazowo skonfigurować swój telefon.

* **Włącz „Debugowanie USB”:** Na telefonie z systemem Android wejdź w Ustawienia -> Opcje programistyczne i włącz opcję „Debugowanie USB”. Jeśli menu „Opcje programistyczne” jest ukryte, kliknij 7 razy w „Numer kompilacji” w sekcji „O telefonie”.
* **Podłącz kabel:** Połącz telefon z PC dobrym kablem USB. Na telefonie pojawi się komunikat „Zezwalać na debugowanie USB z tego komputera?”. Zaznacz „Zawsze zezwalaj” i kliknij „OK”.
* **Wejdź do gry:** Otwórz Hero Wars, wejdź do Lochów i zatrzymaj się w korytarzu (tam, gzie widać kolejne drzwi).
* **Połącz bota:** W oknie naszego programu kliknij przycisk „1. Podłącz telefon”. Na monitorze pojawi się okno z ekranem Twojego telefonu.

**➡ NAJWAŻNIEJSZA ZASADA:** Bot „patrzy” na grę dokładnie tak samo jak Ty — swoimi cyfrowymi oczami. Okno transmisji gry musi być zawsze widoczne na monitorze! Nie wolno go minimalizować, zasłaniać przeglądarką ani chować poza krawędź ekranu. Jeśli okno zostanie zasłonięte, bot zatrzyma się i będzie czekać, aż przywrócisz mu widok.

**➡ Nocne farmienie:** Jeśli chcesz zostawić bota na noc i nie wypalić ekranu telefonu, użyj przycisku „WYŁĄCZ ekran” w Panelu sterowania. Wyświetlacz telefonu zgaśnie (stanie się czarny), ale sama gra będzie działać w tle, a bot nadal będzie wszystko widzieć!



## Rozdział 2. Cele sesji (Panel sterowania)

Możesz powiedzieć botowi: „Kop, dopóki nie zbierzesz normy gildii, a potem idź odpocząć”. Przejdź do zakładki „Kreator reguł” i wybierz cel:

* Według ilości Tytanitu (na przykład: zatrzymaj się na 150).
* Według liczby Pokoi (na przykład: przejdź dokładnie 10 drzwi).
* Według Pięter (przejdź 2 piętra).
* Według Czasu (farmuj dokładnie 30 minut).

Gdy limity zostaną ustawione, wróć do zakładki Głównej i kliknij „2. Rozpocznij farmowanie”. Bot sam dostosuje rozmiar okna, dobierze odpowiedni skład i ruszy do walki.



## Rozdział 3. Kreator Reguł (Uczymy bota myśleć)

W Lochach są 4 typy pokoi: Ziemia, Woda, Ogień oraz Mieszany. Aby bot nie klikał bezmyślnie, lecz podejmował decyzje jak doświadczony gracz, możesz skonfigurować logikę dla każdego żywiołu indywidualnie.

**1. Podstawowy skład (Domyślny team)**

To Twój główny skład, którego bot będzie używał domyślnie. Na początku wszystkie sloty są puste.

* Kliknij niebieski przycisk wybranego żywiołu (na przykład „Woda”).
* W otwartym oknie wybierz od 3 do 5 tytanów (zazwyczaj wybiera się pełną piątkę — na przykład Hyperion, Sigurd, Tethys, Nova, Mairi).
* Kliknij zielony przycisk „Zastosuj”.

Jeśli w grze wszystko idzie zgodnie z planem, a zdrowie jest w normie, bot zawsze będzie grał tym składem.

**2. Kreator reguł (Przejęcia)**

Czasami sytuacja wymyka się spod kontroli. Do tego służą reguły (przycisk **„+ Warunek”**). Bot ocenia sytuację przed każdymi drzwiami i może przejąć kontrolę, zmieniając skład. Nazwę reguły wymyślasz sam — nie wpływa ona na działanie, pomaga Ci jedynie się zorientować.

Warunki dzielą się na trzy typy:

* **Według zdrowia (HP):** Na przykład Twój tank Sigurd często traci dużo życia. Tworzysz regułę: *„Jeśli HP Sigurda spadnie poniżej 35%, wybierz skład z healerem (Iyari)”*. Główna zasada: twórz regułę przejęcia na leczenie **dokładnie w tym żywiole, w którym dany tytan może się leczyć!** (Dla Sigurda jest to pokój Wody lub Mieszany).

* **Według energii:** Kluczowa sprawa dla „szybkich” składów. Na przykład Twój Angus zabia wrogów w pokoju Ziemi jednym ultem w kilka sekund, nie pozwalając im zadać ciosu. Aby to jednak zrobił, musi wejść do walki naładowany. Stwórz regułę: *„Jeśli energia Angusa spadnie poniżej 97% — zatrzymaj bota”*. Bot dojdzie do pokoju Ziemi, wyda sygnał dźwiękowy i zatrzyma się, abyś mógł wejść do pokoju Mieszanego ręcznie i naładować energię Angusa.

* **Według wrogów (Anty-teamu):** Jeśli nie znosisz wrogiego Araji (ponieważ pali Twój team), ustaw regułę: *„Jeśli wśród wrogów jest Araji, wystaw mój specjalny anty-team”*.

**3. Inteligentne opcje (Skip i Rozgrzewka)**

W Kreatorze reguł znajdziesz opcje, które ratują przed głupimi porażkami:

* **Zabroń wejścia do pokoju (Skip):** Wyobraź sobie, że Sigurdowi zostało 10% HP, a przed botem jest pokój Mieszany. Jeśli tam wejdzie — Sigurd zginie. Zaznaczasz opcję „Skip” (Zabroń wejścia) przy HP poniżej 20%. Bot zobaczy poobijanego Sigurda, zignoruje pokój Mieszany i pójdzie szukać pokoju Wody, aby go uleczyć.

* **Wymagaj rozgrzewki tytanów:** Unikalna funkcja na start nowego dnia gry! Rano wszyscy tytani mają 100% HP, ale 0% energii. Jeśli wpuścisz ich od razu do ciężkiego pokoju Mieszanego, po prostu padną, zanim zdążą użyć ulta. Opcja „Rozgrzewka” mówi botowi: „Ten tytan musi najpierw stoczyć przynajmniej jedną łatwą walkę w swoim rodzimym żywiole, aby naładować manę, i dopiero wtedy można go wystawić w pokojach Mieszanych”.

**4. Priorytety: Kto ma pierwszeństwo?**

Co ma zrobić bot, jeśli Sigurd ma mało HP, a jednocześnie wśród wrogów stoi groźny Araji?
Bot czyta listę Twoich reguł **ściśle od góry do dołu**, zupełnie jak człowiek.

Kliknij szary przycisk **„Pokaż/Usuń aktywne reguły”**. Zobaczysz tam logikę bota. Grupuje on wszystko w następujący sposób:

1. **Najpierw reguły „Skip”** (nie wpuszczaj poobijanych tytanów do walki).
2. **Następnie ratowanie według HP i Energii**.
3. **Następnie anty-teamu (według wrogów)**.
4. **Na samym końcu — Podstawowy skład**, jeśli nie ma żadnych zagrożeń.

W tym oknie możesz przesuwać reguły strzałkami (W górę / W dół). Bot posłucha w pierwszej kolejności tej reguły, która znajduje się wyżej na liście. Jeśli zmienisz kolejność, koniecznie kliknij tam zielony przycisk **„Zapisz zmiany”**.

**5. WAŻNE: Jak bot zapisuje pamięć**

Interfejs bota został zaprojektowany tak, aby nie przeciążać Twojego dysku twardego ciągłym nadpisywaniem i działać błyskawicznie.

1. Gdy konfigurujesz reguły, pamiętaj, aby zawsze kliknąć **fioletowy przycisk „Zapisz profil”** na ekranie głównym.
2. Gdy klikasz przycisk „Farmuj”, bot **jednorazowo** odczytuje wszystkie reguły i ładuje je do pamięci RAM.
3. Jeśli bot już farmuje, a Ty w locie zmienisz reguły i je zapiszesz — bot ich NIE zauważy! Musisz kliknąć „Stop” i ponownie uruchomić „Farmuj”, aby bot na nowo wczytał świeże ustawienia.

**➡ Przycisk „Przywróć / Reset”:** Jeśli przy nagłym braku prądu lub awarii systemu plik ustawień ulegnie uszkodzeniu, po prostu kliknij ten czerwony przycisk PRZED uruchomieniem farmienia. Bot automatycznie przywróci kopię zapasową ustawień i wszystko naprawi.

**6. Globalna kontrola Angusa**

Przełącznik **„Ręczna kontrola ulta Angusa (Globalnie)”** nie bez powodu znalazł się na ekranie głównym. Bot potrafi grać Angusem lepiej niż wielu ludzi: sam odczekuje dokładnie 1,8 sekundy, aby korzenie zadały maksymalne obrażenia, i natychmiast wyłącza ulta. Jeśli ta opcja jest włączona, bot będzie stosował tę sztuczkę **we wszystkich walkach**, w których bierze udział Angus, niezależnie od tego, czy jest to podstawowy skład, czy przejęcie warunkowe. Przed włączeniem tej opcji upewnij się jednak, że Angus ma 100% energii przed użyciem tego ustawienia.

**Sekret od dewelopera: Dlaczego bot często pauzuje grę i jak uczynić go w 100% autonomicznym?**

Częsta sytuacja przy primeiros uruchomieniach: zdrowie tytanów wizualnie jest jeszcze na wysokim poziomie, ale bot ciągle pauzuje grę, wyrzuca okno SOS i pyta, co robić. Może się wydawać, że panikuje bez powodu.

Wszystko sprowadza się do ustawienia **„Delta strat HP”** (znajdziesz je na ekranie głównym).
Delta to ochrona przed gwałtownymi, nagłymi obrażeniami podczas jednej konkretnej walki. Na przykład masz ustawioną Deltę na 30%. Jeśli Twój tytan wejdzie do pokoju ze 100% zdrowia, a wyjdzie z 69% (stracił 31%), bot natychmiast się zatrzyma — nawet jeśli 69% to wciąż zielony pasek i sytuacja zupełnie niezagrażająca życiu.

**Jak przestać rozpraszać się oknami SOS i sprawić, by bot stał się samodzielny:**

1. **Zwiększ tolerancję „Delty” (dla leniwych):** Jeśli denerwują Cię częste zatrzymania, a jesteś pewien swoich tytanów, po prostu zwiększ „Deltę strat HP” nawet do 100% (co w praktyce ją wyłączy). W takim przypadku bot przestanie liczyć obrażenia na pojedynczą walkę i będzie kierować się *wyłącznie* „Progiem paniki HP” — czyli zatrzyma się tylko wtedy, gdy zdrowie naprawdę spadnie do krytycznego minimum (na przykład poniżej 25%).

2. **Zamień zatrzymania w doświadczenie:** Każde okno SOS to okazja, by wejść do Kreatora reguł i stworzyć warunek, dzięki któremu następnym razem bot będzie wiedział, jak uniknąć tych obrażeń.

3. **Korzystaj z Analityki (Droga do pełnej autonomii):** To najważniejsze! Po każdej sesji gry koniecznie wejdź w zakładkę „Analityka” i uruchom analizę logów. Bot sam znajdzie zależności i zaproponuje Ci **„Złote reguły”** (sprawdzone, zwycięskie składy). Po prostu kliknij „Wdróż”.

**Podsumowanie:** Im więcej takich „Złotych reguł” i ręcznych warunków przyswoi bot, tym rzadziej będzie zadawał pytania. Z czasem zbuduje idealną bazę wiedzy dostosowaną do poziomu Twoich tytanów i stanie się **w 100% autonomiczny**!



## Rozdział 4. Ochrona przed porażką (Ustawienia HP i SOS)

Bot nigdy nie doprowadzi do śmierci Twoich tytanów bez Twojej zgody. Po każdej walce uważnie analizuje paski zdrowia. W zakładce „Kreator reguł” znajdują się dwa główne ustawienia bezpieczeństwa:

* **Próg paniki HP (na przykład 40%):** To absolutne minimum. Jeśli po walce u któregokolwiek z Twoich tytanów zostanie mniej niż 40% zdrowia, bot wszczyna alarm.
* **Delta strat HP (na przykład 30%):** To ochrona przed nagłymi obrażeniami. Jeśli tytan wszedł do walki mając 100% HP, a wyszedł mając 60% — stracił 40% (to właśnie jest delta). Jeśli zezwoliłeś na utratę maksymalnie 30% na walkę, bot zatrzyma grę, nawet jeśli zdrowia pozostało jeszcze sporo.

**System SOS (Menu ratunkowe):**
Jeśli aktywuje się Panika, Delta lub ktoś zginie, bot pauzuje grę i wyświetla okno z trzema opcjami do wyboru:
* **Przejdź ręcznie:** Bot wycofa się, zresetuje walkę, a Ty przejdziesz pokój sam.
* **Cofnij walkę:** Bot anuluje walkę, a Ty będziesz mógł wybrać inny skład do kolejnej próby.
* **Ignoruj:** Mówisz botowi: „Wszystko w porządku, zgadzam się na te straty, idziemy do następnego pokoju”.



## Rozdział 5. Powiadomienia na Telegramie

Możesz pójść napić się herbaty lub pójść na spacer, podczas gdy bot farmuje. Jeśli tytani będą bliscy śmierci, bot wyśle zrzut ekranu i przyciski sterowania prosto na Twój Telegram!

* **Krok 1:** Znajdź na Telegramie oficjalnego bota **@BotFather**. Wyślij mu komendę `/newbot`, wymyśl nazwę i skopiuj długi `Token`.
* **Krok 2:** Znajdź bota **@getmyid_bot**. Kliknij Start i skopiuj swoje cyfry `Your user ID`.
* **Krok 3:** Wróć do czatu ze swoim nowym botem z Kroku 1 i koniecznie kliknij przycisk **„START”**.
* **Krok 4:** W naszym programie otwórz „Kreator reguł” i kliknij **„Skonfiguruj Telegram”**. Wklej Token oraz Chat ID, kliknij „Zastosuj” i „Zapisz profil”.



## Rozdział 6. Analityka i Nauka

Bot zapisuje w niewidocznym dzienniku każdą Twoją walkę: kto z kim walczył i ile HP pozostało.

Wejdź w zakładkę „Analityka” i kliknij „Uruchom analizę logów”. Bot obliczy Twój Winrate (procent udanych walk) dla każdego składu. Jeśli znajdzie zespół, który stabilnie pokonuje konkretnych wrogów z szansą ponad 80%, nazwie to **„Złotą regułą”**.
Kliknij „Wdróż” — a bot na zawsze zapamięta tę wygrywającą taktykę!



## Rozdział 7. Statystyki i Synchronizacja

Bot prowadzi czytelne statystyki: rysuje wykresy, liczy tytanit, pokoje i mikstury. 

**Ważne informacje o czasie gry:** 
Nowy dzień w grze Hero Wars rozpoczyna się o godzinie 05:00 rano. Pamiętaj, aby ustawić swoją „Godzinę resetu dnia” w Kreatorze reguł, by bot nie mylił walk wieczornych z nocnymi.

**Inteligentna synchronizacja:**
Wyobraź sobie, że rano grałeś ręcznie na telefonie i zebrałeś 60 tytanitu. Wieczorem uruchamiasz bota. Jak bot ma zrozumieć ogólny obraz sytuacji?
To bardzo proste! Wejdź w zakładkę „Statystyki”, wybierz dzień (Dzisiaj) i w polu wpisz **ŁĄCZNĄ liczbę tytanitu**, którą widzisz w grze (na przykład 150). Bot jest sprytny: wie, że sam zdobył 90, odejmie je od 150 i dokładnie doda Twoje 60 punktów zdobytych ręcznie do statystyk, przeliczając na ich podstawie pokoje i mikstury. Zabezpieczenie przed błędami jest wbudowane — bot nie pozwoli Ci wpisać liczby mniejszej niż ta, którą sam zdobył.



## Rozdział 8. Skróty klawiszowe PC

* **Ctrl + Q (Łagodna pauza):** Bot nie przerwie gry w środku walki. Spokojnie dobije wrogów, odbierze nagrodę, zatrzyma się przed kolejnymi drzwiami i będzie czekać.
* **Ctrl + Shift + Q (Awaryjny STOP):** Błyskawicznie wyłącza bota. Użyj, jeśli coś pójdzie nie tak.