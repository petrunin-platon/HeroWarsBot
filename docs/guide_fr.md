# Guide de l'utilisateur complet de Hero Wars RPA Bot v1.0

Salut ! Bienvenue dans le système d'automatisation pour le jeu Hero Wars. 

Soyons clairs dès le départ : ce bot n'est pas juste un programme stupide qui clique bêtement sur l'écran. C'est ton propre assistant intelligent (un agent RPA). Il est capable de « voir » l'écran du jeu, d'évaluer la santé de tes titans, de collecter des statistiques et de prendre des décisions tactiques en plein combat pendant que tu nettoies le Donjon.

Voyons étape par étape comment tout configurer pour que le farm devienne simple, sécurisé et te rapporte un maximum de ressources.



## Section 1. Comment connecter ton téléphone à ton PC

Le bot contrôle le jeu via un logiciel spécial de partage d'écran (scrcpy). Pour que le bot puisse prendre le relais, tu devez configurer ton téléphone une bonne fois pour toutes.

* **Active le « Débogage USB » :** Sur ton téléphone Android, va dans Paramètres -> Options pour les développeurs et active l'option "Débogage USB". Si le menu "Options pour les développeurs" est masqué, tapote 7 fois sur le "Numéro de build" dans la section "À propos du téléphone".
* **Branche le câble :** Connecte ton téléphone au PC avec un bon câble USB. Un message « Autoriser le débogage depuis cet ordinateur ? » va s'afficher sur ton téléphone. Coche "Toujours autoriser" et appuie sur « OK ».
* **Lance le jeu :** Ouvre Hero Wars, va dans le Donjon et arrête-toi dans le couloir (là où on voit la porte suivante).
* **Connecte le bot :** Dans la fenêtre de notre programme, clique sur le bouton « 1. Connecter le téléphone ». Une fenêtre affichant l'écran de ton téléphone va s'ouvrir sur ton moniteur.

**➡ LA RÈGLE LA PLUS IMPORTANTE :** Le bot « regarde » le jeu exactement comme toi, avec ses propres yeux numériques. La fenêtre de diffusion du jeu doit TOUJOURS être visible sur ton écran ! Tu ne dois pas la réduire, la masquer avec un navigateur ou la cacher sur le bord de l'écran. Si la fenêtre est masquée, le bot va s'arrêter et attendre que tu lui redonnes de la visibilité.

**➡ Farm de nuit :** Si tu veux laisser le bot tourner toute la nuit sans brûler l'écran de ton téléphone, utilise le bouton « Éteindre Écran » dans le Panneau de configuration. L'écran de ton téléphone s'éteindra (deviendra noir), mais le jeu continuera de tourner en arrière-plan et le bot verra tout !



## Section 2. Objectifs de session (Panneau de configuration)

Tu peux dire au bot : "Ferme jusqu'à atteindre le quota de la guilde, puis va te reposer". Va dans l'onglet « Gestionnaire de règles » et choisis ton objectif :

* Par quantité de Titanite (par exemple, s'arrêter à 150).
* Par nombre de Salles (par exemple, passer exactement 10 portes).
* Par Étages (passer 2 étages).
* Par Temps (farmer pendant exactement 30 minutes).

Une fois les limites fixées, retourne sur l'onglet Principal et clique sur « 2. Lancer le farm ». Le bot va ajuster lui-même la taille de la fenêtre, composer la bonne équipe et foncer au combat.



## Section 3. Le Gestionnaire de Règles (Apprendre au bot à réfléchir)

Dans le Donjon, il y a 4 types de salles : Terre, Eau, Feu et Mixte. Pour que le bot ne se contente pas de cliquer bêtement, mais prenne des décisions comme un joueur pro, tu peux configurer la logique pour chaque élément individuellement.

**1. La compo de base (Équipe par défaut)**

C'est ta composition principale, celle que le bot utilisera par défaut. Au départ, tous les emplacements sont vides.

* Clique sur le bouton bleu de l'élément souhaité (par exemple, « Eau »).
* Dans la fenêtre qui s'ouvre, choisis de 3 à 5 titans (généralement, on met l'équipe complète de 5 — par exemple, Hypérion, Sigurd, Tidus, Nova, Mairi).
* Clique sur le bouton vert « Appliquer ».

Si tout se passe comme prévu en jeu et que les PV sont bons, le bot jouera toujours avec cette compo.

**2. Le Créateur de règles (Interceptions)**

Parfois, la situation dérape. C'est là qu'interviennent les règles (bouton **« + Condition »**). Le bot évalue la situation avant chaque porte et peut reprendre le contrôle en changeant de compo. Tu choisis toi-même le nom de la règle — cela n'influence rien, c'est juste pour t'aider à t'y retrouver.

Les conditions se divisent en trois types :

* **Par santé (PV) :** Par exemple, ton tank Sigurd perd souvent trop de vie. Tu crées la règle suivante : *« Si les PV de Sigurd tombent sous 35%, choisir la compo avec le healer (Iyari) »*. La règle d'or : crée une interception de soin **uniquement dans l'élément où ce titan peut se soigner !** (Pour Sigurd, c'est la salle d'Eau ou Mixte).

* **Par énergie :** Crucial pour les compos rapides. Par exemple, ton Angus décime les ennemis dans la salle de Terre avec un seul ulti en quelques secondes, sans leur laisser le temps de riposter. Mais pour cela, il doit commencer le combat chargé. Crée la règle suivante : *« Si l'Énergie d'Angus est inférieure à 97% — arrêter le bot »*. Le bot s'arrêtera devant la salle de Terre avec un signal sonore pour que tu puisses faire la salle Mixte à la main afin de charger l'énergie d'Angus.

* **Par ennemis (Anti-compos) :** Si tu détestes l'Araji adverse (qui décime ton équipe), configure la règle suivante : « Si Araji fait partie des ennemis, déployer mon anti-compo spéciale ».

**3. Options intelligentes (Skip et Rodage)**

Dans le Créateur de règles, il y a des cases à cocher qui évitent les morts stupides :

* **Interdire l'accès à la salle (Skip) :** Imagine qu'il reste 10% de PV à Sigurd et que le bot fait face à une salle Mixte. S'il y va, Sigurd meurt. Tu coches l'option « Skip » (Interdire l'accès) pour des PV inférieurs à 20%. Le bot verra que Sigurd est mal en point, ignorera la salle Mixte et cherchera une salle d'Eau pour le soigner.

* **Exiger le rodage des titans :** Une fonctionnalité unique pour le début d'une nouvelle journée de jeu ! Le matin, tous tes titans ont 100% de PV mais 0% d'énergie. Si tu les envoies direct dans une salle Mixte difficile, ils vont mourir sans avoir le temps de lancer leur ulti. Cocher « Rodage » dit au bot : "Ce titan doit d'abord faire au moins un combat facile dans son élément d'origine pour accumuler du mana, et ensuite seulement il pourra être placé dans les salles Mixtes".

**4. Priorités : Qui passe en premier ?**

Que doit faire le bot si Sigurd a peu de PV, mais qu'un terrible Araji se dresse en face ?
Le bot lit ta liste de règles **strictement de haut en bas**, comme un être humain.

Clique sur le bouton gris **« Voir/Supprimer les règles actives »**. Tu y verras la logique du bot. Il regroupe tout ainsi :

1. **D'abord les règles "Skip"** (ne pas envoyer les titans blessés au combat).
2. **Ensuite, le sauvetage par PV et Énergie**.
3. **Ensuite, les anti-compos (selon les ennemis)**.
4. **Tout à la fin — la Compo de base**, s'il n'y a aucune menace.

Dans cette fenêtre, tu peux déplacer les règles avec les flèches (Haut/Bas). Le bot écoutera en priorité la règle la plus haute de la liste. Si tu modifies l'ordre, n'oublie pas de cliquer sur le bouton vert **« Enregistrer les modifications »**.

**5. IMPORTANT : Comment le bot gère sa mémoire**

L'interface du bot est conçue pour ne pas surcharger ton disque dur avec des réécritures constantes et pour fonctionner à la vitesse de l'éclair.

1. Quand tu configures des règles, n'oublie pas de cliquer sur le **bouton violet « Enregistrer le profil »** sur l'écran principal.
2. Quand tu appuies sur le bouton « Farm », le bot lit toutes les règles **une seule fois** et les charge dans la mémoire vive (RAM).
3. Si le bot est déjà en train de farmer et que tu modifies et sauvegardes les règles à la volée — le bot ne les verra PAS ! Tu dois cliquer sur « Stop » puis relancer le « Farm » pour que le bot charge les nouveaux paramètres.

**➡ Bouton "Restaurer / Réinitialiser" :** Si une coupure de courant soudaine ou un bug système corrompt le fichier de configuration, clique simplement sur ce bouton rouge AVANT de lancer le farm. Le bot récupérera automatiquement une sauvegarde des paramètres et réparera tout.

**6. Contrôle global d'Angus**

L'interrupteur **« Contrôle manuel de l'ulti d'Angus (Global) »** est placé sur l'écran principal pour une bonne raison. Le bot sait jouer Angus mieux que la plupart des humains : il attend lui-même pile 1.8 seconde pour que les racines infligent un maximum de dégâts, puis coupe immédiatement l'ulti. Si cette case est cochée, le bot appliquera cette astuce **dans absolument tous les combats** où Angus participe, que ce soit avec la compo de base ou lors d'une interception sous condition. Mais avant d'activer cette option, assure-toi qu'Angus a son énergie chargée à 100% avant d'utiliser ce paramètre.

**Secret de développeur : Pourquoi le bot se met-il souvent en pause et comment le rendre 100% autonome ?**

Situation classique lors des premiers lancements : la santé des titans semble encore excellente à l'œil nu, mais le bot met constamment le jeu sur pause, affiche une fenêtre SOS et demande quoi faire. On a l'impression qu'il panique pour rien.

Tout réside dans le paramètre **« Delta de perte de PV »** (sur l'écran principal).
Le Delta est une protection contre les dégâts violents et soudains subis lors d'un combat spécifique. Par exemple, si ton Delta est réglé sur 30% : si ton titan entre dans la salle à 100% de santé et en ressort à 69% (il a perdu 31%), le bot s'arrêtera instantanément. Même si 69% reste dans la zone verte et n'est pas du tout critique pour sa survie.

**Comment ne plus être dérangé par les fenêtres SOS et rendre le bot autonome :**

1. **Assouplis le « Delta » (pour les fainéants) :** Si les interceptions fréquentes t'agacent et que tu as confiance en tes titans, augmente simplement le « Delta de perte de PV » jusqu'à 100% (ce qui revient à le désactiver). Dans ce cas, le bot arrêtera de calculer les dégâts par combat et se basera *uniquement* sur le « Seuil de panique PV » — c'est-à-dire qu'il ne s'arrêtera que lorsque la santé tombera réellement à un niveau critique (par exemple, sous les 25%).

2. **Transforme les arrêts en expérience :** Chaque fenêtre SOS est l'occasion d'aller dans le Gestionnaire de règles pour créer une condition, afin que le bot sache comment éviter ces dégâts la prochaine fois.

3. **Utilise l'Analytique (La voie vers l'autonomie totale) :** C'est le plus important ! Après chaque session de jeu, va impérativement dans l'onglet « Analytique » et lance l'analyse des logs. Le bot va détecter lui-même les tendances et te proposer des **« Règles d'Or »** (des compositions d'équipe gagnantes éprouvées). Clique simplement sur « Intégrer ».

**En résumé :** Plus le bot apprendra de « Règles d'Or » et de conditions manuelles, moins il te posera de questions. Avec le temps, il se constituera une base de connaissances idéale adaptée à la puissance de tes titans et deviendra **100% autonome** !



## Section 4. Protection contre le wipe (Paramètres PV et SOS)

Le bot не sacrifiera jamais tes titans sans te demander. Après chaque combat, il examine attentivement les barres de vie. Dans l'onglet "Gestionnaire de règles", il y a deux paramètres de sécurité majeurs :

* **Seuil de panique PV (par exemple, 40%) :** C'est le minimum absolu. Si après un combat, l'un de tes titans a moins de 40% de PV, le bot tire la sonnette d'alarme.
* **Delta de perte de PV (par exemple, 30%) :** C'est une protection contre les dégâts soudains. Si un titan commence le combat à 100% de PV et en ressort à 60%, il a perdu 40% (c'est le delta). Si tu as configuré une perte maximale de 30% par combat, le bot arrêtera le jeu, même s'il reste encore beaucoup de PV.

**Système SOS (Menu de sauvetage) :**
Si la Panique, le Delta se déclenche ou si quelqu'un meurt, le bot met le jeu en pause et t'affiche une fenêtre avec trois options :
* **Faire à la main :** Le bot bat en retraite, réinitialise le combat, et tu fais la salle toi-même.
* **Annuler le combat :** Le bot annule le combat pour que tu puisses choisir une autre compo et réessayer.
* **Ignorer :** Tu dis au bot : « Tout va bien, j'accepte ces pertes, passe à la salle suivante ».



## Section 5. Notifications Telegram

Tu peux aller boire un thé ou te promener pendant que le bot farm. Si tes titans sont sur le point de mourir, le bot t'enverra une capture d'écran et des boutons de contrôle directement sur Telegram !

* **Étape 1 :** Cherche le bot officiel **@BotFather** sur Telegram. Envoie-lui la commande `/newbot`, choisis un nom et copie le long `Token`.
* **Étape 2 :** Cherche le bot **@getmyid_bot**. Appuie sur Start et copie les chiffres de `Your user ID`.
* **Étape 3 :** Retourne dans la discussion avec ton nouveau bot créé à l'Étape 1 et appuie obligatoirement sur le bouton **"DÉMARRER"** (ou "START").
* **Étape 4 :** Dans notre programme, ouvre le « Gestionnaire de règles » et clique sur **« Configurer Telegram »**. Colle le Token et le Chat ID, puis clique sur "Appliquer" et "Enregistrer le profil".



## Section 6. Analytique et Apprentissage

Le bot enregistre chaque combat dans un journal invisible : qui a affronté qui, et combien de PV il restait.

Va dans l'onglet « Analytique » et clique sur « Lancer l'analyse des logs ». Le bot calculera ton Winrate (pourcentage de victoires) pour chaque compo. S'il trouve une équipe qui bat systématiquement des ennemis spécifiques avec un taux de réussite de 80% ou plus, il l'appellera une **« Règle d'Or »**.
Clique sur « Intégrer » — et le bot mémorisera cette tactique gagnante pour toujours !



## Section 7. Statistiques et Synchronisation

Le bot génère de superbes statistiques : il dessine des graphiques, compte la titanite, les salles et les potions.

**Important concernant l'heure du jeu :** 
Une nouvelle journée dans Hero Wars commence à 05h00 du matin. Pense bien à indiquer ton "Heure de réinitialisation du jour" dans le Gestionnaire de règles pour que le bot ne confonde pas les combats du soir et de la nuit.

**Synchronisation intelligente :**
Imagine que tu as joué à la main ce matin sur ton téléphone et que tu as récupéré 60 de titanite. Le soir, tu lances le bot. Comment le bot peut-il comprendre la situation globale ?
C'est très simple ! Va dans l'onglet « Statistiques », choisis le jour (Aujourd'hui) et saisis dans le champ la **valeur TOTALE de titanite** que tu vois en jeu (par exemple, 150). Le bot est malin : il sait qu'il en a farmé 90 de son côté, il va donc les soustraire des 150, puis ajouter proprement tes 60 points faits à la main dans les statistiques, en recalculant les salles et les potions correspondantes. Une protection contre les erreurs est intégrée : le bot ne te laissera pas entrer un nombre inférieur à ce qu'il a lui-même farmé.



## Section 8. Raccourcis clavier PC

* **Ctrl + Q (Pause douce) :** Le bot n'abandonnera pas la partie en plein combat. Il va achever proprement les ennemis, récupérer la récompense, s'arrêter devant la porte suivante et attendre.
* **Ctrl + Shift + Q (ARRÊT d'urgence) :** Arrête instantanément le bot. À utiliser si quelque chose tourne mal.