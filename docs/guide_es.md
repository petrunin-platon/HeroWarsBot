# Guía completa de usuario de Hero Wars RPA Bot v1.0

¡Hola! Te damos la bienvenida al sistema de automatización para Hero Wars. 

Aclaremos algo de entrada: este bot no es un simple programa tonto que hace clics sin sentido en la pantalla. Es tu asistente inteligente personal (agente RPA). Sabe «ver» la pantalla del juego, evaluar la salud de tus titanes, recopilar estadísticas y tomar decisiones tácticas en tiempo real mientras limpias la Mazmorra.

Veamos paso a paso cómo configurarlo todo para que el farmeo sea fácil, seguro y te consiga el máximo de recursos.



## Sección 1. Cómo conectar tu teléfono a la PC

El bot controla el juego mediante un programa especial de duplicación de pantalla (scrcpy). Para que el bot pueda tomar el control, solo necesitas configurar tu teléfono una vez.

* **Activa la «Depuración por USB»:** En tu teléfono Android, ve a Ajustes -> Opciones de desarrollador y activa «Depuración por USB». Si el menú «Opciones de desarrollador» está oculto, toca 7 veces seguidas en «Número de compilación» dentro de «Acerca del teléfono».
* **Conecta el cable:** Conecta tu teléfono a la PC con un buen cable USB. En el teléfono aparecerá el mensaje «¿Permitir depuración USB desde este equipo?». Marca la casilla «Permitir siempre» y pulsa «Aceptar».
* **Entra al juego:** Abre Hero Wars, ve a la Mazmorra y detente en el pasillo (donde se vea la siguiente puerta).
* **Conecta el bot:** En la ventana de nuestro programa, haz clic en el botón «1. Conectar teléfono». Aparecerá una ventana en tu monitor con la pantalla de tu teléfono.

**➡ LA REGLA MÁS IMPORTANTE:** El bot «mira» el juego exactamente como tú, con sus ojos digitales. ¡La ventana de transmisión del juego siempre debe estar visible en tu monitor! No debes minimizarla, taparla con el navegador ni esconderla fuera del borde de la pantalla. Si la ventana queda tapada, el bot se detendrá y esperará a que le devuelvas la vista.

**➡ Farmeo nocturno:** Si quieres dejar el bot farmeando toda la noche sin quemar la pantalla de tu teléfono, usa el botón «APAGAR Pantalla» en el Panel de Control. La pantalla del teléfono se apagará (quedará en negro), ¡pero el juego seguirá funcionando por dentro y el bot lo verá todo!



## Sección 2. Objetivos de la sesión (Panel de Control)

Puedes decirle al bot: "Pica hasta conseguir la cuota del gremio y luego descansa". Ve a la pestaña «Maestro de Reglas» y elige un objetivo:

* Por cantidad de Titanita (por ejemplo, detenerse al llegar a 150).
* Por cantidad de Salas (por ejemplo, completar exactamente 10 puertas).
* Por Pisos (completar 2 pisos).
* Por Tiempo (farmear durante exactamente 30 minutos).

Una vez fijados los límites, regresa a la pestaña Principal y pulsa «2. Iniciar farmeo». El bot ajustará automáticamente el tamaño de la ventana, formará el equipo adecuado e irá directo al combate.



## Sección 3. Maestro de Reglas (Enseñando al bot a pensar)

En la Mazmorra hay 4 tipos de salas: Tierra, Agua, Fuego y Mixta. Para que el bot no solo haga clics, sino que tome decisiones como un jugador experto, puedes configurar la lógica para cada elemento de forma individual.

**1. Pack básico (Equipo por defecto)**

Es tu alineación principal, la que el bot usará de forma predeterminada. Al principio, todos los espacios estarán vacíos.

* Haz clic en el botón azul del elemento correspondiente (por ejemplo, «Agua»).
* En la ventana que se abra, selecciona entre 3 y 5 titanes (lo habitual es poner los cinco completos; por ejemplo, Hyperion, Sigurd, Tidus, Nova, Mairi).
* Pulsa el botón verde «Aplicar».

Si en el juego todo va según lo planeado y la salud está bien, el bot siempre jugará con este equipo.

**2. Constructor de reglas (Intercepciones)**

A veces las cosas se salen de control. Para eso existen las reglas (botón **«+ Condición»**). El bot evalúa la situación ante cada puerta y puede tomar el control cambiando de equipo. El nombre de la regla lo inventas tú: no influye en nada, solo sirve para que te orientes.

Las condiciones se dividen en tres tipos:

* **Por salud (PS):** Por ejemplo, si tu tanque Sigurd suele perder mucha vida, creas la regla: *«Si los PS de Sigurd bajan del 35%, elegir formación con sanador (Iyari)»*. Regla de oro: crea la intercepción para curar **¡justo en el elemento donde ese titán pueda curarse!** (Para Sigurd, sería una sala de Agua o Mixta).

* **Por energía:** Fundamental para equipos rápidos. Por ejemplo, tu Angus elimina a los enemigos en la sala de Tierra de una sola ulti en cuestión de segundos, sin dejarlos atacar. Pero para eso, debe entrar al combate cargado. Crea la regla: *«Si la Energía de Angus es inferior al 97% — detener el bot»*. El bot llegará a la sala de Tierra, emitirá un pitido y se detendrá para que puedas entrar manualmente a una sala Mixta y cargar la energía de Angus.

* **Por enemigos (Anti-packs):** Si no soportas al Araji enemigo (porque incinera a tu equipo), configura la regla: «Si en los enemigos está Araji, usar mi anti-pack especial».

**3. Opciones inteligentes (Skip y Rodaje)**

En el Constructor de Reglas hay casillas que te salvan de muertes absurdas:

* **Prohibir entrar a la sala (Skip):** Imagina que a Sigurd le queda un 10% de PS y el bot tiene delante una sala Mixta. Si entra, Sigurd morirá. Marcas la casilla «Skip» (Prohibir entrada) si los PS bajan del 20%. El bot verá a Sigurd tocado, ignorará la sala Mixta e irá a buscar una sala de Agua para curarlo.

* **Exigir rodaje de titanes:** ¡Una función única para empezar el nuevo día de juego! Por la mañana, todos los titanes tienen el 100% de PS pero 0% de energía. Si los metes de golpe a una sala Mixta difícil, caerán antes de poder tirar su ulti. La casilla «Rodaje» le dice al bot: "Este titán debe disputar primero al menos una batalla fácil en su elemento nativo para acumular energía, y solo después podrá colocarse en salas Mixtas".

**4. Prioridades: ¿Quién manda?**

¿Qué hace el bot si Sigurd tiene poca vida, pero enfrente hay un temible Araji?
El bot lee tu lista de reglas **estrictamente de arriba a abajo**, como una persona de carne y hueso.

Haz clic en el botón gris **«Ver/Eliminar reglas activas»**. Allí verás la lógica del bot. Agrupa todo así:

1. **Primero, las reglas "Skip"** (no enviar titanes heridos al combate).
2. **Luego, salvación por PS y Energía**.
3. **Después, los anti-packs (según enemigos)**.
4. **Al final del todo, el Pack Básico**, si no hay ninguna amenaza.

En esta ventana puedes mover las reglas con las flechas (Arriba/Abajo). A lo que esté más arriba en la lista, el bot le dará máxima prioridad. Si cambias el orden, asegúrate de presionar el botón verde **«Guardar cambios»**.

**5. IMPORTANTE: Cómo guarda el bot la memoria**

La interfaz del bot está diseñada para no "maltratar" tu disco duro con escrituras constantes y funcionar a la velocidad del rayo.

1. Al configurar reglas, haz clic siempre en el **botón morado «Guardar perfil»** en la pantalla principal.
2. Al pulsar el botón «Farmear», el bot lee todas las reglas **una sola vez** y las carga en la memoria RAM.
3. Si el bot ya está farmeando y cambias las reglas sobre la marcha y las guardas, ¡el bot NO las verá! Tendrás que pulsar «Detener» y volver a iniciar «Farmear» para que el bot vuelva a leer la nueva configuración.

**➡ Botón "Restaurar / Restablecer":** Si por un corte de luz o fallo del sistema se daña el archivo de configuración, pulsa este botón rojo ANTES de iniciar el farmeo. El bot recuperará automáticamente la copia de seguridad y lo arreglará todo.

**6. Control global de Angus**

El interruptor **«Control manual de la ulti de Angus (Global)»** está en la pantalla principal por una buena razón. El bot sabe jugar con Angus mejor que muchos humanos: espera exactamente 1.8 segundos para que las raíces inflijan el daño máximo y cancela de inmediato la ulti. Si la casilla está activada, el bot aplicará este truco **en absolutamente todos los combates** donde participe Angus, ya sea en el pack básico o en una intercepción por condición. Pero antes de activar esta opción, asegúrate de que tu Angus tenga el 100% de energía cargada.

**Secreto del desarrollador: ¿Por qué el bot pausa tan seguido y cómo hacerlo 100% autónomo?**

Situación común en los primeros inicios: visualmente los titanes aún tienen muchísima vida, pero el bot no para de pausar el juego, sacar la ventana de SOS y preguntar qué hacer. Da la impresión de que entra en pánico sin motivo.

Todo se debe al ajuste **«Delta de pérdida de PS»** (en la pantalla principal).
El delta es una protección contra el daño repentino y brusco en un único combate. Por ejemplo, tienes configurado un Delta del 30%. Si tu titán entra a la sala con el 100% de vida y sale con el 69% (ha perdido un 31%), el bot se detendrá al instante, aunque ese 69% siga siendo una barra verde y no suponga peligro de muerte.

**Cómo dejar de distraerse con ventanas SOS y hacer que el bot sea autónomo:**

1. **Relaja el «Delta» (para los más prácticos):** Si te molestan las interrupciones constantes y confías en tus titanes, simplemente sube el «Delta de pérdida de PS» hasta el 100% (básicamente desactivándolo). Así, el bot dejará de calcular el daño por combate individual y se guiará *únicamente* por el «Umbral de pánico de PS»; es decir, solo se detendrá cuando la vida caiga a un mínimo crítico real (por ejemplo, menos del 25%).

2. **Convierte las paradas en experiencia:** Cada ventana de SOS es una oportunidad para entrar al Maestro de Reglas y crear una condición, para que la próxima vez el bot sepa cómo evitar ese daño.

3. **Usa las Analíticas (El camino hacia la autonomía total):** ¡Esto es lo más importante! Después de cada sesión de juego, entra a la pestaña «Analítica» y ejecuta el análisis de registros. El bot encontrará patrones por sí solo y te sugerirá **«Reglas de Oro»** (alineaciones ganadoras comprobadas). Solo dale a «Implementar».

**En resumen:** Cuantas más «Reglas de Oro» y condiciones manuales aprenda el bot, menos preguntas te hará. Con el tiempo, creará la base de datos ideal para el nivel de tus titanes y ¡será **100% autónomo**!



## Sección 4. Protección contra derrotas (Ajustes de PS y SOS)

El bot nunca dejará morir a tus titanes sin consultarte. Tras cada combate, analiza minuciosamente las barras de vida. En la pestaña "Maestro de Reglas" hay dos ajustes clave de seguridad:

* **Umbral de pánico de PS (por ejemplo, 40%):** Es el mínimo absoluto. Si tras un combate a cualquiera de tus titanes le queda menos del 40% de vida, el bot hace sonar la alarma.
* **Delta de pérdida de PS (por ejemplo, 30%):** Protección contra daño masivo repentino. Si un titán entra al combate con 100% de PS y sale con 60%, ha perdido un 40% (ese es el delta). Si fijaste no perder más del 30% en un solo combate, el bot detendrá el juego aunque le quede mucha vida.

**Sistema SOS (Menú de rescate):**
Si salta el Pánico, el Delta o muere alguien, el bot pausa el juego y te muestra una ventana con tres opciones:
* **Completar manualmente:** El bot se retira, reinicia el combate y tú pasas la sala por tu cuenta.
* **Reintentar combate:** El bot cancela el combate para que puedas elegir otro pack e intentarlo de nuevo.
* **Ignorar:** Le dices al bot: «Todo bien, permito estas pérdidas, pasemos a la siguiente sala».



## Sección 5. Notificaciones en Telegram

Puedes irte a tomar un café o salir a pasear mientras el bot farmea. Si los titanes están al borde de la muerte, ¡el bot te enviará una captura de pantalla y botones de control directo a tu Telegram!

* **Paso 1:** Busca en Telegram el bot oficial **@BotFather**. Envíale el comando `/newbot`, elige un nombre y copia el `Token` largo.
* **Paso 2:** Busca el bot **@getmyid_bot**. Pulsa Start y copia tus números en `Your user ID`.
* **Paso 3:** Vuelve al chat con tu nuevo bot del Paso 1 y asegúrate de pulsar el botón **"INICIAR"**.
* **Paso 4:** En nuestro programa, abre «Maestro de Reglas» y haz clic en **«Configurar Telegram»**. Pega el Token y el Chat ID, pulsa "Aplicar" y luego "Guardar perfil".



## Sección 6. Analítica y Aprendizaje

El bot registra en un diario invisible cada uno de tus combates: quién luchó contra quién y cuántos PS quedaron.

Ve a la pestaña «Analítica» y pulsa «Iniciar análisis de registros». El bot calculará tu Winrate (porcentaje de victorias) para cada formación. Si encuentra un equipo que vence de forma constante a ciertos enemigos con más del 80% de probabilidad, lo bautizará como **«Regla de Oro»**.
Haz clic en «Implementar» ¡y el bot recordará esa táctica ganadora para siempre!



## Sección 7. Estadísticas y Sincronización

El bot lleva un registro estadístico visualmente impecable: genera gráficos, cuenta la titanita, las salas y las pociones.

**Importante sobre la Hora del Juego:** 
El nuevo día en Hero Wars comienza a las 05:00 de la mañana. No olvides indicar tu "Hora de reinicio diario" en el Maestro de Reglas para que el bot no confunda los combates nocturnos con los del día siguiente.

**Sincronización inteligente:**
Imagina que jugaste por la mañana a mano en el móvil y reuniste 60 de titanita. Por la tarde inicias el bot. ¿Cómo entiende el bot el panorama general?
¡Muy fácil! Ve a la pestaña «Estadísticas», selecciona el día (Hoy) y escribe en el campo la **cifra TOTAL de titanita** que ves en el juego (por ejemplo, 150). El bot es inteligente: sabe que él mismo recolectó 90, los restará de 150 y sumará limpiamente tus 60 puntos manuales a las estadísticas, calculando las salas y pociones correspondientes. Viene con protección contra errores: el bot no te dejará introducir un número inferior al que haya conseguido él mismo.



## Sección 8. Atajos de teclado en PC

* **Ctrl + Q (Pausa suave):** El bot no abandonará el juego en medio de un combate. Rematará cuidadosamente a los enemigos, recogerá la recompensa, se detendrá ante la siguiente puerta y se quedará esperando.
* **Ctrl + Shift + Q (STOP de emergencia):** Apaga el bot de forma instantánea. Úsalo si algo sale mal.