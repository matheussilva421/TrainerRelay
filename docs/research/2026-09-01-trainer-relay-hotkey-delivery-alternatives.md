# Trainer Relay — alternativas para entrega de hotkeys FLiNG via Decky

**Data:** 2026-09-01
**Escopo:** pesquisa de mecanismos para a sidebar do Decky acionar hotkeys conhecidas de trainers FLiNG em jogos Windows executados no Steam Deck, evitando um terceiro processo Windows residente.
**Fontes:** somente documentação oficial, especificações e código-fonte upstream, além da evidência local explicitamente identificada.
**Decisão local incorporada:** os FLiNG x86 analisados fazem polling de `GetAsyncKeyState`; `Tools/FlingDeckWrapper/tests/FakeFlingTrainer` reproduz esse comportamento.

## Resumo executivo

A recomendação para os FLiNG existentes é um **helper Windows efêmero, lançado pelo caminho UMU/Proton já usado pelo Trainer Relay, que injeta a sequência com `SendInput` e termina imediatamente**. Ele não mantém um terceiro processo Windows residente. É o caminho genérico com melhor compatibilidade provável com o polling de `GetAsyncKeyState`, mas continua sendo uma ação **best effort**: `SendInput` confirma apenas que eventos foram aceitos na fila de entrada, não que o trainer aplicou o cheat.

O backend nativo do Decky deve ser a camada de orquestração: resolver sessão, validar jogo/prefixo/trainer/hash, lançar o helper, registrar resultado e expor `requested`/`unknown`. Ele não é, por si só, um mecanismo de input Windows.

Para trainers próprios, a opção preferida é um **protocolo cooperativo embutido no próprio trainer**, com catálogo versionado, comando, acknowledgement e estado verificado pelo processo que possui o patch. Essa solução elimina a dependência de foco e de semântica de teclado e oferece a melhor observabilidade sem criar um sidecar Windows residente.

`PostMessage`/`SendMessage` não devem ser o transporte padrão para FLiNG: eles entregam mensagens a uma janela, enquanto o alvo local lê o estado assíncrono. Podem funcionar em um trainer que deliberadamente processa `WM_KEYDOWN` ou `WM_HOTKEY`, mas isso é uma hipótese incompatível com o FakeFlingTrainer e não deve ser inferida para FLiNG arbitrário.

`uinput`, XTest e eventuais extensões de emulação Wayland são planos experimentais de host: podem produzir entrada mais parecida com um evento físico, mas dependem de toda a cadeia SteamOS → Gamescope/Xwayland/Wayland → Wine. Têm maior superfície de entrega, permissões e risco de afetar outros consumidores.

Um motor próprio de patches sem trainer pode remover a dependência de hotkeys, mas é uma solução por jogo/build, de alto risco operacional e de manutenção. Deve permanecer fora do caminho genérico do Trainer Relay.

## Evidência decisiva: o alvo não consome apenas mensagens

O contrato relevante é o bit alto de `GetAsyncKeyState`: a documentação Microsoft descreve uma consulta ao estado atual da tecla; o bit baixo, que indica pressão desde a consulta anterior, é explicitamente pouco confiável em multitarefa. A API é distinta do modelo de mensagens de teclado descrito pela própria Microsoft. Consulte [`GetAsyncKeyState`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getasynckeystate) e [`Keyboard Input`](https://learn.microsoft.com/en-us/windows/win32/inputdev/about-keyboard-input).

O achado local torna essa distinção concreta:

- `C:\Users\slvma\Downloads\Github\Mods\Tools\FlingDeckWrapper\tests\FakeFlingTrainer.cs` importa `GetAsyncKeyState`, consulta `Ctrl`/`Alt` e as teclas configuradas usando `& 0x8000`, e detecta a transição pressionada com `_prevDown`.
- `C:\Users\slvma\Downloads\Github\Mods\Tools\FlingDeckWrapper\src\WindowsInputSender.cs` usa `SendInput` e verifica a quantidade de eventos aceitos.
- O código local dos trainers próprios também contém caminhos de `RegisterHotKey`/`WM_HOTKEY`, mas isso é uma implementação cooperativa específica; não transforma o polling de FLiNG em um consumidor de mensagens.

Portanto, há três classes diferentes de entrega:

1. **Entrada de sistema/hardware-like:** `SendInput`, uma entrada XTest que realmente atravesse o driver X11/Wine, ou um dispositivo virtual `uinput`. Esses caminhos podem atualizar o estado que o Wine apresenta a `GetAsyncKeyState`, sujeito à cadeia de runtime.
2. **Mensagem dirigida à janela:** `WM_KEYDOWN`, `WM_KEYUP`, `WM_CHAR` ou `WM_HOTKEY` via `PostMessage`/`SendMessage`. Isso chama ou enfileira o procedimento da janela; não é evidência de que a tabela de estado assíncrono foi atualizada.
3. **Comando de aplicação:** IPC/protocolo próprio ou automação de controle. Não simula teclado e pode oferecer acknowledgement, mas requer cooperação do trainer ou de sua UI.

A documentação Microsoft separa explicitamente `SendInput` das mensagens de janela: [`SendInput`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput) injeta eventos de teclado/mouse no fluxo de entrada, enquanto [`PostMessageW`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-postmessagew) e [`SendMessageW`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendmessagew) operam sobre uma fila/procedimento associado a `HWND`. Assim, a conclusão “mensagem não atualiza o async state” é uma **inferência arquitetural forte e aplicável ao alvo local**, não uma promessa de que nenhuma implementação Windows jamais poderá ter efeitos colaterais adicionais.

## Como o caminho recomendado atravessa Proton/Wine

No Wine upstream, `keybd_event` constrói um `INPUT` e chama `NtUserSendInput` em [`dlls/user32/input.c`](https://github.com/wine-mirror/wine/blob/master/dlls/user32/input.c). A implementação de [`NtUserSendInput`](https://github.com/wine-mirror/wine/blob/master/dlls/win32u/input.c#L606-L759) envia a entrada ao servidor Wine como mensagem de hardware injetada. A fila de teclado em [`server/queue.c`](https://github.com/wine-mirror/wine/blob/master/server/queue.c#L2132-L2279) trata a entrada de hardware, atualiza o fluxo de teclado e produz tanto input bruto quanto mensagens legadas quando aplicável.

Isso não prova sozinho que todo build FLiNG reagirá no SteamOS: o driver Wine, a sessão gráfica, a versão Proton, a janela ativa e a implementação do trainer ainda precisam ser validados. Mas é o caminho upstream que mais se aproxima do que o FakeFlingTrainer consulta; `PostMessage(WM_KEYDOWN)` começa depois desse estado e não o substitui.

O UMU upstream documenta que `umu-run` executa o binário com `WINEPREFIX`, Proton e argumentos especificados dentro do container do Steam Runtime, sem exigir que o programa esteja na biblioteca Steam ([README do UMU](https://github.com/Open-Wine-Components/umu-launcher)). No código de [`umu_run.py` 1.4.4](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_run.py), `set_env` prepara `WINEPREFIX`/`STEAM_COMPAT_DATA_PATH`, e `build_command` pode reencontrar o serviço do mesmo prefixo quando `UMU_CONTAINER_NSENTER=1`, usando `PROTON_VERB=runinprefix`. Isso corresponde ao caminho de reentrada já adotado pelo Trainer Relay.

O Proton upstream é uma distribuição baseada em Wine ([README do Proton](https://github.com/ValveSoftware/Proton)); seu script de execução mantém o prefixo e inicia processos com as variáveis de compatibilidade ([`proton`](https://github.com/ValveSoftware/Proton/blob/proton_11.0/proton)). Nem Proton nem UMU definem um protocolo de controle de trainer. Eles resolvem execução, prefixo e container; a semântica de hotkey continua sendo Win32/Wine ou do aplicativo.

## Matriz comparativa

Legenda: **alta/média/baixa** é adequação para este alvo, não garantia de sucesso; `estado` mede o que Relay consegue provar depois do comando.

| Alternativa | Chega ao caminho de `GetAsyncKeyState` | Foco/janela | Proton/Wine e permissões | Confiabilidade e observabilidade | Custo e segurança | Veredicto |
|---|---|---|---|---|---|---|
| **Helper Windows efêmero via UMU + `SendInput`** | **Alta provável**: injeta no fluxo de entrada do Wine, ao contrário de uma mensagem dirigida | Não é `HWND`-targeted; depende da sessão/desktop e do foreground. Não tomar foco automaticamente por padrão | Boa aderência se usar o mesmo `WINEPREFIX`, `PROTONPATH`, container e `runinprefix`; normalmente roda como usuário Deck, sem root | Evento aceito e exit code são observáveis; aplicação do cheat não. Startup por ação é um custo, mas não há lifecycle residente | Médio: allowlist/hash/capability são importantes; a entrada ainda é global ao desktop | **Recomendação imediata para FLiNG** |
| **Helper Windows residente + IPC** | **Alta**, com mais tempo para manter contexto/foco e retry | Pode rastrear janela/foreground, mas adiciona handles/PIDs obsoletos e risco de roubo de foco | Compatibilidade boa; exige manter um processo Windows, canal e lifecycle confiáveis | Pode oferecer ack se o trainer cooperar; caso contrário continua sem estado real | Alto custo permanente, superfície IPC e persistência | **Fallback; viola o objetivo principal** |
| **`uinput` para dispositivo virtual** | **Média/experimental**: só chega ao async state se atravessar corretamente kernel, compositor, Gamescope/Xwayland e Wine | Sem foco no kernel; o compositor decide roteamento e pode consumir/remapear | Kernel permite emular dispositivo via `/dev/uinput`; acesso é controlado por permissões do dispositivo e varia no SteamOS. Evitar root por padrão | Pode observar a criação/envio do dispositivo, mas não o efeito no trainer; host-wide | Médio/alto: permissões e impacto em todos os consumidores | **Fallback de host, não default** |
| **`evdev`** | **Nenhuma por si só**: `evdev` é interface para consumir eventos do kernel, não API de injeção | Não se aplica | Normalmente exige acesso de leitura a `/dev/input/event*` para observar; não substitui `uinput` | Bom para diagnóstico de eventos físicos, zero ack do trainer | Baixo para leitura, mas sensível em privacidade/permissões | **Diagnóstico, não entrega** |
| **X11/XTest** | **Média/condicional**: pode funcionar se o evento fake entrar no display X11 que o driver Wine usa | Precisa de `DISPLAY`/autorização e do display correto; Xwayland/Gamescope podem mudar a topologia | XTest só cobre X11; não há garantia de que o alvo seja o X server certo em Game Mode | Fácil de emitir, difícil provar destino/efeito; Gamescope pode consumir teclas | Baixo custo, mas risco de atingir outras janelas e depender de Xauthority | **Ferramenta experimental/diagnóstica** |
| **Wayland core** | **Baixa/nula como API genérica**: o core entrega teclado do compositor ao cliente focado, não permite a um cliente enviar teclado a outro | Foco é propriedade do compositor/seat; não há target arbitrário pelo cliente | Não exige root para ser cliente, mas não oferece a operação necessária | Sem mecanismo genérico de envio ou ack | Baixo custo aparente, mas não resolve o problema | **Descartar como transporte genérico** |
| **Gamescope / protocolo privado / libei quando disponível** | **Média/condicional**: depende de suporte, autorização e integração do compositor; não equivale automaticamente a Wine async state | Gamescope pode capturar hotkeys e redirecionar eventos; sua configuração é parte do resultado | O protocolo `gamescope-input-method` é privado e voltado a input method/text composition; libei requer compositor/autorização e pode não estar habilitado | Estado do compositor não é estado do trainer | Médio: integração frágil e superfície privilegiada | **Não basear o produto nisso** |
| **`PostMessage`/`SendMessage`** | **Baixa para FLiNG polling**: entrega mensagem; não simula a tabela assíncrona consultada | Requer `HWND`/thread corretos; `SendMessage` pode bloquear no procedimento alvo; ambos sofrem limites/UIPI | Não precisa de Proton extra, mas atravessa somente o message path do Wine | Retorno da API é entrega à janela, não aplicação; pode funcionar para `WM_HOTKEY` deliberado | Baixo custo, porém falsa confirmação e handles frágeis | **Não usar para FLiNG por padrão** |
| **Backend nativo do Decky** | Não injeta sozinho; orquestra um dos mecanismos acima | Pode acompanhar a sessão e não deve presumir foco Windows | Decky executa backend em processo isolado; com `flags: []` o plugin atual não pede root. Root ampliaria muito o risco | Excelente lugar para lifecycle, allowlist, logs e `requested/unknown`; não inventa estado | Baixo custo incremental; manter privilégios mínimos | **Camada obrigatória de controle, não transporte** |
| **Protocolo cooperativo embutido em trainer próprio** | Não depende de teclado nem de async state | Não depende de foreground/`HWND` | Pode usar IPC local escolhido pelo próprio trainer; requer alteração do trainer, não root do Decky | **Alta**: ack, estado, build, timestamp e verificação do patch no dono | Custo inicial médio/alto, segurança controlável e sem sidecar Windows | **Melhor solução para trainers próprios** |
| **Automação de UI / UI Automation** | **Baixa** para o alvo: invoca UI, não cria async key state | Pode chamar `Invoke` sem foco se houver provider; controles customizados/minimizados podem não expor árvore | UIA em Wine/Proton e providers de trainers customizados são incertos | Pode observar estado visual exposto, não o patch no jogo; risco de clicar no controle errado | Médio custo de implementação, superfície de UI instável | **Fallback específico, não default** |
| **Motor próprio de patches sem trainer** | Não se aplica: altera o jogo diretamente | Não depende de janela/foco depois de attached | Por jogo/build, assinatura e processo; permissões e compatibilidade muito mais delicadas | Pode oferecer estado direto se implementar verificação própria, mas alto risco de erro | **Muito alto**: memória, crashes, anti-cheat, corrupção e manutenção | **Pesquisa/último recurso; fora do caminho genérico** |

## Análise das alternativas

### 1. Helper Windows efêmero via UMU/Wine `SendInput`

**Forma:** a sidebar envia um comando já resolvido por um adapter hash-bound. O backend Decky inicia um pequeno `TrainerRelay.InputHelper.exe` pela mesma reentrada UMU usada para o trainer, com uma chord validada; o helper pressiona modificadores e tecla, libera tudo em `finally`, registra a contagem retornada por `SendInput` e sai.

**Por que é o melhor caminho genérico:** o helper chama o mesmo `user32!SendInput` que o código local do wrapper já usa. No Wine upstream, isso entra na camada de input injetado do wineserver. É a única alternativa genérica da lista, além das rotas host que precisam atravessar o compositor, que modela uma entrada de teclado em vez de apenas chamar o `WndProc` da janela.

**Foco:** `SendInput` não seleciona um `HWND`; a entrada vai para a sessão/desktop e o foco/foreground vigente. `SetForegroundWindow` dirige teclado à janela, mas a Microsoft documenta restrições para impedir que qualquer processo roube o foreground ([`SetForegroundWindow`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow)). O Relay deve evitar roubar foco automaticamente, não assumir que o trainer visível é o alvo e exigir validação de que a sessão do jogo está ativa. O polling de `GetAsyncKeyState` pode ser vantajoso por não depender da janela do trainer, mas o comportamento exato no Proton precisa de teste com o FakeFlingTrainer e com o build FLiNG real.

**Limitações:**

- `SendInput` está sujeito a UIPI no Windows; no Proton, a tradução passa pelas regras do Wine e pelo desktop do prefixo.
- A documentação Microsoft diz que o retorno indica quantos eventos foram inseridos; não é acknowledgement do aplicativo. O estado do cheat deve permanecer `unknown`/`requested` para FLiNG.
- O helper deve enviar key-up de todos os modificadores mesmo em erro, usar sequência determinística e impedir chords fora da allowlist.
- O custo de iniciar UMU/Proton por comando deve ser medido; como o jogo/trainer já está no prefixo, `runinprefix` pode evitar um segundo ciclo de jogo, mas não se deve assumir latência sem medir.

**Contrato recomendado do helper:** entrada estruturada e restrita (`game_id`, adapter id/hash, virtual-key/scancode, modificadores, correlation id), nunca shell ou texto arbitrário; saída pequena com `accepted_count`, erro, duração, PID do helper e versão; nenhum processo fica aguardando depois da sequência.

### 2. Helper Windows residente/IPC

Um processo Windows residente poderia manter um canal no prefixo, descobrir janelas uma vez, controlar retry e talvez receber estado de um trainer cooperativo. Ele reduz o custo de startup e pode tornar o envio menos sensível a timing.

O custo é estrutural: lifecycle em boot/saída de jogo, stale PID/`HWND`, travamento, atualização, IPC autenticado, encerramento e uma nova superfície que aceita comandos. Se o helper só chama `SendInput`, ele ainda não sabe se FLiNG mudou o patch. Se ele faz introspecção ou memória, o risco cresce. Como o requisito é evitar um terceiro processo Windows residente, esta opção só deve existir como fallback explicitamente habilitado para um caso comprovado de latência ou compatibilidade.

Uma alternativa aceitável para trainers próprios é o IPC **dentro do processo do trainer**: nesse caso não há sidecar Windows; o processo que possui o estado responde ao backend. Isso é o protocolo cooperativo da seção adiante, não um helper residente genérico.

### 3. Linux `uinput` e `evdev`

O kernel Linux define `evdev` como a interface genérica para consumir eventos de entrada e recomenda-a para usuáriospace ([documentação da arquitetura de input](https://www.kernel.org/doc/html/latest/input/input.html)). Isso é observação, não injeção. O módulo [`uinput`](https://www.kernel.org/doc/html/latest/input/uinput.html) permite que userspace crie um dispositivo virtual e emule eventos; a própria documentação recomenda `libevdev` como wrapper menos propenso a erros.

`uinput` é mais próximo de uma origem física no host que `PostMessage`, mas não é um túnel direto para um prefixo Wine. O caminho seria:

`Decky backend → /dev/uinput → kernel → libinput/compositor/Gamescope → Xwayland ou cliente Wayland → driver Wine → wineserver → GetAsyncKeyState`.

Qualquer elo pode remapear, consumir, duplicar ou direcionar o evento. A existência de `/dev/uinput` e suas permissões, grupo e regras udev são propriedades do sistema SteamOS; o plugin atual não deve ganhar `root` só para tornar isso possível. Também não há seleção natural de “somente este trainer”: o dispositivo é global para os consumidores da sessão.

O caminho pode ser um fallback de diagnóstico se um protótipo demonstrar, no Game Mode real, que o evento atravessa Gamescope até o FakeFlingTrainer. Deve ser one-shot ou mantido pelo backend já existente, nunca um novo daemon sem necessidade, e deve ter capability explícita porque um emissor uinput comprometido pode simular teclas para todo o desktop.

### 4. X11/XTest, Wayland e Gamescope

#### X11/XTest

A especificação upstream do [XTEST Extension](https://xorg.freedesktop.org/archive/X11R7.7/doc/xextproto/xtest.html) define `XTestFakeInput` para simular eventos core como `KeyPress` e `KeyRelease`. Se o `DISPLAY` for o X11/Xwayland correto e o driver Wine consumir o evento como input normal, ele pode atualizar o estado no caminho de Wine; isso precisa ser medido e não é garantido pelo contrato de XTest.

No Steam Deck em Game Mode, “o display correto” pode ser uma instância Xwayland sob Gamescope, não a sessão X11 esperada por uma ferramenta desktop. São necessárias `DISPLAY`, autorização X e descoberta de topologia. O driver X11 do Wine também traduz códigos/layouts para o input do Wine ([`winex11.drv/keyboard.c`](https://github.com/wine-mirror/wine/blob/master/dlls/winex11.drv/keyboard.c)); ele não oferece uma API genérica de “enviar para este prefixo/trainer”.

XTest é útil como experimento de compatibilidade, não como contrato de produto: a emissão é barata, mas destino, foco, display e observabilidade são frágeis.

#### Wayland core

O protocolo Wayland descreve `wl_keyboard` como um dispositivo do `wl_seat`; o compositor envia `enter`, `leave` e `key` ao surface com foco ([protocolo core](https://wayland.freedesktop.org/docs/html/apa.html)). O modelo de protocolo também deixa o compositor controlar foco e grabs ([Protocol book](https://wayland.freedesktop.org/docs/book/Protocol.html)). Um cliente Wayland comum recebe esses eventos; o core não define um método para um plugin enviar teclas arbitrárias a outro cliente.

Logo, “usar Wayland” não é uma solução de entrega por si só. Exige uma extensão do compositor ou uma camada de emulação autorizada.

#### Gamescope, protocolo privado e libei

Gamescope é o compositor/window manager usado no ecossistema SteamOS ([repositório ValveSoftware/gamescope](https://github.com/ValveSoftware/gamescope)). Seu código trata hotkeys, grabs e entrega de teclado ao seat; hotkeys próprias podem ser consumidas ou redirecionadas antes de um cliente receber o evento ([`src/wlserver.cpp`](https://github.com/ValveSoftware/gamescope/blob/master/src/wlserver.cpp)). Isso explica por que uma entrada que parece global no host não é automaticamente equivalente a uma entrada no Wine.

O arquivo [`gamescope-input-method.xml`](https://github.com/ValveSoftware/gamescope/blob/master/protocol/gamescope-input-method.xml) chama o protocolo de privado e voltado a input methods/composição de texto; clientes Wayland comuns não devem tratá-lo como API pública para hotkeys arbitrárias.

`libei` é uma possível camada upstream para emulação de input com participação do compositor ([documentação libei](https://libinput.pages.freedesktop.org/libei/) e [API de sender](https://libinput.pages.freedesktop.org/libei/api/group__libei-sender.html)). Ela foi desenhada com autorização e distinção entre sender/receiver, mas a disponibilidade e integração no SteamOS/Gamescope precisam ser demonstradas no dispositivo. Não deve ser dependência do Trainer Relay enquanto essa presença não for um fato validado.

### 5. `PostMessage` e `SendMessage`

`PostMessageW` coloca a mensagem na fila da thread que criou o `HWND`; `SendMessageW` chama o procedimento e pode bloquear até ele processar a mensagem. Ambos são mecanismos de janela, sujeitos a regras de integridade/UIPI e a detalhes de marshalling para mensagens customizadas; consulte as referências Microsoft de [`PostMessageW`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-postmessagew) e [`SendMessageW`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendmessagew).

Um trainer que registra [`RegisterHotKey`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey) e trata `WM_HOTKEY` no seu `WndProc` pode deliberadamente aceitar esse protocolo de janela. Isso explica o caminho dos trainers próprios locais. Não é, porém, o comportamento comprovado do FLiNG analisado: o FakeFlingTrainer consulta `GetAsyncKeyState` em polling. Enviar `WM_KEYDOWN`, `WM_KEYUP` ou um `WM_HOTKEY` sintético pode chamar o código da janela e ainda deixar o bit assíncrono que FLiNG consulta inalterado.

`SendMessage` é ainda pior como fallback cego porque o backend/bridge pode ficar preso no procedimento de uma janela que não bombeia mensagens ou que execute trabalho lento. O sucesso do envio não significa que o cheat foi ativado. Para o alvo local, a classificação correta é **incompatível até teste específico em contrário**.

### 6. Integração nativa no backend Decky

Decky é o lugar certo para controle de sessão, configuração, autorização e telemetria. O código upstream do loader inicia o plugin backend em processo separado e despacha chamadas por socket local em [`plugin.py`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/plugin.py#L17-L129). [`SandboxedPlugin`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/plugin/sandboxed_plugin.py#L51-L127) prepara ambiente, usuário efetivo, módulos e servidor; o dispatch de métodos está em [`on_new_message`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/plugin/sandboxed_plugin.py#L178-L200).

O `plugin.json` atual do Trainer Relay usa `flags: []`. Adicionar `root` para abrir uinput ou manipular processos seria uma mudança de segurança de alto impacto e não é necessário para lançar um helper UMU como usuário do Deck. O backend deve operar com privilégio mínimo.

Integração nativa não remove o processo do próprio Decky; ela remove a necessidade de um **terceiro Windows residente**. É apropriado que o backend:

- associe o comando a `store:game_id`, prefixo, PID/starttime, trainer e hash exatos;
- recuse sessão ambígua, jogo encerrado, prefixo divergente ou adapter desconhecido;
- lance o helper efêmero via reentrada UMU ou escolha um transport autorizado;
- registre `accepted_count`, exit code, duração e correlation id sem declarar o cheat ativo;
- exponha `requested`, `unknown`, `stale` e `failed` de modo explícito;
- limpe processos e key-up pendentes quando a sessão terminar.

O backend atual tem RPCs de configuração, status, retry e diagnóstico, mas não tem ainda uma API de comando/estado de cheat. Esta pesquisa recomenda adicionar essa camada somente junto com o contrato de confiança descrito aqui, não inferir estado de processos ou janelas existentes.

### 7. Protocolo cooperativo embutido em trainers próprios

Esta é a melhor solução para os trainers cujo código está sob controle do projeto. O trainer já possui o catálogo, a tecla, o `CheatRuntime.IsEnabled` e a lógica que verifica bytes do processo do jogo. O Relay não deve duplicar essa lógica.

Um contrato mínimo poderia ser:

- `hello`: `protocol_version`, `trainer_id`, build/hash, `session_id`, catálogo e capabilities;
- `list`: ids estáveis, label, hotkey visual, dependências, conflitos e estado inicial;
- `set`/`toggle`: `command_id`, cheat id, operação desejada e precondições;
- `ack`: `command_id`, `accepted`/`rejected`, estado resultante, timestamp e motivo;
- `state`: `enabled`, `disabled`, `failed`, `unknown` ou `stale`, com evidência de verificação do patch;
- `bye`/heartbeat: validade da sessão e encerramento seguro.

O canal pode ser um IPC local escolhido pelo trainer, desde que tenha framing, timeout, versão, autenticação/capability por sessão e não aceite comandos arbitrários. O processo que altera a memória deve continuar sendo o verificador da própria alteração. Assim, a sidebar mostra estado real e não apenas “uma tecla foi injetada”.

Esse protocolo não ajuda um FLiNG fechado sem cooperação. Para FLiNG, o adapter conhecido deve continuar estático, hash-bound e explicitamente `best effort`.

### 8. Automação de UI

Microsoft UI Automation oferece acesso programático a elementos quando a aplicação expõe um provider apropriado ([UI Automation overview](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-uiautomationoverview)). Padrões como `Invoke` e `Toggle` descrevem operações e propriedades suportadas ([control patterns](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-controlpatternsoverview)); propriedades como nome, accelerator key e estado dependem do provider ([properties](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-propertiesoverview)).

Isso pode ser útil para um trainer próprio ou uma versão FLiNG que exponha controles Win32 acessíveis. Não é equivalente à tecla: invocar um botão não precisa atualizar `GetAsyncKeyState`; uma UI minimizada, custom-drawn ou sem provider pode não expor o controle; e estado visual do trainer não prova o estado do patch no jogo. UI Automation em Wine/Proton adiciona outra incerteza de compatibilidade. Deve ser um adapter experimental por trainer, nunca a camada genérica.

### 9. Motor próprio de patches sem trainer

Esta opção radical substitui a entrega de hotkey por uma implementação própria que localiza o processo do jogo e aplica/remove patches. Ela poderia oferecer estado direto, evitar janela/foco, não depender de FLiNG e não deixar um trainer Windows residente.

O custo é muito maior e não é uma alternativa genérica:

- cada jogo e build precisa de assinaturas, offsets, invariantes e teste físico próprios;
- ASLR, atualizações, múltiplos executáveis, threads e timing tornam a aplicação frágil;
- erro de assinatura ou restauração pode causar crash, corrupção de save ou estado parcial;
- acesso a memória/injeção aumenta o impacto de segurança e pode interagir com anti-cheat, termos do jogo e suporte;
- uma nova versão precisa fail closed até receber adapter e validação independentes.

Se algum dia for aprovado para um jogo específico, o mínimo de segurança é hash/fingerprint exato, validação de bytes antes da escrita, patch reversível, escopo de processo restrito, logs sem conteúdo sensível, restauração em saída e bloqueio para builds desconhecidos. A categoria deve aparecer no produto como **por-jogo/build, alto risco, pesquisa**, não como “alternativa de hotkey FLiNG”.

## Recomendação de arquitetura

### Fase A — FLiNG existente, sem processo Windows residente

1. Manter catálogo manual/adapter conhecido, com hash SHA-256 do trainer e identidade exata do jogo/build. Não tentar descobrir hotkeys de um `.exe` arbitrário.
2. Acrescentar no backend Decky um comando `send_known_hotkey` que só aceite ids/chords do adapter validado.
3. Lançar `InputHelper.exe` por UMU com o mesmo contexto do jogo: `WINEPREFIX` ancorado no compatdata root, `PROTONPATH`, `STEAM_COMPAT_DATA_PATH` e reentrada `UMU_CONTAINER_NSENTER=1`/`PROTON_VERB=runinprefix` conforme o contrato existente.
4. Usar `SendInput` com ordem explícita de key-down/key-up, tratamento de modifiers e `finally` para liberar qualquer tecla. O helper deve terminar após a sequência.
5. Não usar `PostMessage` como fallback silencioso. Se `SendInput` falhar, informar falha; não trocar automaticamente para um transporte com semântica diferente e alegar sucesso.
6. Exibir `enviado/requested`, não `enabled`. Só trocar para estado real após protocolo cooperativo ou verificação aprovada específica.

### Fase B — validação física e fallback controlado

Validar primeiro com `FakeFlingTrainer` no mesmo caminho UMU/Proton e depois com cada FLiNG/hash suportado. O gate precisa cobrir modifiers, key-up, janela em primeiro plano e em segundo plano, Game Mode/Gamescope, repetição, jogo encerrado e interrupção do helper.

Se `SendInput` não alcançar o polling em uma combinação real de Proton/Gamescope, investigar XTest ou `uinput` como adapters experimentais independentes, com capability explícita, logs do transport e sem root por padrão. O fallback não deve ser selecionado apenas porque `PostMessage` retornou sucesso.

### Fase C — trainers próprios

Gerar um manifest versionado a partir do perfil do trainer e embutir um canal cooperativo no mesmo processo. Relay deve consumir estado/ack do dono do patch. Esse caminho tem prioridade sobre UI Automation, janela Win32 ou leitura externa de memória.

### Fase D — motor de patches

Não iniciar como continuação natural do hotkey delivery. Só considerar após uma decisão separada por jogo/build, threat model, estratégia de rollback e validação física. O risco e o custo justificam um produto/adapter isolado, não uma capacidade genérica do Relay.

## Segurança, observabilidade e contrato de UI

O Relay deve separar quatro fatos:

| Fato observado | Pode ser afirmado? | Estado sugerido |
|---|---:|---|
| Adapter/hash/jogo conferem | Sim | `validated_target` |
| Helper foi lançado e `SendInput` aceitou N eventos | Sim | `requested` |
| Trainer próprio respondeu com ack | Sim | `accepted`/`rejected` |
| Cheat está realmente aplicado no jogo | Somente com verificação do trainer ou de adapter de memória aprovado | `enabled`/`disabled`/`unknown` |

Regras mínimas:

- allowlist por trainer, jogo, build e chord; desconhecido falha fechado;
- nenhum argumento livre passado ao helper; nenhum shell command construído a partir da UI;
- binário do helper assinado ou hash-checked; atualizar allowlist junto do release;
- rejeitar teclas reservadas do sistema e chords que possam bloquear/encerrar a sessão, salvo opt-in explícito;
- key-up garantido e timeout curto para helper/IPC;
- correlation id, transport, adapter/hash, PID, exit code e contagem de eventos nos diagnósticos;
- não registrar ambiente completo, tokens, command line arbitrária ou conteúdo de memória;
- Decky continua sem `root` por padrão; qualquer acesso a `uinput` deve ser uma capability revisada;
- `HWND`, PID e foreground são evidência transitória, não identidade suficiente do trainer.

## Evidência local e limites

O relatório usa a árvore local para estabelecer o comportamento do alvo e o encaixe com o código existente:

- `Tools/FlingDeckWrapper/tests/FakeFlingTrainer.cs`: polling de `GetAsyncKeyState` e detecção de borda;
- `Tools/FlingDeckWrapper/src/WindowsInputSender.cs` e `NativeMethods.cs`: transporte local por `SendInput` e validação de quantidade aceita;
- `docs/research/2026-08-31-trainer-relay-cheat-introspection.md`: catálogo/adapter FLiNG estático, estado não observável genericamente e fronteira atual do Relay;
- `main.py`, `trainer_relay/` e `plugin.json`: backend/lifecycle atual, reentrada UMU e ausência de RPC de cheat state.

Isso não é evidência de que cada FLiNG possui os mesmos detalhes internos, nem substitui a validação física por jogo/build. A regra de produto deve continuar sendo: hotkey conhecida pode ser enviada; sucesso do envio não prova o efeito.

## Ledger de fontes primárias/upstream

### Microsoft Win32

- [`GetAsyncKeyState`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getasynckeystate) — estado assíncrono atual, bits de retorno e limitações de desktop/UIPI.
- [`SendInput`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput) — injeção de teclado/mouse, retorno de eventos aceitos, UIPI e estado de input.
- [`Keyboard Input`](https://learn.microsoft.com/en-us/windows/win32/inputdev/about-keyboard-input) — distinção entre input de teclado, mensagens e `GetAsyncKeyState`.
- [`PostMessageW`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-postmessagew) — fila de mensagens, `HWND` e UIPI.
- [`SendMessageW`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendmessagew) — chamada síncrona ao procedimento da janela.
- [`SetForegroundWindow`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow) — foco/foreground e restrições contra roubo de foco.
- [`RegisterHotKey`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey) — registro e entrega de `WM_HOTKEY` a janela/thread.
- [`UI Automation overview`](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-uiautomationoverview), [`control patterns`](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-controlpatternsoverview) e [`properties`](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-propertiesoverview) — providers, invocação e limites de observabilidade da UI.

### Wine, Proton e UMU

- Wine upstream/mirror: [`dlls/user32/input.c`](https://github.com/wine-mirror/wine/blob/master/dlls/user32/input.c), [`dlls/win32u/input.c`](https://github.com/wine-mirror/wine/blob/master/dlls/win32u/input.c#L606-L759) e [`server/queue.c`](https://github.com/wine-mirror/wine/blob/master/server/queue.c#L2132-L2279) — caminho de `SendInput` e fila de input injetado.
- Wine X11 driver: [`dlls/winex11.drv/keyboard.c`](https://github.com/wine-mirror/wine/blob/master/dlls/winex11.drv/keyboard.c) — integração/layout de teclado X11.
- [`ValveSoftware/Proton`](https://github.com/ValveSoftware/Proton) e [`proton`](https://github.com/ValveSoftware/Proton/blob/proton_11.0/proton) — Proton baseado em Wine e execução por prefixo.
- [`Open-Wine-Components/umu-launcher`](https://github.com/Open-Wine-Components/umu-launcher) e [`umu_run.py` 1.4.4](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_run.py) — `umu-run`, runtime container, ambiente e reentrada `runinprefix`.

### Linux, X11, Wayland e Gamescope

- Linux kernel [`input`](https://www.kernel.org/doc/html/latest/input/input.html) — `evdev` como interface de consumo.
- Linux kernel [`uinput`](https://www.kernel.org/doc/html/latest/input/uinput.html) — criação de dispositivo de input virtual.
- X.Org [`XTEST Extension`](https://xorg.freedesktop.org/archive/X11R7.7/doc/xextproto/xtest.html) — `XTestFakeInput`.
- Wayland [`core protocol`](https://wayland.freedesktop.org/docs/html/apa.html) e [`Protocol book`](https://wayland.freedesktop.org/docs/book/Protocol.html) — seat, keyboard e foco controlado pelo compositor.
- Valve [`gamescope`](https://github.com/ValveSoftware/gamescope), [`src/wlserver.cpp`](https://github.com/ValveSoftware/gamescope/blob/master/src/wlserver.cpp) e [`gamescope-input-method.xml`](https://github.com/ValveSoftware/gamescope/blob/master/protocol/gamescope-input-method.xml) — routing/hotkeys do compositor e protocolo privado de input method.
- freedesktop/libinput [`libei`](https://libinput.pages.freedesktop.org/libei/) e [`sender API`](https://libinput.pages.freedesktop.org/libei/api/group__libei-sender.html) — emulação autorizada de input quando suportada pelo compositor.

### Decky

- Decky Loader [`plugin.py`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/plugin.py) — processo backend e dispatch.
- Decky Loader [`sandboxed_plugin.py`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/plugin/sandboxed_plugin.py) — ambiente, usuário efetivo, socket e dispatch de métodos.

### Contexto oficial FLiNG

- [Arquivo oficial de trainers FLiNG](https://flingtrainer.com/uncategorized/my-trainers-archive/comment-page-2/) — evidência de catálogo/documentação humana; não define API de IPC ou de estado para um trainer em execução.

## Continuidade / handoff desta pesquisa

- **Entregue:** matriz e recomendação em um único arquivo Markdown.
- **Alterado:** somente este relatório; nenhum código ou configuração foi modificado.
- **Validação pendente:** implementar o helper e executar primeiro o FakeFlingTrainer no caminho UMU/Proton, depois validar cada trainer/hash FLiNG no Steam Deck físico.
- **Contrato pendente:** decidir o schema de `send_known_hotkey` e o vocabulário `requested`/`unknown` antes de adicionar RPCs de cheat.
- **Estado GitHub no momento da pesquisa delegada:** o agente de pesquisa não executou commit nem push; a integração final deve revisar este arquivo, atualizar o handoff e sincronizar o bloco conforme as regras do projeto.
