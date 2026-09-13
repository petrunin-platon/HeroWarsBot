# Guia Completo do Usuário - Bot RPA do Hero Wars v1.0

E aí! Boas-vindas ao sistema de automação para o jogo Hero Wars. 

Vamos deixar uma coisa bem clara: este bot não é só um programa bobo que clica na tela sem pensar. Ele é o seu assistente inteligente pessoal (um agente RPA). Ele consegue "ver" a tela do jogo, avaliar a vida dos seus titãs, coletar estatísticas e tomar decisões táticas em tempo real enquanto limpa a Masmorra.

Vamos ver o passo a passo de como configurar tudo para que o seu farm seja fácil, seguro e renda o máximo de recursos possível.



## Seção 1. Como conectar o celular ao computador

O bot controla o jogo por meio de um programa especial de transmissão de tela (scrcpy). Para que o bot possa assumir o controle, você precisa configurar o seu celular apenas uma vez.

* **Ative a "Depuração USB":** No seu celular Android, vá em Configurações -> Opções do desenvolvedor e ative a "Depuração USB". Se o menu "Opções do desenvolvedor" estiver oculto, toque 7 vezes em "Número da versão" na seção "Sobre o telefone".
* **Conecte o cabo:** Conecte o celular ao PC usando um bom cabo USB. No celular, aparecerá a pergunta "Permitir depuração USB a partir deste computador?". Marque a caixa "Sempre permitir" e toque em "OK".
* **Abra o jogo:** Abra o Hero Wars, vá para a Masmorra e pare no corredor (onde dá para ver a próxima porta).
* **Conecte o bot:** Na janela do nosso programa, clique no botão "1. Conectar telefone". A tela do seu celular vai aparecer no monitor do PC.

**➡ A REGRA MAIS IMPORTANTE:** O bot "enxerga" o jogo exatamente como você — com os olhos digitais dele. A janela de transmissão do jogo deve sempre estar visível no monitor! Você não pode minimizá-la, cobri-la com o navegador ou escondê-la nos cantos da tela. Se a janela for coberta, o bot vai parar e esperar até que você devolva a visão a ele.

**➡ Farm noturno:** Se quiser deixar o bot farmando de madrugada sem queimar a tela do celular, use o botão "Desligar Tela" no Painel de Controle. A tela do celular vai apagar (ficar preta), mas o jogo continuará rodando internamente e o bot continuará vendo tudo!



## Seção 2. Objetivos da Sessão (Painel de Controle)

Você pode dizer ao bot: "Cave até juntar a meta da guilda e depois vá descansar". Vá até a aba "Mestre de Regras" e escolha o seu objetivo:

* Por quantidade de Titanita (por exemplo, parar em 150).
* Por quantidade de Salas (por exemplo, passar exatamente por 10 portas).
* Por Andares (passar 2 andares).
* Por Tempo (farmar exatamente por 30 minutos).

Com os limites definidos, volte para a aba Principal e clique em "2. Iniciar Farm". O bot vai ajustar o tamanho da janela sozinho, montar a equipe certa e correr para a batalha.



## Seção 3. Mestre de Regras (Ensinando o bot a pensar)

Na Masmorra existem 4 типа salas: Terra, Água, Fogo e Mista. Para que o bot não fique apenas clicando, mas tome decisões como um jogador experiente, você pode configurar a lógica para cada elemento individualmente.

**1. Comp Padrão (Equipe padrão)**

Esta é a sua formação principal que o bot usará por padrão. Inicialmente, todos os slots ficam vazios.

* Clique no botão azul do elemento desejado (por exemplo, "Água").
* Na janela que abrir, escolha de 3 a 5 titãs (geralmente coloca-se o time completo de 5 — por exemplo, Hyperion, Sigurd, Tethys, Nova, Mairi).
* Clique no botão verde "Aplicar".

Se tudo estiver correndo conforme o planejado no jogo e a vida estiver de boa, o bot sempre usará essa comp.

**2. Construtor de Regras (Interceptações)**

Às vezes, as coisas saem do controle. É para isso que servem as regras (botão **"+ Condição"**). O bot avalia a situação antes de cada porta e pode assumir o controle manualmente, mudando de equipe. O nome da regra você mesmo inventa — ele não afeta nada, serve apenas para você se organizar.

As condições são divididas em três tipos:

* **Por vida (HP):** Por exemplo, seu tanque Sigurd costuma ficar miado (com pouca vida). Você cria a regra: *“Se o HP do Sigurd estiver abaixo de 35%, selecionar a comp com healer (Iyari)”*. Regra de ouro: crie a interceptação de cura **exatamente no elemento onde esse titã pode se curar!** (Para o Sigurd, isso seria na sala de Água ou Mista).

* **Por energia:** Crítico para comps rápidas. Por exemplo, o seu Angus mata os inimigos na sala de Terra com um único ult em poucos segundos, sem dar chance de contra-ataque. Mas para isso, ele precisa entrar na luta carregado. Crie a regra: *“Se a Energia do Angus estiver abaixo de 97% — parar o bot”*. O bot vai até a sala de Terra, vai apitar e parar para que você possa entrar na sala Mista manualmente e acumular energia para o Angus.

* **Por inimigos (Anti-comps):** Se você odeia o Araji inimigo (ele derrete a sua equipe), configure a regra: "Se houver Araji entre os inimigos, use minha anti-comp especial".

**3. Opções Inteligentes (Pular/Skip e Aquecimento)**

No Construtor de Regras existem caixas de seleção que evitam mortes bobas:

* **Proibir entrada na sala (Pular / Skip):** Imagine que o Sigurd está com 10% de HP e tem uma sala Mista à frente do bot. Se ele entrar lá, o Sigurd morre. Você marca a opção "Skip" (Pular) para quando o HP estiver abaixo de 20%. O bot vai ver o Sigurd machucado, vai ignorar a sala Mista e procurar uma sala de Água para curá-lo.

* **Exigir aquecimento dos titãs:** Um recurso único para o início de um novo dia de jogo! Pela manhã, todos os titãs têm 100% de HP, но 0% de energia. Se você os mandar direto para uma sala Mista difícil, eles vão morrer antes de conseguir ultar. A opção "Aquecimento" diz ao bot: "Este titã deve primeiro passar por pelo menos uma batalha fácil em seu elemento nativo para acumular mana, e só depois pode ser colocado em salas Mistas".

**4. Prioridades: Quem tem preferência?**

O que o bot deve fazer se o Sigurd estiver com pouco HP, mas ao mesmo tempo houver um Araji assustador entre os inimigos?
O bot lê a sua lista de regras **estritamente de cima para baixo**, como um ser humano faria.

Clique no botão cinza **"Ver/Excluir regras ativas"**. Lá você verá a lógica do bot. Ele agrupa tudo assim:

1. **Primeiro as regras de "Skip"** (não deixar titãs machucados entrarem em combate).
2. **Depois, salvamento por HP e Energia**.
3. **Depois, anti-comps (por inimigos)**.
4. **Por último, a Comp Padrão**, se não houver ameaças.

Nesta janela, você pode mover as regras usando as setas (Para Cima/Para Baixo). A regra que estiver mais no topo da lista será a que o bot ouvirá primeiro. Se você alterar a ordem, lembre-se de clicar no botão verde **"Salvar alterações"** ali mesmo.

**5. IMPORTANTE: Como o bot salva a memória**

La interface do bot foi feita para não sobrecarregar o seu disco rígido com gravações constantes e para funcionar na velocidade da luz.

1. Sempre que configurar as regras, lembre-se de clicar no **botão roxo "Salvar Perfil"** na tela principal.
2. Quando você clica no botão "Farm", o bot lê todas as regras **uma única vez** e as carrega na memória RAM.
3. Se o bot já estiver farmando e você alterar e salvar as regras no meio do caminho, o bot NÃO vai visualizá-las! Você precisará clicar em "Parar" e iniciar o "Farm" novamente para o bot "reler" as novas configurações.

**➡ Botão "Restaurar / Reset":** Se o arquivo de configurações for corrompido devido a uma queda de energia repentina ou erro de sistema, basta clicar neste botão vermelho ANTES de iniciar o farm. O bot recuperará automaticamente um backup das configurações e resolverá o problema.

**6. Controle Global do Angus**

A chave **"Controle manual da ult do Angus (Global)"** não está na tela principal por acaso. O bot sabe jogar com o Angus melhor do que muita gente: ele espera exatamente 1.8 segundo para que as raízes causem o dano máximo e desativa a ult imediatamente depois. Se a opção estiver marcada, o bot aplicará essa jogada **em absolutamente todas as batalhas** que o Angus participar, seja na comp padrão ou em uma interceptação por condição. Mas antes de ativar essa opção, certifique-se de que o Angus está com 100% de energia antes de usar esta configuração.

**Segredo do desenvolvedor: Por que o bot pausa tanto e como deixá-lo 100% autônomo?**

Uma situação comum nos primeiros usos: a vida dos titãs parece cheia visualmente, mas o bot pausa o jogo o tempo todo, exibe uma janela de SOS e pergunta o que fazer. Parece que ele está entrando em pânico sem motivo.

Tudo se resume à configuração **"Delta de perda de HP"** (localizada na tela principal).
O Delta é uma proteção contra danos bruscos e repentinos em uma única batalha específica. Por exemplo, se você definiu o Delta em 30% e o seu titã entrou na sala com 100% de vida e saiu com 69% (perdeu 31%), o bot vai parar instantaneamente, mesmo que 69% ainda seja uma barra verde e nada crítica para a sobrevivência.

**Como parar de ser interrompido por janelas SOS e deixar o bot independente:**

1. **Aumente o "Delta" (para os preguiçosos):** Se as interceptações frequentes te irritam e você confia nos seus titãs, basta aumentar o "Delta de perda de HP" para até 100% (praticamente desativando-o). Nesse caso, o bot vai parar de calcular o dano por batalha livre e vai focar *apenas* no "Limiar de Pânico de HP" — ou seja, ele só vai parar quando a vida realmente cair para um mínimo crítico (por exemplo, abaixo de 25%).

2. **Transforme as paradas em aprendizado:** Cada janela de SOS é uma oportunidade para ir ao Mestre de Regras e criar uma condição, para que da próxima vez o bot saiba como evitar esse dano.

3. **Use a Análise (O caminho para a autonomia total):** Isso é o mais importante! Após cada sessão de jogo, acesse a aba "Análise" e execute a análise de logs. O bot identificará padrões sozinho e sugerirá as **"Regras de Ouro"** (composições de vitória comprovadas). Basta clicar em "Implementar".

**Resumo:** Quanto mais "Regras de Ouro" e condições manuais o bot aprender, menos perguntas ele fará. Com o tempo, ele montará a base de conhecimento perfeita para o nível dos seus titãs e se tornará **100% autônomo**!



## Seção 4. Proteção contra Derrotas (Configurações de HP e SOS)

O bot nunca vai deixar seus titãs morrerem sem a sua permissão. Após cada batalha, ele analisa com atenção as barras de vida. Na aba "Mestre de Regras" existem duas configurações de segurança principais:

* **Limiar de Pânico de HP (por exemplo, 40%):** Este é o mínimo absoluto. Se após a batalha qualquer um de seus titãs ficar com menos de 40% de vida, o bot vai disparar o alarme.
* **Delta de perda de HP (por exemplo, 30%):** Proteção contra dano repentino. Se o titã entrou na batalha com 100% de HP e saiu com 60%, ele perdeu 40% (este é o delta). Se você configurou para não perder mais de 30% em uma batalha, o bot vai pausar o jogo, mesmo se ainda restar bastante vida.

**Sistema SOS (Menu de resgate):**
Se o Pânico, o Delta forem acionados ou se alguém morrer, o bot pausa o jogo e mostra uma janela com três opções:
* **Jogar manualmente:** O bot recua, cancela a batalha e você passa a sala por conta própria.
* **Desfazer batalha:** O bot cancelará o combate e você poderá escolher outra comp para tentar de novo.
* **Ignorar:** Você diz ao bot: "Está de boa, eu aceito essas perdas, pode ir para a próxima sala".



## Seção 5. Notificações no Telegram

Você pode ir tomar um café ou dar uma volta enquanto o bot farma. Se os titãs estiverem prestes a morrer, o bot enviará um print e botões de controle direto no seu Telegram!

* **Passo 1:** Procure o bot oficial **@BotFather** no Telegram. Envie o comando `/newbot`, escolha um nome e copie o código `Token` longo.
* **Passo 2:** Procure pelo bot **@getmyid_bot**. Clique em Start e copie os números de `Your user ID`.
* **Passo 3:** Volte para a conversa com o seu novo bot criado no Passo 1 e clique obrigatoriamente no botão **"COMEÇAR"** (ou /start).
* **Passo 4:** No nosso programa, abra o "Mestre de Regras" e clique em **"Configurar Telegram"**. Insira o Token e o Chat ID, clique em "Aplicar" e em "Salvar Perfil".



## Seção 6. Análise e Aprendizado

O bot registra em um histórico invisível cada uma das suas batalhas: quem lutou contra quem e quanto HP sobrou.

Acesse a aba "Análise" e clique em "Iniciar análise de logs". O bot vai calcular a sua Taxa de Vitória (Winrate) para cada comp. Se ele encontrar uma equipe que vence constantemente certos inimigos com uma chance de mais de 80%, ele a chamará de **"Regra de Ouro"**.
Clique em "Implementar" — e o bot lembrará dessa tática vencedora para sempre!



## Seção 7. Estatísticas e Sincronização

O bot gera estatísticas visuais bem legais: desenha gráficos, conta a titanita, as salas e as poções. 

**Importante sobre o Horário do Jogo:** 
O novo dia no jogo Hero Wars começa às 05:00 da manhã. Lembre-se de definir a sua "Hora de reset do dia" no Mestre de Regras para que o bot não confunda as batalhas da noite com as da madrugada.

**Sincronização inteligente:**
Imagine que você jogou manualmente no celular pela manhã e coletou 60 de titanita. À noite, você ligou o bot. Como o bot pode entender o progresso geral?
Muito simples! Vá até a aba "Estatísticas", escolha o dia (Hoje) e digite no campo o **VALOR TOTAL de titanita** que você vê no jogo (por exemplo, 150). O bot é inteligente: ele sabe que farmou 90 sozinho, vai subtraí-los de 150 e adicionará cuidadosamente seus 60 pontos manuais às estatísticas, calculando as salas e poções referentes a eles. Há uma proteção contra erros integrada — o bot não deixará você digitar um número menor do que o que ele mesmo farmou.



## Seção 8. Teclas de Atalho no PC

* **Ctrl + Q (Pausa suave):** O bot não vai abandonar o jogo no meio da batalha. Ele vai derrotar os inimigos com calma, coletar a recompensa, parar antes della próxima porta e esperar.
* **Ctrl + Shift + Q (PARADA de Emergência):** Desliga o bot instantaneamente. Use se algo der muito errado.