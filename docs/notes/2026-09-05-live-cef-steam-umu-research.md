# Pesquisa: visibilidade de janela CEF/Wine no seletor Steam sob Gamescope + UMU

Data: 2026-09-05
Escopo: pesquisa documental/código-fonte; nenhuma alteração de código e nenhum binário do trainer executado.

## Resultado executivo

Há uma cadeia de três decisões independentes:

1. **UMU precisa realmente iniciar o monitor de janelas.** `UMU_STEAM_GAME_ID` é apenas uma entrada para calcular o AppID que será escrito; ele não prova que `monitor_windows()` rodou.
2. **O monitor do UMU precisa conseguir associar a janela.** A associação é por `_NET_WM_PID` pertencente à árvore de processos observada; o resultado é a propriedade X11 `STEAM_GAME`.
3. **Gamescope precisa considerar a janela reportável/focável.** No código analisado, isso depende do AppID, estado mapeado/visível, classe X11, opacidade, `override_redirect`, tamanho e estados `SKIP_TASKBAR`/`SKIP_PAGER`. Gamescope publica então listas de janelas e AppIDs focáveis na raiz X11.

Portanto, a observação “a janela existe e `WM_STATE=Normal`” não fecha o caso. Também não fecha o caso restaurar somente `UMU_STEAM_GAME_ID`: a propriedade `STEAM_GAME` pode nunca ter sido escrita, pode ter valor zero/errado, ou a janela pode ser excluída por seus estados/tipo.

O caminho exato usado pelo seletor visual do cliente Steam não é verificável no código público pesquisado. O que é demonstrável é o contrato público entre UMU e Gamescope e as propriedades X11 que Gamescope exporta para consumidores Steam.

## Contexto local preservado

O handoff existente registra:

- `experimental.19` abriu o trainer para GOG por observação do usuário;
- `experimental.22` ainda mostrou somente Mortal Shell no seletor Steam;
- a `.22` restaurou `UMU_STEAM_GAME_ID`, sem resolver isoladamente o comportamento;
- sondagens anteriores confirmaram que o trainer cria uma janela X11, mas ainda sem prova de que ela recebeu `STEAM_GAME` ou entrou na lista Steam de janelas focáveis.

Esses fatos são **observações do repositório/handoff**, não resultados de uma nova execução nesta pesquisa.

## 1. UMU-launcher 1.4.4

Fonte primária: [`umu/umu_run.py` na tag 1.4.4](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_run.py).

### 1.1 Identidade: `set_env()` não equivale a associação da janela

Em [`set_env`, linhas 192–282](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_run.py#L192-L282), a tag 1.4.4:

- copia o `SteamGameId` recebido para `UMU_STEAM_GAME_ID` (linhas 252–255);
- define `SteamAppId` e `SteamGameId` do processo para o ID derivado de `UMU_ID` (linhas 257–261);
- mantém `UMU_CONTAINER_NSENTER` no ambiente (linhas 277–282);
- normaliza um `PROTON_VERB` inválido para `waitforexitandrun` (linhas 212–217).

O valor posteriormente usado para escrever `STEAM_GAME` vem de [`get_steam_appid`, linhas 515–537](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_run.py#L515-L537). A ordem é: caminhos de mídia/cache e, por último, `int(UMU_STEAM_GAME_ID) >> 32`; se não houver valor válido, o retorno fica zero.

**Fato:** restaurar `UMU_STEAM_GAME_ID` torna o ID disponível para essa função.
**Não demonstrado:** que o valor efetivo calculado na execução foi o esperado ou que ele chegou a uma janela.

### 1.2 `build_command()` e a reentrada `runinprefix`

Em [`build_command`, linhas 331–383](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_run.py#L331-L383), quando `UMU_CONTAINER_NSENTER=1` e o launch client encontra o bus da aplicação, UMU:

- monta a reentrada por `--bus-name=...` (linhas 349–371);
- muda o `PROTON_VERB` para `runinprefix` (linha 372);
- constrói o comando usando esse verbo (linhas 377–382).

Isso é relevante porque o gate do monitor, descrito abaixo, exige exatamente `PROTON_VERB == "waitforexitandrun"`. **Inferência de instrumentação:** uma invocação separada de UMU reentrada em `runinprefix` não deve ser tratada como se ela própria fosse iniciar o monitor; é necessário descobrir se a associação será herdada/realizada pelo processo UMU pai ou se ficará sem monitor. O código não permite concluir, sem a árvore de processos real, qual invocação é a responsável no caso do trainer.

### 1.3 Associação por PID e escrita de `STEAM_GAME`

[`get_pstree_window_ids`, linhas 429–464](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_run.py#L429-L464) seleciona janelas por `_NET_WM_PID`:

- `_NET_WM_PID` precisa existir; se o átomo não existir, UMU retorna sem fallback para X-Res (linhas 438–443);
- o PID da janela precisa pertencer à árvore descendente observada (linhas 444–461);
- o próprio comentário explica que X-Res não é usado porque os PIDs não mapeiam de forma segura entre os namespaces Flatpak.

Quando há correspondência, [`set_steam_game_property`, linhas 466–492](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_run.py#L466-L492) escreve um `CARDINAL` com o nome `GamescopeAtom.SteamGame`, isto é, `STEAM_GAME`.

**Fato:** no desenho de 1.4.4, a ponte UMU → Gamescope é a propriedade X11 `STEAM_GAME` escrita somente nas janelas cujo `_NET_WM_PID` bate com a árvore observada.
**Implicação:** janela visível com PID correto, mas sem `STEAM_GAME`, ainda não prova associação Steam.

### 1.4 Gates de `run_in_steammode()` e `run_command()`

[`run_in_steammode`, linhas 597–636](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_run.py#L597-L636):

- conecta a `:0` e `:1` (linhas 608–615);
- lê `GAMESCOPECTRL_BASELAYER_APPID` na raiz primária;
- só instala `SubstructureNotifyMask` e inicia a thread `monitor_windows()` se a sequência do baselayer for truthy **e** `PROTON_VERB` for `waitforexitandrun` (linhas 617–630);
- passa à thread o PID retornado por `_get_pstree_root_pid()`.

Se a conexão com os displays falha, o código registra a exceção e apenas espera o processo terminar (linhas 631–636).

[`run_command`, linhas 645–689](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_run.py#L645-L689) define o gate externo:

- sessão Gamescope: `XDG_CURRENT_DESKTOP` ou `XDG_SESSION_DESKTOP` igual a `gamescope` ([linhas 68–71](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_run.py#L68-L71));
- `STEAM_MULTIPLE_XWAYLANDS == "1"`;
- `container == "flatpak"`;
- somente então chama `run_in_steammode(proc)`; caso contrário, faz `proc.wait()` diretamente (linhas 653–686).

O caminho temporal é importante: `monitor_windows()` primeiro espera uma janela correspondente e só depois escreve `STEAM_GAME`; para janelas novas, acompanha eventos e escreve a propriedade no delta ([linhas 564–595](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_run.py#L564-L595)).

**Diagnóstico que o código permite:** a restauração de uma variável de identidade pode estar correta e ainda assim não produzir `STEAM_GAME` se qualquer gate — sessão, Flatpak, múltiplos Xwayland, baselayer, verbo, conexão ou PID — não ocorrer.

## 2. Gamescope: associação, filtros e propriedades publicadas

Fonte primária fixada: [`ValveSoftware/gamescope`, `steamcompmgr.cpp`, commit `ff6b924fd0634a51d0fb3755c56c01dca1daadc1`](https://github.com/ValveSoftware/gamescope/blob/ff6b924fd0634a51d0fb3755c56c01dca1daadc1/src/steamcompmgr.cpp).

### 2.1 `STEAM_GAME` é a associação de AppID

O código define `GAME_PROP` como `STEAM_GAME` ([linhas 1033–1039](https://github.com/ValveSoftware/gamescope/blob/ff6b924fd0634a51d0fb3755c56c01dca1daadc1/src/steamcompmgr.cpp#L1033-L1039)). Em `map_win`, no modo Steam, Gamescope lê essa propriedade e a trata como autoritativa quando não zero ([linhas 4483–4496](https://github.com/ValveSoftware/gamescope/blob/ff6b924fd0634a51d0fb3755c56c01dca1daadc1/src/steamcompmgr.cpp#L4483-L4496)). Há inclusive log de conflito se o AppID anterior e o da propriedade diferirem.

Assim, a cadeia verificável é:

```text
UMU_STEAM_GAME_ID
        │ get_steam_appid()
        ▼
monitor_windows() ── _NET_WM_PID ∈ pstree ──► STEAM_GAME=CARDINAL(AppID)
        │
        ▼
Gamescope map_win() lê STEAM_GAME como appID
        │
        ▼
lista de janelas focáveis / propriedades na raiz
```

### 2.2 Filtros que podem excluir uma janela existente

`GetPossibleFocusWindows()` descarta ícones de tray, overlays e vídeo de streaming; na estratégia `SteamControlled`, exige AppID não zero ou janela Steam/streaming; depois exige `map_state == IsViewable`, classe `InputOutput` e opacidade acima de transparente ([linhas 3483–3520](https://github.com/ValveSoftware/gamescope/blob/ff6b924fd0634a51d0fb3755c56c01dca1daadc1/src/steamcompmgr.cpp#L3483-L3520)).

O comparador de prioridade prefere janelas com AppID, janelas não `override_redirect` e janelas não marcadas simultaneamente como skip taskbar/pager. O comentário chama explicitamente a relação com `WS_EX_NOACTIVATE` do Wine ([linhas 3215–3255](https://github.com/ValveSoftware/gamescope/blob/ff6b924fd0634a51d0fb3755c56c01dca1daadc1/src/steamcompmgr.cpp#L3215-L3255)). Prioridade não é o mesmo que inclusão: na construção da lista comunicada ao Steam, Gamescope exclui janelas 1x1, `skip-taskbar + skip-pager` não fullscreen e `override_redirect` ([linhas 3895–3907](https://github.com/ValveSoftware/gamescope/blob/ff6b924fd0634a51d0fb3755c56c01dca1daadc1/src/steamcompmgr.cpp#L3895-L3907)).

Depois publica:

- `GAMESCOPE_FOCUSABLE_APPS`: AppIDs não zero;
- `GAMESCOPE_FOCUSABLE_WINDOWS`: triplets `[window, appid, pid]`.

Isso ocorre nas linhas [3908–3933](https://github.com/ValveSoftware/gamescope/blob/ff6b924fd0634a51d0fb3755c56c01dca1daadc1/src/steamcompmgr.cpp#L3908-L3933).

**Fato:** o código público mostra quais janelas Gamescope considera reportáveis e quais propriedades publica.
**Desconhecido:** não há código público do cliente Steam neste levantamento que prove se, em cada versão do SteamOS, o seletor usa exatamente essas propriedades, outro caminho IPC, ou uma política adicional.

### 2.3 Tipo, transient e dropdown

Gamescope lê `WM_TRANSIENT_FOR` e `_NET_WM_WINDOW_TYPE`; `transientFor` inicialmente torna a janela um diálogo, mas `_NET_WM_WINDOW_TYPE_NORMAL` pode desfazer essa classificação ([linhas 4265–4284](https://github.com/ValveSoftware/gamescope/blob/ff6b924fd0634a51d0fb3755c56c01dca1daadc1/src/steamcompmgr.cpp#L4265-L4284)). Hints de posição fixa e `StaticGravity` marcam uma janela como possível dropdown ([linhas 4287–4303](https://github.com/ValveSoftware/gamescope/blob/ff6b924fd0634a51d0fb3755c56c01dca1daadc1/src/steamcompmgr.cpp#L4287-L4303)). O tratamento especial de dropdown, transient e skip é específico de foco/override; não deve ser confundido com uma regra geral de que “qualquer janela CEF” é selecionável ([linhas 3122–3193](https://github.com/ValveSoftware/gamescope/blob/ff6b924fd0634a51d0fb3755c56c01dca1daadc1/src/steamcompmgr.cpp#L3122-L3193)).

## 3. O que os padrões X11/EWMH significam

Fonte primária: [EWMH, seção 5 — Application Window Properties](https://specifications.freedesktop.org/wm/latest/ar01s05.html).

- `_NET_WM_WINDOW_TYPE` deve ser definido antes do map e informa ao window manager o tipo funcional, decoração e comportamento; `NORMAL` é o tipo de janela top-level normal; `DIALOG` identifica diálogo ([§5.6, linhas 90–126](https://specifications.freedesktop.org/wm/latest/ar01s05.html#idm140200472020496)).
- Se `_NET_WM_WINDOW_TYPE` não existir, uma janela gerenciada com `WM_TRANSIENT_FOR` deve ser tratada como diálogo; uma override-redirect com transient, mas sem tipo, é tratada como normal ([mesma seção](https://specifications.freedesktop.org/wm/latest/ar01s05.html#idm140200472020496)).
- `_NET_WM_STATE_SKIP_TASKBAR` significa não incluir na taskbar; `_NET_WM_STATE_SKIP_PAGER` significa não incluir no pager. A especificação recomenda que a aplicação não defina esses estados se o tipo já expressar sua natureza ([§5.7, linhas 127–159](https://specifications.freedesktop.org/wm/latest/ar01s05.html#idm140200471998032)).
- `_NET_WM_STATE_HIDDEN` é estado que o window manager usa para indicar uma janela não visível; `WM_STATE=Normal` não substitui essa informação ([mesma seção](https://specifications.freedesktop.org/wm/latest/ar01s05.html#idm140200471998032)).
- `_NET_WM_PID` deve conter o PID do cliente que possui a janela ([§5.13, linhas 264–270](https://specifications.freedesktop.org/wm/latest/ar01s05.html#idm140200471956064)).
- Para uma popup override-redirect em nome de outra janela, o cliente deve usar `WM_TRANSIENT_FOR` apontando para a top-level correspondente ([EWMH §8.2](https://specifications.freedesktop.org/wm/latest/ar01s08.html#idm140200467814384)).

Essas regras são semântica X11/EWMH; não constituem prova de que o seletor Steam implemente todos os detalhes de um pager tradicional. Gamescope, porém, lê diretamente vários desses sinais no código citado acima.

## 4. Wine/Proton: como estilos Win32 viram propriedades X11

Fonte primária fixada: [`ValveSoftware/wine`, commit `dc26e61847081a1b5cb0733dc30feba6ee575482`, `dlls/winex11.drv/window.c`](https://github.com/ValveSoftware/wine/blob/dc26e61847081a1b5cb0733dc30feba6ee575482/dlls/winex11.drv/window.c).

### 4.1 Owner/transient/tipo

Em [`set_style_hints`, linhas 1070–1116](https://github.com/ValveSoftware/wine/blob/dc26e61847081a1b5cb0733dc30feba6ee575482/dlls/winex11.drv/window.c#L1070-L1116), Wine:

- obtém o owner Win32 e o transforma no ancestor root;
- chama `XSetTransientForHint` para o owner X11;
- classifica popup owned ou `WS_EX_DLGMODALFRAME` como `_NET_WM_WINDOW_TYPE_DIALOG`;
- caso contrário, usa `_NET_WM_WINDOW_TYPE_NORMAL`.

Logo, “janela CEF” não determina por si só o tipo visto por Gamescope: owner, `WS_POPUP`, ex-style e caminho de criação importam.

### 4.2 PID e classe

Em [`set_initial_wm_hints`, linhas 1124–1163](https://github.com/ValveSoftware/wine/blob/dc26e61847081a1b5cb0733dc30feba6ee575482/dlls/winex11.drv/window.c#L1124-L1163), essa versão de Wine/Proton:

- usa `SteamAppId` para classe/resname `steam_app_<id>` quando disponível (linhas 1137–1152);
- escreve `_NET_WM_PID` com o PID do processo Wine (linhas 1155–1160).

O segundo ponto é necessário para o algoritmo de associação do UMU. O primeiro é um sinal útil de diagnóstico, mas não substitui `STEAM_GAME`.

### 4.3 Skip-taskbar/pager

Em [`update_net_wm_states`, linhas 1497–1543](https://github.com/ValveSoftware/wine/blob/dc26e61847081a1b5cb0733dc30feba6ee575482/dlls/winex11.drv/window.c#L1497-L1543), Wine adiciona `SKIP_TASKBAR` e `SKIP_PAGER` quando:

- `skip_taskbar` já está ativo;
- `WS_EX_NOACTIVATE` está presente;
- `WS_EX_TOOLWINDOW` está presente sem `WS_EX_APPWINDOW`.

Para uma janela owned sem `WS_EX_APPWINDOW`, há ainda o caso de `SKIP_TASKBAR` isolado. O Gamescope tem uma exclusão mais forte para a combinação dos dois estados em janela não fullscreen, portanto esses estados devem ser medidos diretamente no X11.

## 5. CEF: o que é fato e o que não pode ser inferido

Fonte primária fixada: [`chromiumembedded/cef`, commit `cd89341bfe7eb5e856e98c8cac9b29fe5f77f926`, `include/internal/cef_win.h`](https://github.com/chromiumembedded/cef/blob/cd89341bfe7eb5e856e98c8cac9b29fe5f77f926/include/internal/cef_win.h).

Na API `CefWindowInfo`:

- `SetAsChild` usa `WS_CHILD | WS_CLIPCHILDREN | WS_CLIPSIBLINGS | WS_TABSTOP | WS_VISIBLE` e atribui `parent_window` ([linhas 700–715](https://github.com/chromiumembedded/cef/blob/cd89341bfe7eb5e856e98c8cac9b29fe5f77f926/include/internal/cef_win.h#L700-L715));
- `SetAsPopup` usa `WS_OVERLAPPEDWINDOW | WS_CLIPCHILDREN | WS_CLIPSIBLINGS | WS_VISIBLE`, parent opcional e bounds default ([linhas 717–740](https://github.com/chromiumembedded/cef/blob/cd89341bfe7eb5e856e98c8cac9b29fe5f77f926/include/internal/cef_win.h#L717-L740));
- `SetAsWindowless` declara explicitamente que nenhuma janela é criada ([linhas 742–772](https://github.com/chromiumembedded/cef/blob/cd89341bfe7eb5e856e98c8cac9b29fe5f77f926/include/internal/cef_win.h#L742-L772)).

**Fato:** a API padrão de popup CEF não adiciona, nesse trecho, `WS_EX_TOOLWINDOW`; a API padrão child cria um child Win32, não uma top-level independente.
**Desconhecido:** o trainer pode usar `CefWindowInfo` customizado, alterar `ex_style`, criar uma janela nativa própria, usar popup/owner, ou usar renderização windowless. Não é válido atribuir `SKIP_TASKBAR`, `WM_TRANSIENT_FOR`, `override_redirect` ou ausência de seleção somente ao rótulo “CEF”.

O sample oficial do CEF também mostra que um browser child pode receber `WS_EX_NOACTIVATE` quando o parent o possui e que popups podem ser mostrados sem ativação ([`browser_window_std_win.cc`, commit `cd89341b…`, linhas 25–73](https://github.com/chromiumembedded/cef/blob/cd89341bfe7eb5e856e98c8cac9b29fe5f77f926/tests/cefclient/browser/browser_window_std_win.cc#L25-L73)). Isso é evidência de uma possibilidade da cadeia CEF, não evidência do trainer específico.

## 6. Matriz de fatos, inferências e desconhecidos

| Item | Classificação | Base | O que falta provar |
|---|---|---|---|
| `UMU_STEAM_GAME_ID` é copiado e pode alimentar o cálculo do AppID | Fato | UMU 1.4.4 `set_env`/`get_steam_appid` | valor efetivo na execução `.22` |
| `STEAM_GAME` é a propriedade que Gamescope lê como AppID autoritativo | Fato | Gamescope `map_win` | se foi escrita no trainer |
| UMU só inicia o monitor sob os gates descritos | Fato | `run_command`/`run_in_steammode` | quais valores reais existiam em `.19` e `.22` |
| `runinprefix` pode impedir o monitor daquela invocação | Inferência direta do gate | `build_command` + gate `PROTON_VERB` | se o monitor do pai cobriu a árvore do trainer |
| `_NET_WM_PID` é necessário no UMU 1.4.4 | Fato | `get_pstree_window_ids` | PID/namespace vistos no caso real |
| `WM_STATE=Normal` garante seletor Steam | Refutado pelo código | filtros Gamescope/EWMH | nenhum; o estado sozinho é insuficiente |
| CEF por padrão implica `SKIP_TASKBAR` | Não comprovado | CEF define estilos base; Wine deriva estados | ex-style/owner real do trainer |
| Gamescope publica a janela para o consumidor Steam | Fato para a camada Gamescope | `GAMESCOPE_FOCUSABLE_*` | consumidor exato e política da versão SteamOS |
| o seletor Steam usa exatamente `GAMESCOPE_FOCUSABLE_WINDOWS` | Desconhecido | cliente Steam não é fonte pública | captura/protocolo da versão instalada |

## 7. Instrumentação/reprodução concreta, sem correção presumida

O próximo repro deve medir a cadeia em uma janela curta, comparando `.19`/GOG e `.22`/caso que falha, sem executar mudanças corretivas durante a coleta.

### 7.1 Ambiente e processo

Registrar, por invocação UMU relevante, sem segredos:

- versão/hash do `umu-launcher`, Proton e Gamescope;
- `PROTON_VERB`, `container`, `XDG_CURRENT_DESKTOP`, `XDG_SESSION_DESKTOP`, `STEAM_MULTIPLE_XWAYLANDS`;
- `DISPLAY` efetivo e sucesso de conexão a `:0`/`:1`;
- presença e valor numérico de `GAMESCOPECTRL_BASELAYER_APPID`;
- `UMU_STEAM_GAME_ID`, `SteamAppId`, `SteamGameId`, `UMU_CONTAINER_NSENTER` e origem efetiva escolhida por `get_steam_appid`;
- PID do UMU, `pv-adverb`/raiz encontrada, jogo e trainer, e árvore PID com timestamps.

O objetivo é responder primeiro: **o monitor foi iniciado?** Depois: **qual AppID ele calculou?**

### 7.2 Janela X11 antes/depois da associação

Para jogo e trainer, em ambos os displays relevantes, registrar antes e depois do nascimento da janela:

- XID, `map_state`, geometria, `override_redirect`, classe visual e opacidade;
- `_NET_WM_PID`, `WM_STATE`, `_NET_WM_NAME`/`WM_NAME`, classe/resname;
- `STEAM_GAME` como `CARDINAL`, inclusive ausência, zero e mudança temporal;
- `_NET_WM_WINDOW_TYPE`, `WM_TRANSIENT_FOR`;
- `_NET_WM_STATE` completo, especialmente `SKIP_TASKBAR`, `SKIP_PAGER`, `HIDDEN`, fullscreen;
- `_WINE_HWND_STYLE` e `_WINE_HWND_EXSTYLE` quando presentes;
- timestamp/evento de criação, map, mudança de propriedade e destruição.

Isso separa quatro falhas que hoje parecem iguais no seletor:

1. janela inexistente no display observado;
2. janela existente, mas `_NET_WM_PID` ausente ou fora da árvore UMU;
3. janela associada sem `STEAM_GAME`, ou com AppID inesperado;
4. janela com AppID correto, mas excluída pelos filtros de Gamescope.

### 7.3 Estado que Gamescope expõe e resultado do usuário

No mesmo timestamp, capturar na raiz X11:

- `GAMESCOPE_FOCUSABLE_APPS`;
- `GAMESCOPE_FOCUSABLE_WINDOWS` como triplets `[XID, AppID, PID]`;
- a janela ativa/foco quando aplicável;
- resultado observável do seletor Steam: lista exibida e se o trainer é selecionável.

Se o XID do trainer não aparece em `GAMESCOPE_FOCUSABLE_WINDOWS`, o problema está demonstravelmente antes/na filtragem Gamescope. Se aparece e ainda não aparece na UI, a camada restante é o consumidor Steam/política específica da versão, que não está coberta pelo código público pesquisado.

### 7.4 Comparação controlada

Não comparar apenas “GOG versus Epic”. Fixar, tanto quanto possível, o mesmo trainer, mesma build do Proton/UMU/Gamescope, mesmo prefixo e mesmo formato de janela; variar somente o caminho de lançamento que produz `.19` e `.22`. A diferença útil é o primeiro ponto divergente na tabela acima, não a hipótese de que a loja por si só determina o resultado.

## 8. Limites e conclusão

O achado mais forte é uma condição necessária operacional:

```text
ID efetivo correto
  + monitor UMU iniciado
  + _NET_WM_PID da janela na árvore monitorada
  = STEAM_GAME escrito
  + filtros Gamescope aprovados
  = janela publicada como focável para a camada Steam
```

Isso explica por que a restauração isolada de `UMU_STEAM_GAME_ID` não encerra a investigação. Ainda não há base primária suficiente para afirmar qual condição falha em `.22`, nem para prescrever uma alteração de estilo CEF/Wine, `WM_TRANSIENT_FOR`, `SKIP_TASKBAR`, `STEAM_GAME` ou rota UMU. A evidência mínima que falta é a coleta sincronizada descrita na seção 7.

## Estado de entrega no repositório

- Arquivo intencionalmente criado: `docs/notes/2026-09-05-live-cef-steam-umu-research.md`.
- Nenhum código, binário, configuração de runtime ou artefato existente foi alterado.
- O diretório não versionado `.codex-remote-attachments/` já existia e foi preservado fora do escopo.
- Testes de software não se aplicam a esta tarefa de pesquisa; a validação executada deve ser documental (`git diff --check`) e de integridade do único arquivo.
- Status de commit/push deve ser conferido após a criação deste relatório; não incluir o diretório de anexos.
