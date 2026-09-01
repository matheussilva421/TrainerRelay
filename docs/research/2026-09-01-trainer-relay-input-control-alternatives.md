# Trainer Relay — alternativas para acionar hotkeys de trainers FLiNG

**Data:** 2026-09-01

**Escopo:** investigação técnica read-only para Steam Deck, Game Mode, Decky Loader, UniFiDeck, UMU e Proton.

**Arquivo criado nesta investigação:** este documento. Nenhum código, trainer, configuração, processo, prefixo, container ou arquivo existente foi alterado.

## Resposta curta

Para um trainer FLiNG Windows **não modificado**, a alternativa atualmente mais viável é um helper Windows pequeno e **one-shot**, lançado por UMU com PROTON_VERB=runinprefix e com o reentry explícito do mesmo container usado pelo jogo. Ele pode enviar uma hotkey conhecida com SendInput, mas só deve reportar **comando solicitado** ou **evento de entrada aceito pelo sistema**. Isso não prova que o FLiNG recebeu a tecla, alternou o cheat ou aplicou o efeito no jogo.

Essa alternativa evita um EXE auxiliar residente, mas não elimina o processo auxiliar: há pelo menos um processo Windows transitório para chamar user32, além da cadeia de launcher/container que UMU/Proton precisar. Portanto:

> **Não há uma opção documentada e já validada que controle de forma confiável um FLiNG não modificado sem sequer um terceiro processo transitório.**

Steam Input, uinput, evdev, XTest, Wayland e gamescope podem produzir eventos na camada Linux/compositor, mas não oferecem um contrato para selecionar o processo Windows do trainer, o HWND correto ou a hotkey registrada pelo FLiNG. Podem ser experimentos de transporte, não a base do contrato do Trainer Relay.

Para **estado real**, a ordem de confiabilidade é:

1. integração cooperativa no trainer, com protocolo versionado de comando, confirmação e estado verificado;
2. observer de memória read-only, somente para jogo/build/assinatura previamente conhecidos e validados;
3. UI Automation, apenas como estado visual condicional;
4. hotkey enviada, processo vivo ou janela visível: não são estado real.

## Como a evidência foi classificada

- **Documentado:** a fonte primária promete o comportamento da API/protocolo.
- **Medido localmente:** observado por leitura estática do checkout ou por comando read-only nesta investigação.
- **Inferido:** consequência técnica razoável, mas não uma promessa da fonte nem uma medição no Deck.
- **Não validado:** requer teste físico no Steam Deck/Game Mode, um build específico do trainer ou uma autorização que não foi dada.

O risco de anti-cheat abaixo é uma avaliação de engenharia, não uma declaração de compatibilidade de qualquer jogo. Não foi encontrada uma fonte primária geral que autorize injeção, uinput, XTest ou automação de um trainer externo perante todo anti-cheat. Onde não houver uma promessa oficial, o risco é marcado como inferido/unknown.

## Linha de base local

### Trainer Relay

**Medido localmente:**

- O branch inicial estava limpo em feat/trainer-relay, acompanhando origin/feat/trainer-relay, com HEAD 4efb7f6 (docs: research trainer cheat introspection).
- O README descreve um plugin Decky que acompanha shortcuts Epic/GOG da UniFiDeck, inicia um trainer .exe através de UMU e usa o mesmo prefixo com reentry explícito. A própria documentação diz que a validação física no Steam Deck ainda é o limite experimental.
- main.py:66-78 constrói OwnedTrainerRunner e RelayWatcher; main.py:97-110 mantém o watcher como task do backend Decky. Portanto o backend do plugin já é residente.
- trainer_relay/runner.py:256-332 chama subprocess.Popen([umu_run, trainer_executable], shell=False, start_new_session=True) e rastreia o grupo do sidecar. O mecanismo atual é de lançamento/ownership, não de comando de cheat.
- src/domain/relay/types.ts:3-22 contém configuração de caminho/prefixo e estados de ciclo de vida. src/infra/relayRpc.ts:12-17 expõe configuração, status e retry, mas não catálogo, comando de cheat, acknowledgement ou estado de cheat.
- README.md:45-50, CONTEXT.md:21-36 e docs/adr/0001-session-watcher.md:32-60 delimitam o contrato atual: mesmo prefixo, UMU_CONTAINER_NSENTER=1, steam-runtime-launch-client, PROTON_VERB=runinprefix, validação da sessão e falha fechada. Isso melhora a execução do sidecar, mas não cria uma interface de hotkeys ou estado.

### FlingDeckWrapper

O diretório consultado foi C:\Users\slvma\Downloads\Github\Mods\.worktrees\fling-re-analysis\Tools\FlingDeckWrapper, somente para leitura.

**Medido localmente:**

- src/WindowsInputSender.cs:7-36 monta key-down/key-up, libera modificadores em ordem reversa e chama NativeMethods.SendInput.
- src/NativeMethods.cs:36-43 declara SendInput, ShowWindow e GetForegroundWindow; não há PostMessage, UI Automation, IPC, leitura/escrita de memória, DLL ou remote thread.
- src/TrainerProcessManager.cs:15-69 procura o executável por caminho completo, pode iniciar/reutilizar o FLiNG e minimiza a janela; CloseIfOwned só encerra o processo que o wrapper iniciou.
- src/MainForm.cs:51-59 declara explicitamente que o estado do cheat não é observável; :145-172 verifica hash, inicia/reutiliza o trainer e o minimiza; :248-260 registra “comando enviado” depois de SendInput; :301-315 envia Home e encerra somente a sessão própria.
- src/Contracts.cs:6-17 define apenas a abstração de input e de ciclo de vida do processo. Os testes locais dos perfis amarram nome, hash, título, opções e teclas de builds conhecidos, mas não provam o efeito no jogo.
- O git status do worktree do wrapper não pôde ser obtido porque o Git recusou a ownership do diretório como safe.directory; nenhuma configuração global foi alterada. Isso não impediu a leitura dos arquivos.

**Interpretação:** o wrapper é uma prova local de que a fronteira “perfil versionado + envio de hotkey + lifecycle” é implementável. Ele não é evidência de que a hotkey chega ao trainer a partir do compositor Linux, nem de que o cheat está ativo.

Não foram executados trainers, jogos, testes, injeções ou benchmark físico nesta investigação. O relatório não promove o estado experimental atual a validação de Deck.

## Contratos primários relevantes

### Decky, UniFiDeck, UMU, Proton e container

- O [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) é o host do plugin; o [template oficial de plugin](https://github.com/SteamDeckHomebrew/decky-plugin-template/blob/main/main.py) mostra _main/_unload e um backend de longa duração. O [loader do sandbox](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/plugin/sandboxed_plugin.py) despacha chamadas para métodos do plugin, mas não define semântica de hotkey Windows, HWND, trainer ou cheat-state.
- A [arquitetura da UniFiDeck](https://github.com/mubaraknumann/unifideck/blob/staging/docs/architecture.md) e a documentação de [launch options](https://github.com/mubaraknumann/unifideck/blob/staging/docs/launch-options.md) são o contrato externo consultado para launcher/runtime. O checkout local continua sendo a autoridade para o contrato específico do Trainer Relay.
- O [README do UMU](https://github.com/Open-Wine-Components/umu-launcher), o [manual umu.1.scd](https://github.com/Open-Wine-Components/umu-launcher/blob/main/docs/umu.1.scd) e o [código umu_run.py 1.4.4](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_run.py) documentam execução fora do Steam dentro do Steam Runtime, WINEPREFIX, PROTONPATH, GAMEID, STORE, PROTON_VERB e o caminho de reentry por steam-runtime-launch-client quando habilitado. UMU é launcher/runtime, não uma API de controle de aplicações Windows.
- O [código do Proton](https://github.com/ValveSoftware/Proton/blob/proton_10.0/proton) distingue a execução normal da modalidade runinprefix, que executa um processo Wine na sessão/prefixo existente. Isso é a base documentada para um helper no mesmo prefixo; a igualdade de prefixo, sozinha, não é uma garantia de igualdade de container.
- O [Steam Linux Runtime](https://github.com/ValveSoftware/steam-runtime) e sua documentação de [container runtime](https://github.com/ValveSoftware/steam-runtime/blob/master/doc/reporting-steamlinuxruntime-bugs.md) deixam claro que cada jogo pode estar dentro de um container de runtime. O reentry exato usado localmente pelo Trainer Relay é uma decisão específica da integração UMU/UniFiDeck, não uma API genérica do Proton.

### Windows input, foco e UI

- [SendInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput) sintetiza eventos de teclado/mouse, retorna quantos eventos foram inseridos e é bloqueado por UIPI quando o processo chamador não tem integridade suficiente. A função não confirma que o aplicativo pretendido processou a tecla.
- A visão de [keyboard input](https://learn.microsoft.com/en-us/windows/win32/inputdev/about-keyboard-input) da Microsoft separa mensagens de teclado, janela/thread em foco e a sequência de input simulada. [SetForegroundWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow) está sujeito às regras do Windows sobre qual processo pode tomar o foreground.
- [PostMessageW](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-postmessagew) coloca uma mensagem na fila de uma janela. UIPI restringe mensagens entre níveis de integridade e mensagens acima de WM_USER exigem marshalling definido pelo aplicativo. Isso não transforma WM_KEYDOWN em um WM_HOTKEY registrado, nem confirma que o trainer consumiu a mensagem.
- [RegisterHotKey](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey) registra uma combinação para uma janela/thread e faz o sistema postar WM_HOTKEY. A documentação não oferece uma API genérica para enumerar as hotkeys registradas por outro processo.
- [UI Automation](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-uiautomationoverview) expõe elementos e padrões de controle quando há um provider. A documentação de [providers](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-providersoverview) deixa explícito que controls customizados sem provider podem ser opacos; [control patterns](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-controlpatternsoverview) podem expor um Toggle/Invoke, mas só se o aplicativo oferecer o padrão. O [security overview](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview) descreve a fronteira de UIAccess/integridade.

### Input Linux e compositores

- O [Linux input subsystem](https://docs.kernel.org/input/input.html), a [Input Userspace API](https://docs.kernel.org/input/input_uapi.html) e os [event codes](https://docs.kernel.org/input/event-codes.html) descrevem evdev como interface de eventos e EV_KEY como estados down/up/repeat.
- [uinput](https://docs.kernel.org/input/uinput.html) permite que um processo de userspace crie um dispositivo virtual escrevendo em /dev/uinput; os eventos são entregues aos consumidores do dispositivo. A fonte não promete direcionamento a um HWND, a uma superfície Wayland ou a um processo Wine.
- A especificação [XTEST](https://xorg.freedesktop.org/archive/X11R7.7/doc/xextproto/xtest.html) permite ao cliente X testar o servidor com eventos sintéticos. O [código/documentação do xdotool](https://github.com/jordansissel/xdotool/blob/main/xdotool.pod) confirma que essa ferramenta depende de X11/XTEST/Xlib e do display/foco disponíveis.
- O [gamescope da Valve](https://github.com/ValveSoftware/gamescope) é um micro-compositor que usa Wayland/Xwayland em seu modelo documentado; seu [servidor de input](https://github.com/ValveSoftware/gamescope/blob/master/src/wlserver.cpp) trata keyboard/pointer e Xwayland. O [protocolo privado de input method](https://github.com/ValveSoftware/gamescope/blob/master/protocol/gamescope-input-method.xml) diz que é um protocolo privado do gamescope e que clientes Wayland comuns não devem usá-lo. Ele não é uma API pública “envie F1 ao processo FLiNG”.
- O protocolo [virtual keyboard do wlroots](https://github.com/swaywm/wlroots/blob/master/protocol/virtual-keyboard-unstable-v1.xml) modela um teclado virtual associado a um seat e exige keymap antes de eventos. É uma extensão compositor-dependente; a existência do XML não prova que o gamescope da imagem do Deck a habilite ou autorize o plugin.

### Steam Input

- A documentação oficial de [Steam Input](https://partner.steamgames.com/doc/features/steam_controller?l=english) descreve configurações, ações e modos de entrada para jogos.
- O [guia de desenvolvedor](https://partner.steamgames.com/doc/features/steam_controller/getting_started_for_devs?l=english), o [action manifest](https://partner.steamgames.com/doc/features/steam_controller/action_manifest_file?l=english) e a interface [ISteamInput](https://partner.steamgames.com/doc/api/ISteamInput) são contratos do jogo/Steam AppID: o jogo define ações e pode consultá-las. Não há nessas APIs uma chamada Decky/Steamworks para selecionar um trainer externo e acionar sua RegisterHotKey.
- As [boas práticas de emulação](https://partner.steamgames.com/doc/features/steam_controller/steam_input_gamepad_emulation_bestpractices?l=english) explicam que a tradução pode usar gamepad, mouse/keyboard emulation ou Steam Input API. Isso ainda é uma rota de input do jogo/configuração do Steam; não é acknowledgement nem estado do FLiNG.

### Wine, processos e memória

- O [código-fonte oficial do Wine](https://gitlab.winehq.org/wine/wine) e a documentação do [Wine API](https://source.winehq.org/WineAPI/) são a referência para wineserver, user32, processos e DLLs. O [wineserver](https://gitlab.winehq.org/wine/wine/-/blob/master/server/wineserver.c) fornece serviços compartilhados de execução Wine; o [manual do wineserver](https://gitlab.winehq.org/wine/wine/-/blob/master/server/wineserver.man.in) documenta sua seleção por prefixo e seu ciclo de vida. Isso coordena processos, mas não define comando de trainer.
- [OpenProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openprocess) aplica o descritor de segurança do processo e direitos de acesso. [ReadProcessMemory](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-readprocessmemory) exige PROCESS_VM_READ; [WriteProcessMemory](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-writeprocessmemory) e [VirtualAllocEx](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualallocex) exigem direitos de escrita/operação apropriados.
- [CreateRemoteThread](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createremotethread) cria uma thread no processo remoto e requer múltiplos direitos, inclusive leitura/escrita/operação de memória. A própria documentação alerta para efeitos de temporização, layout de endereço e deadlock; isso é uma técnica de injeção, não uma extensão suportada pelo FLiNG.

## Análise das alternativas

### 1. Helper Windows nativo one-shot via UMU/runinprefix

**Modelo:** o backend Decky, já residente, recebe uma ação; inicia um pequeno EXE Windows somente para executar a hotkey conhecida; o helper sai imediatamente. O helper deve usar o umu-run já resolvido pelo UniFiDeck, a raiz compatdata correta, UMU_CONTAINER_NSENTER=1 e PROTON_VERB=runinprefix.

**O que é documentado:** UMU/Proton suportam iniciar um programa Windows com prefixo e runinprefix; o código local já verifica a sessão, o prefixo, o launcher service e o grupo do processo. A chamada SendInput e suas limitações são documentadas pela Microsoft.

**Processo e foco:** o helper é transitório, mas a cadeia UMU/pressure-vessel/launcher também pode criar processos auxiliares transitórios. SendInput usa a entrada interativa do desktop e depende de foreground/foco; tentar SetForegroundWindow não garante tomada de foco. Um FLiNG que usa RegisterHotKey pode exigir a rota de input normal; não existe aqui acknowledgement do WM_HOTKEY.

**Prefixo/container:** é a melhor alternativa para a exigência de mesmo wineserver/prefixo/container, desde que o reentry exato seja confirmado antes de cada sessão. Um umu-run novo com ambiente apenas parecido não deve ser tratado como equivalente ao container do jogo.

**Permissões/dependências/empacotamento:** requer um EXE helper compatível com a arquitetura Wine, uma forma segura de identificar a hotkey por hash/build, UMU/Proton e acesso ao runtime já instalado. SendInput pode falhar por UIPI/integridade. Não requer root Linux além do contrato atual do plugin, mas precisa ser executado no contexto de usuário/runtime correto.

**Game Mode, confiabilidade e anti-cheat:** o helper pode ser headless e não depender de mostrar a janela; ainda assim foco, Xwayland/gamescope e comportamento de user32 em Wine precisam de teste físico. Confiabilidade inicial: **condicional/média-baixa**. Risco anti-cheat adicional: **inferido baixo a médio**, menor que injeção de memória, mas não garantido; o trainer já altera memória do jogo.

**Estado real:** **não**. O máximo seguro é requested, input_inserted ou unknown. Um retorno de SendInput não prova toggle nem patch.

**Veredito:** recomendação de fase 1 para FLiNG não modificado, com o contrato explicitamente sem estado. É o menor custo que respeita o boundary UMU atual, mas não satisfaz “zero terceiro processo”.

### 2. Helper residente com IPC

**Modelo:** um EXE Windows permanece no mesmo prefixo e recebe comandos do Decky por um canal local; pode reutilizar processo, janela, thread de mensagens, foco e caches.

**Processo e IPC:** adiciona um terceiro processo residente e um protocolo de lifecycle. Named pipe/TCP local/ponte Unix são decisões de projeto; UMU, Proton e FLiNG não fornecem esse canal. O helper pode serializar comandos e manter um HWND conhecido, mas isso não elimina as regras do SendInput, PostMessage ou UIPI.

**Prefixo/container e Game Mode:** deve ser iniciado pelo mesmo runinprefix e reentry para compartilhar a sessão Wine. A persistência exige tratar reinício do jogo, troca de prefixo, atualização do Proton, unload do Decky e encerramento sem matar um FLiNG que não é ownership do helper. Em Game Mode, o processo residente deve funcionar sem depender de janela visível.

**Estado real:** para FLiNG não modificado, **não**. IPC só transporta a alegação “enviei tecla”. Para um trainer próprio, o mesmo canal pode carregar acknowledgement e estado verificado; nesse caso a solução deixa de ser genérica FLiNG.

**Empacotamento/risco:** EXE, protocolo, heartbeat, upgrade/rollback e limpeza permanente. Risco anti-cheat adicional: **inferido baixo/médio** se apenas envia input; mais alto se também injeta ou lê memória.

**Veredito:** não justifica o custo para FLiNG puro. É uma opção para muitos comandos por sessão ou para um trainer cooperativo, quando a latência/lifecycle do one-shot for insuficiente.

### 3. Integração ou modificação do trainer

**Modelo:** o trainer expõe seu próprio catálogo, hotkeys, comandos, acknowledgement, sessão e estado; o comando não precisa passar por foco. Em um trainer próprio, o endpoint pode estar no próprio processo, sem EXE auxiliar.

**Estado real:** **sim**, desde que o trainer seja o dono da verificação. Ele conhece o jogo/build, patch bytes, falha, dependências e rollback. O relatório local de introspecção já encontrou o padrão correto nos trainers próprios: CheatRuntime.IsEnabled e a rotina que verifica memória ficam dentro do trainer; hoje essa informação não sai por uma API.

**Prefixo/container:** a integração não exige um segundo container para o comando se o canal local for alcançável, mas o lançamento ainda deve respeitar a sessão UMU do jogo. Para um protocolo Windows local, a implementação e o teste no mesmo wineserver continuam necessários.

**Processo, foco, empacotamento e Game Mode:** pode haver somente Decky + jogo + trainer, sem helper auxiliar, se o endpoint for embutido no trainer. Exige distribuir uma versão modificada, manifestar identidade/hash/versão, tratar bind local e autenticação mínima, e garantir que o trainer continue headless em Game Mode.

**Anti-cheat:** **inferido baixo adicional** quando a integração só coordena o código que já aplica o cheat; ainda é comportamento de trainer e não há garantia do jogo. É muito menos arriscado que remote thread em um processo arbitrário.

**Veredito:** melhor solução de produto para trainers sob controle do projeto; não é uma solução para o binário FLiNG não modificado.

### 4. SendInput

**Modelo:** helper Windows one-shot/residente injeta key-down/key-up no input stream do desktop Wine.

**Pontos fortes:** a API é nativa, simples, disponível em user32 e corresponde ao que o FlingDeckWrapper já implementa. Não exige conhecer o HWND para a inserção, embora exija que o alvo efetivo seja o foreground correto.

**Limites:** UIPI/integridade, foreground, layout/virtual-key, desktop ativo e possíveis diferenças de Wine. O retorno é quantidade de eventos inseridos, não consumo da hotkey. Uma FLiNG minimizado/sem foco, ou um compositor que não encaminha o evento à janela esperada, pode não reagir. O sucesso pode ser SendInput-accepted, não cheat-enabled.

**Processo/prefixo:** não é uma solução sem processo: precisa de um processo Windows que chame user32, a menos que outra camada já existente faça a injeção por conta própria. Rodar o chamador via runinprefix é o caminho mais controlável.

**Estado e risco:** não lê estado. Risco adicional anti-cheat **inferido baixo/médio**, não validado.

**Veredito:** transporte recomendado da fase 1 para uma hotkey conhecida; não usar o resultado como estado.

### 5. PostMessage

**Modelo:** enviar WM_KEYDOWN/WM_KEYUP para um HWND determinado, sem depender do foreground para a entrega à fila.

**Pontos fortes:** pode ser direcionado a uma janela e evita parte da dependência de foco visual.

**Limites:** UIPI pode bloquear; marshalling de mensagens customizadas não é automático; WM_KEYDOWN na fila de uma janela não é a mesma coisa que um evento de teclado físico nem necessariamente aciona RegisterHotKey/WM_HOTKEY. O FLiNG pode usar hotkey global, polling de tecla ou hooks, em vez da fila da janela.

**Processo/prefixo:** exige um chamador Windows com HWND válido e visível para a sessão Wine correta; ainda é transitório/residente conforme o helper. Enumerar uma janela e postar para ela não prova que a rotina do cheat executou.

**Estado e risco:** não fornece estado; risco anti-cheat **inferido baixo**, não validado.

**Veredito:** fallback experimental para controles que comprovadamente aceitem mensagens; não é transporte padrão para hotkeys FLiNG.

### 6. UI Automation

**Modelo:** consultar a árvore de UI e invocar um botão, toggle ou padrão exposto pelo trainer.

**Pontos fortes:** pode evitar foco e dar uma leitura visual de checked/unchecked quando o provider expõe esse padrão.

**Limites:** UI Automation é framework de acessibilidade/teste, não uma API de cheats. Controles customizados podem ser opacos; janela visível não implica provider completo. Mesmo um checkbox marcado representa estado da UI, não prova que o patch no processo do jogo permanece aplicado. UIA também tem fronteiras de integridade/UIAccess e pode não estar implementada no caminho Wine/Proton específico.

**Processo/prefixo/empacotamento:** normalmente precisa de um cliente Windows e de COM/UIAutomationCore; deve alcançar a janela na mesma sessão Wine. A resolução de elementos, providers e permissões precisa ser validada por build. Game Mode e trainer minimizado são riscos.

**Estado e risco:** estado visual **condicional**; estado real do jogo **não**. Risco anti-cheat **inferido baixo**, não validado.

**Veredito:** diagnóstico/fallback para trainers acessíveis; não adequado como descoberta genérica ou contrato de estado FLiNG.

### 7. Injeção Linux uinput/evdev

**Modelo:** o backend Decky (ou um helper Linux one-shot) cria um teclado virtual com uinput; evdev/compositor/Steam/Wine recebem os eventos.

**Processo/persistência:** pode ser incorporado ao backend residente, evitando um EXE Windows extra; ou executado como helper Linux transitório. Não há necessidade de um processo Wine para criar o device, mas um helper separado torna o lifecycle/empacotamento mais complexo.

**Foco e rota:** uinput cria um dispositivo; não seleciona HWND, thread ou trainer. O seat/compositor decide para onde o teclado focado vai. Pode atingir o jogo, o Steam UI ou o trainer somente se a cadeia concreta encaminhar o evento ao alvo.

**Permissões/dependências:** exige kernel/uinput e acesso a /dev/uinput ou /dev/input/uinput; a permissão concreta pode depender de udev/grupo/root da imagem. Evdev é a interface de eventos, não uma garantia de escrita; uinput é a parte de criação/emissão.

**Prefixo/container/Game Mode:** não compartilha wineserver nem entra automaticamente no container do Proton. Em Game Mode, Steam Input e gamescope podem consumir/transformar o evento. A compatibilidade desta rota com o FLiNG no Game Mode do Deck é **não validada**.

**Estado e risco:** não informa o estado do cheat. Risco anti-cheat adicional **inferido baixo/médio**, mas dispositivo virtual e remapeamento não têm garantia de aceitação.

**Veredito:** interessante como experimento de input físico global, mas não como controle dirigido de FLiNG.

### 8. X11/XTest/xdotool

**Modelo:** xdotool/cliente X one-shot usa XTEST/Xlib para emitir teclas ou focar uma janela X.

**Processo/persistência:** xdotool é transitório; um cliente X poderia ser incorporado ao backend Decky, mas ainda dependeria do display/autorização. Um daemon não melhora o contrato do FLiNG e adiciona lifecycle.

**Foco e rota:** XTEST injeta no X server e pode usar a janela atual/focada; windowfocus depende do window manager. A rota para Win32 user32, registered hotkeys e Wine é uma tradução adicional. No modelo gamescope/Game Mode, o caminho pode ser Xwayland, múltiplos displays ou keyboard grab; localizar a janela certa não é garantido.

**Dependências/permissões:** DISPLAY, autorização X (XAUTHORITY/cookie), XTEST e xdotool/Xlib. Um X11 display ausente ou errado falha antes de chegar ao trainer.

**Prefixo/container/Game Mode:** não seleciona wineserver/prefixo/container. A cadeia X11 de um processo Wine pode ser diferente da do processo do plugin. Compatibilidade física com a janela FLiNG no Game Mode é **não validada**.

**Estado e risco:** nenhum estado real; risco anti-cheat **inferido baixo/médio**, não validado.

**Veredito:** útil apenas em um desktop X11 conhecido; frágil como contrato Steam Deck/Game Mode e não recomendada para a primeira fase.

### 9. Wayland virtual keyboard/gamescope

**Modelo:** cliente Wayland usa um protocolo de teclado virtual, ou tenta o protocolo privado de input method do gamescope, para emitir eventos no seat.

**Pontos fortes:** pode evitar X11 e conversar com o compositor da sessão atual; um cliente embutido no backend poderia evitar um EXE Windows auxiliar.

**Limites:** o protocolo virtual keyboard é extensão compositor-dependente, precisa de seat/keymap e pode ser recusado. O protocolo gamescope-input-method é privado e serve ao input method/Steam keyboard, não é uma API pública para um plugin escolher uma janela Windows. Wayland não dá ao cliente acesso às superfícies de outros clientes como se fossem HWNDs.

**Permissões/dependências:** socket WAYLAND_DISPLAY, suporte/implementação específica e política de autorização do compositor; não basta instalar uma biblioteca cliente. O suporte exato da imagem SteamOS/gamescope usada pelo Deck é **não validado**.

**Prefixo/container/Game Mode:** não conhece wineserver ou prefixo. O compositor define foco; um trainer minimizado ou uma janela fora da superfície ativa pode não receber nada.

**Estado e risco:** nenhum estado real; risco anti-cheat **inferido baixo/médio**, não validado.

**Veredito:** não usar o protocolo privado como dependência do Trainer Relay. Só merece uma prova experimental separada se o objetivo mudar para “input global do compositor”, não “hotkey dirigida ao FLiNG”.

### 10. Steam Input/Steamworks

**Modelo:** mapear um botão do controle a uma ação/tecla usando Steam Input, sem iniciar outro helper próprio.

**Pontos fortes:** integra naturalmente ao Game Mode e pode não adicionar um processo controlado pelo Trainer Relay; Steam já possui seus próprios serviços/overlay.

**Limites:** Steam Input é orientado a ações/configuração do jogo, com manifest e AppID. A API ISteamInput não é uma ponte para o HWND ou RegisterHotKey de um trainer externo. A emulação de keyboard/mouse continua dependente do alvo/foco da configuração. Para shortcuts Epic/GOG da UniFiDeck, não há no contrato local uma integração Steamworks que represente o FLiNG.

**Processo/prefixo:** nenhum helper adicional do Relay é conceitualmente necessário, mas o Relay não controla o pipeline interno Steam de forma documentada. Também não escolhe o mesmo wineserver/prefixo do trainer.

**Game Mode/confiabilidade:** bom encaixe para input do jogo; confiabilidade para FLiNG externo **baixa/não validada**. O foco pode permanecer no jogo e a hotkey nunca chegar ao trainer.

**Estado e risco:** não fornece estado do cheat. Risco anti-cheat adicional **inferido baixo/médio**, não validado.

**Veredito:** não é solução para FLiNG não modificado; pode ser suporte opcional apenas quando o jogo/trainer cooperar com um action manifest ou quando testes físicos comprovarem uma rota específica.

### 11. Wine server, DLL e remote thread

**Modelo A — wineserver:** usar a coordenação do wineserver/mesmo prefixo como se fosse um barramento de comandos.

wineserver coordena serviços internos dos processos Wine; não enumera hotkeys FLiNG, não expõe o catálogo do trainer e não oferece toggle/state API. runinprefix reduz a chance de iniciar em uma sessão Wine separada, mas não converte o server interno em protocolo público.

**Modelo B — DLL/remote thread:** um injector abre o processo, aloca/escreve memória, carrega uma DLL ou cria uma thread remota dentro do trainer/jogo.

**Processos e permissões:** normalmente requer um injector transitório ou residente, direitos de processo e DLL compatível com arquitetura/ABI. A cadeia precisa enxergar o processo no mesmo container/pid namespace e atravessar as permissões Wine/Windows. Um helper Linux não passa a ter OpenProcess só por estar no mesmo prefixo; em geral ainda é necessário código Windows/Wine ou uma técnica nativa de processo.

**Foco/Game Mode:** não depende de foco visual e pode funcionar headless, mas depende de processo, endereço, loader, sincronização e momento corretos. Game Mode não reduz a fragilidade.

**Estado e risco:** pode obter estado e controlar memória se o código conhecer internals específicos; não há descoberta genérica. Risco anti-cheat **inferido alto**, além de instabilidade, falsos positivos de segurança, deadlock e quebra com atualizações.

**Veredito:** rejeitar para FLiNG arbitrário no Trainer Relay. Só é aceitável como pesquisa isolada, autorizada e build-specific, preferencialmente substituída por integração cooperativa.

### 12. Leitura/controle de memória e observer one-shot

**Modelo:** após um comando, um observer transitório lê o processo do jogo e procura uma assinatura/bytes conhecidos; uma variante de controle escreve a memória para aplicar/desfazer o efeito.

**Leitura:** [ReadProcessMemory](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-readprocessmemory) exige acesso de leitura e uma região válida. Um observer pode confirmar um patch conhecido em um jogo/build conhecido, sem foco e sem UI. Isso é estado do **efeito no jogo**, não necessariamente estado visual ou intenção do FLiNG.

**Controle:** [WriteProcessMemory](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-writeprocessmemory), VirtualAllocEx e remote thread exigem direitos de escrita/operação e conhecimento do layout. É mais invasivo, mais sensível a atualização e de risco anti-cheat **inferido alto**. Não deve ser usado como fallback automático para um executável arbitrário.

**Processo/prefixo/container:** um observer Windows lançado com runinprefix é transitório e tem a melhor chance de compartilhar a visão Wine do jogo. Um observer Linux poderia inspecionar PIDs/proc se permissões e namespace permitirem, mas precisa traduzir processo Wine, endereço e semântica do patch; isso não foi validado. Prefixo não substitui direitos de memória.

**Empacotamento/Game Mode:** requer tabela de build, assinatura, arquitetura, timeout, tolerância a ausência e rollback; pode ser headless. A validação física precisa provar endereço, bytes esperados, reversão, crash safety e que o jogo não está em uma fase transitória.

**Estado real:** **sim, condicionalmente**, para um efeito conhecido e verificado. Não obtém automaticamente o catálogo, rótulos ou hotkeys do FLiNG.

**Veredito:** observer read-only é uma fase posterior opcional para builds curados; controle de memória não é recomendação para FLiNG externo.

## Critério de “sem terceiro processo”

Há três cenários que não devem ser confundidos:

1. **Sem EXE auxiliar residente:** possível com helper Windows one-shot; ainda há um processo Windows transitório.
2. **Sem novo processo Windows, mas usando o backend Decky existente:** teoricamente possível com uinput, XTest ou cliente Wayland embutidos; não há garantia de que o evento seja roteado para o FLiNG, principalmente em Game Mode.
3. **Sem sequer um terceiro processo transitório e com FLiNG não modificado:** não há uma API documentada que faça o backend Linux chamar user32/RegisterHotKey em outro processo Wine. Steam Input e gamescope são componentes existentes, mas não oferecem ao Relay o alvo e acknowledgement necessários.

Logo, a resposta operacional é **não**. Uma exceção só seria uma coincidência experimental — por exemplo, uma hotkey global do FLiNG receber um evento que o Steam já emite — e não deve ser prometida sem teste por build, prefixo, runtime e Game Mode.

## Matriz comparativa

Legenda: Sim significa capacidade documentada/condicional; Não significa que o mecanismo não oferece a capacidade; Cond. significa que depende de integração, build ou teste físico; — significa que o conceito não se aplica diretamente.

| Alternativa | Processo extra | Foco/janela | Mesmo wineserver/prefixo/container | Permissões/dependências/empacotamento | Game Mode | Confiabilidade para FLiNG não modificado | Anti-cheat adicional | Estado real | Veredito |
|---|---|---|---|---|---|---|---|---|---|
| Helper Windows one-shot + UMU runinprefix | Transitório; não residente | SendInput depende de foreground; PostMessage pode ser tentado | **Cond. forte**: usar reentry exato local | EXE, hash/build, UMU/Proton, UIPI | **Não validado** | Média-baixa até teste físico | Inferido baixo/médio | Não | Melhor fase 1; requested/unknown |
| Helper residente + IPC | Residente | Pode serializar foco/HWND, mas não elimina UIPI | **Cond. forte** | EXE, IPC, lifecycle, heartbeat, cleanup | Condicional | Média se muitos comandos; sem estado FLiNG | Inferido baixo a alto conforme implementação | Não sem protocolo | Só se frequência justificar ou trainer cooperar |
| Integração/modificação do trainer | Pode ser zero helper adicional | Comando direto, sem foco | Condicional; ainda lançar no runtime correto | Rebuild, manifest, protocolo, autenticação local | Condicional | Alta para trainer próprio; inaplicável a FLiNG fechado | Inferido baixo adicional | **Sim** | Melhor produto para código sob controle |
| SendInput | Requer chamador Windows | Foreground/desktop/UIPI | Requer helper no mesmo reentry para coerência | user32, integridade, layout de tecla | Não validado | Média-baixa | Inferido baixo/médio | Não | Transporte one-shot recomendado |
| PostMessage | Requer chamador Windows | HWND, mas não equivale a WM_HOTKEY/input físico | Requer mesma sessão Wine para achar HWND | user32, UIPI, marshalling | Não validado | Baixa-condicional | Inferido baixo | Não | Fallback experimental |
| UI Automation | Cliente Windows, transitório/residente | Elementos/provider, não hotkey global | Requer UIA/COM na sessão correta | UIAutomationCore, provider, UIAccess | Não validado | Baixa para UI customizada/minimizada | Inferido baixo | Visual condicional, jogo não | Diagnóstico apenas |
| Linux uinput/evdev | Pode ser backend existente ou helper Linux | Seat/compositor; sem HWND | Não | /dev/uinput, kernel, udev/grupo/root conforme imagem | Não validado | Baixa/unknown | Inferido baixo/médio | Não | Experimento global, não alvo FLiNG |
| X11/XTest/xdotool | xdotool transitório ou cliente embutido | X focus/window; Xwayland adicional | Não | DISPLAY, XAUTHORITY, XTEST/Xlib | Frágil/não validado | Baixa em Game Mode | Inferido baixo/médio | Não | Não usar como base |
| Wayland virtual keyboard/gamescope | Cliente transitório ou embutido | Seat/foco do compositor; sem HWND | Não | socket, protocolo suportado/autorizado | Não validado; gamescope protocol privado | Unknown | Inferido baixo/médio | Não | Não usar protocolo privado |
| Steam Input/Steamworks | Pode reutilizar Steam; sem helper Relay | Configuração/ação do jogo, não trainer externo | Não | Steam AppID, manifest, integração do jogo | Bom para o jogo; não para FLiNG | Baixa/não validada | Inferido baixo/médio | Não | Não é API de trainer |
| wineserver como API | Já existe, mas sem contrato | Nenhum alvo de hotkey | Coordena prefixo, não comandos | Wine interno | Irrelevante | Não | Unknown | Não | Não é solução |
| DLL/remote thread/injeção | Injector transitório/residente + DLL | Sem foco | Condicional; precisa ver processo/container | Direitos de processo, ABI, memória, DLL | Pode ser headless | Baixa/instável | **Inferido alto** | Condicional | Rejeitar para FLiNG arbitrário |
| Observer de memória one-shot | Transitório | Sem foco | Melhor com runinprefix; direitos ainda necessários | Assinatura/build, ReadProcessMemory, tabela | Condicional/não validado | Condicional por build | Inferido médio; escrita alto | **Sim, só efeito conhecido** | Fase posterior read-only |

## Recomendação em fases

### Fase 0 — contrato seguro antes de qualquer automação

- Tratar FLiNG como executável externo sem estado: perfil amarrado a game identity, nome, arquitetura quando conhecida, versão e SHA-256.
- Exibir apenas catálogo curado/documentado. Para o caso local BioShock 2, manter cobertura e exclusões explícitas; não inferir toda a tabela a partir de strings/imports.
- Separar command_requested, input_inserted, trainer_acknowledged, effect_verified, disabled e unknown. Nunca converter processo vivo, janela visível ou retorno de SendInput em enabled.
- Fail closed para hash/build desconhecido, processo ambíguo, prefixo errado, container não reentrado ou ausência de foco quando a rota exigir foco.

### Fase 1 — FLiNG não modificado, sem helper residente

- Prototipar um Windows helper one-shot mínimo, com uma única hotkey de um perfil conhecido e sem leitura/escrita de memória.
- Iniciá-lo pelo mesmo umu-run/runinprefix e pelo reentry UMU confirmado pelo Trainer Relay atual.
- Definir o resultado como requested/unknown; oferecer um botão separado de “verificar efeito” somente quando houver observer read-only curado.
- Testar fisicamente em Game Mode, por trainer/build: foco do FLiNG, hotkey sem modificador e com modificador, processo minimizado, troca jogo/FLiNG, reinício, Proton/runtime, encerramento e falha do helper.
- Não chamar uinput, XTest, Wayland privado ou Steam Input de substituto equivalente até existir um teste reproduzível que prove o alvo.

### Fase 2 — observer read-only curado

- Para poucos jogos/builds estáveis, implementar apenas verificação de memória conhecida, com assinatura, bytes esperados, timeout, proteção contra PID reutilizado e estado unknown quando a leitura falhar.
- Preferir que o trainer próprio faça a verificação e publique o resultado; para FLiNG, manter a verificação como evidência do efeito no jogo, nunca como descoberta automática da UI/hotkeys.
- Não incluir WriteProcessMemory, remote thread ou DLL injection no caminho padrão.

### Fase 3 — protocolo cooperativo para trainers próprios

- Gerar um manifest versionado junto do trainer, com catálogo, hotkey canônica, dependências, build do jogo e estado.
- Expor no próprio trainer comandos idempotentes, acknowledgement, session id, timestamp, enabled/disabled/failed/unknown e resultado de verificação interna.
- Fazer o Relay mostrar estado somente quando a resposta corresponder ao mesmo trainer, hash, jogo e sessão. Este caminho pode eliminar o helper adicional, pois o endpoint vive no trainer, mas não altera a situação do FLiNG fechado.

### Decisão final

Adotar a **Fase 1** como alternativa prática de menor impacto para FLiNG não modificado, aceitando explicitamente um processo Windows transitório e estado desconhecido. Investir na **Fase 3** para obter estado real e eliminar a dependência de foco. Manter uinput, X11/XTest, Wayland/gamescope, Steam Input e injeção Wine fora do contrato principal até cada rota demonstrar, no hardware e runtime alvo, foco/alvo/ack/efeito/rollback. Para a pergunta estrita do usuário, a resposta permanece: **não existe hoje uma opção primária, genérica, documentada e validada que acione um FLiNG não modificado sem sequer um terceiro processo transitório**.
