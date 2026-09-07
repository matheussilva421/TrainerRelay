# Handoff — correção FLiNG visível e toggles clicáveis

Data: 2026-09-06
Objetivo: executar o plano `docs/superpowers/plans/# Plano de correção do FLiNG no Tra.txt` no TrainerRelay, preservando o UniFiDeck, sem Force Compatibility, e validar a tela real do FLiNG com troca Steam jogo/trainer e ativação/desativação por interação visual.

## Estado atual

- A tarefa ainda não está concluída: o ensaio live da `.28` reproduziu a ausência da janela e revelou uma validação incorreta do runtime; a correção `.29` está implementada localmente e aguarda empacotamento/instalação e validação física.
- O trabalho está no worktree/branch existente `feat/trainer-relay`, baseado em `10e3269aa4dbea9a629069105ee049dabbc74d6d` (`docs: consolidate FLiNG visibility handoff`). A tentativa de criar branch isolada falhou antes de alterar o working tree por falta de permissão no `HEAD.lock` do worktree administrativo.
- O repositório já estava sujo com artefatos/documentos do usuário; preservar mudanças não relacionadas e fazer staging explícito.
- Plugin instalado no Deck: `0.1.0-experimental.28`. Mortal Shell está vivo pelo atalho normal do UniFiDeck, sem Force Compatibility, mas essa versão lançou o trainer pelo perfil incorreto `umu_direct` e a janela não entrou em `GAMESCOPE_FOCUSABLE_WINDOWS`.
- Steam Deck: `deck@192.168.1.247`, host key pinned com fingerprint `SHA256:YkrB6o3zby/e8NdZ/Kzx3yBDH01ZFQEg9XBTl/0/8mI`. SSH temporário autorizado para diagnóstico; remover a chave dedicada e qualquer habilitação temporária de sshd ao final, preservando estado preexistente.
- Jogo observado vivo em diagnóstico anterior: `Dungeonhaven.exe`/`Dungeonhaven-Wi`, Steam app `2476768691`, com `wineserver` no mesmo container. Não imprimir argumentos completos de processos.
- A instalação pelo fluxo oficial do Decky reiniciou o plugin e encerrou a sessão de jogo que estava aberta; isso foi preservado como estado conhecido, não como falha do jogo. O artefato `.28` no Deck tem SHA-256 `1ea72b8ba6e97b7cf11e8d71a881df40770099c487796d0a384ff65d8711bacb`, igual ao PC. O arquivo instalado reporta `.28`; ainda falta RPC/frontend e validação física.

## Correção de produção implementada

- `trainer_relay/watcher.py`: uma falha inesperada de `poll_once()` agora é registrada como evento sanitizado e não mata o loop de monitoramento.
- `main.py`: o serviço recria o watcher quando a task anterior terminou e o bootstrap também registra `plugin_loaded` no watcher vivo.
- `PLUGIN_VERSION`, `package.json`, README, protocolo e teste de layout foram atualizados de `.26` para `.27`.
- Regressões TDD adicionadas em `tests_backend/test_watcher.py` e `tests_backend/test_main.py`; primeiro executaram em RED e depois em GREEN.
- `.28` adiciona perfil allowlisted para o hash x64 exato do Mortal Shell: mantém o GE11 Wine client/server e prefixo do jogo, mas inicia o trainer dentro do mesmo container via `steam-runtime-launch-client` usando o clone privado GE11/Mono10 já validado.
- `.29` corrige o resolvedor do perfil privado: `lib` e `lib/wine` continuam obrigatórios e confinados ao runtime, enquanto a pasta top-level `lib64` passa a ser opcional, compatível com o layout real do GE-Proton 11-6 no Deck.

## Evidências já produzidas

- `docs/research/2026-09-06-fling-toggle-root-cause-ledger.md`: identidade exata do trainer, SHA, arquitetura, constraints e separação entre estado atual bloqueado e evidência histórica.
- `docs/research/2026-09-06-mortal-shell-fling-runtime-fingerprint.md`: o executável exato é PE x64 nativo com host CLR (`mscoree.dll`, `CLRCreateInstance`, `CorBindToRuntime`, referências a `v4.0.30319`/`v2.0.50727`), sem evidência suficiente de WinForms/WPF puro. A troca de Mono, isoladamente, não pode ser declarada como causa.
- `docs/STEAM-DECK-VALIDATION.md`: protocolo de aceitação física para visibilidade, troca pelo Steam e toggles, com estados `PASS_PHYSICAL`, `RED_REPRODUCED`, `NOT_TESTED`, `INCONCLUSIVE`, `CRASHED` e `ROLLED_BACK`.
- `tools/fling-toggle-lab/`: laboratório diagnóstico não empacotado, com `ToggleProbe.cs`, build/run, inspeção estática e contrato esperado. Não deve ser instalado nem incluído no ZIP de produção.
- `tests_packaging/test_package_layout.py`: regressão garante que `fling-toggle-lab` nunca entra no pacote.
- Evidência histórica controlada: o mecanismo de `STEAM_GAME` + `GAMESCOPE_FOCUSABLE_WINDOWS` colocou a janela real do trainer no seletor do Gamescope; com clone privado GE-Proton 11 + Mono 10.4.1 houve renderização, troca pelo botão Steam e validação física de `NUM3` (Infinite Stamina) ON/OFF. O Mono global 11.2.0 permaneceu intacto. Isso é evidência de caminho diagnóstico, não prova de integração do plugin `.26`.

## Gates executados

- `python -m unittest tests_packaging.test_package_layout.TrainerRelayPackageLayoutTests.test_diagnostic_fling_lab_is_never_packaged -v`: verde.
- `python -m unittest discover -s tests_packaging -q`: 8 testes, 8 passaram, 0 falharam.
- RED observado antes da implementação: 2 testes focados, 1 erro e 1 falha pelos sintomas esperados.
- GREEN focado depois: 28 testes, 28 passaram.
- Backend: 298 testes, 298 passaram.
- Packaging: 8 testes, 8 passaram.
- Frontend Vitest: 217 testes, 217 passaram.
- Biome: 75 arquivos sem erro.
- TypeScript (produção e testes): passou.
- Rollup: passou.
- RED `.29`: o teste realista sem `lib64` falhou com `profile is None`.
- GREEN focado `.29`: 74 testes de runtime/runner/watcher passaram, 0 falharam.
- Ainda falta empacotar/instalar `.29`, validar RPC/frontend e tela física, e executar o teste de regressão GOG.

## Decisões e limites

- Não usar Force Compatibility, não trocar o Mono global, não migrar .NET no prefixo real sem autorização explícita, não alterar `shortcuts.vdf` enquanto Steam estiver rodando.
- Não usar cliques/toques sintéticos como prova. A aceitação exige interação física do usuário na tela do Deck.
- Não implementar silenciosamente um overlay que converta clique em hotkey. Isso é fallback/RFC separado e não substitui a tela real do FLiNG.
- O caminho candidato de produção, se a evidência ao vivo exigir, é preservar o atalho normal do UniFiDeck e corrigir a associação da janela dentro do container/prefixo exato, com prova de Gamescope/CEF e regressão automatizada. Uma camada de runtime privada só pode ser promovida após prova isolada, hash/prefixes preservados e rollback claro.

## Próxima retomada

1. Pedir ao usuário para abrir novamente Mortal Shell pelo UniFiDeck normal, com Force Compatibility desligado, e deixá-lo no menu. A sessão anterior foi encerrada pela instalação do `.28`.
2. Ler eventos atuais do plugin, processo/container, propriedades X11 `STEAM_GAME`, triplets `GAMESCOPE_FOCUSABLE_WINDOWS` e mapa CEF; sem expor segredos nem argumentos completos.
3. Se o ensaio falhar, escrever primeiro o teste de regressão focado no ponto observado; implementar a menor correção e repetir os gates.
4. Validar no Deck: trainer visível, Steam alterna jogo/trainer, clique/tap em Infinite Stamina liga o efeito e segundo clique desliga/reverte; repetir baseline GOG e checar UniFiDeck.
5. Atualizar este handoff, validar o GOG, verificar hash/backup/rollback, limpar SSH temporário e fazer commit/push. Rollback remoto pré-instalação: `/home/deck/Downloads/TrainerRelay-rollback-20260906-1905/`.

## Arquivos deste bloco

- Alterado: este handoff.
- Alterados para a correção `.27`: `main.py`, `package.json`, `README.md`, `trainer_relay/diagnostics.py`, `trainer_relay/watcher.py`, `tests_backend/test_main.py`, `tests_backend/test_watcher.py`, `tests_packaging/test_package_layout.py`, `docs/STEAM-DECK-VALIDATION.md`.
- Alterados para `.28`: `trainer_relay/runtime_profile.py`, `trainer_relay/runner.py`, `trainer_relay/watcher.py`, `trainer_relay/diagnostics.py`, `src/infra/diagnosticRpc.ts`, `tests_backend/test_runtime_profile.py`, `tests_backend/test_runner.py`, `tests_backend/test_watcher.py` e os arquivos de versão/protocolo acima.
- Alterados para `.29`: `trainer_relay/runtime_profile.py`, `tests_backend/test_runtime_profile.py`, `main.py`, `package.json`, `README.md`, `docs/STEAM-DECK-VALIDATION.md` e este handoff.
- Criados anteriormente: ledger, fingerprint, protocolo, laboratório e plano detalhado listados acima.
- Nenhum arquivo de produção alterado neste bloco.

## Atualização `.28` — instalado, validação pendente

- O candidato `.28` foi empacotado, transferido e instalado pelo fluxo autenticado `utilities/install_plugin`/`utilities/confirm_plugin_install` do Decky, a partir do `SharedJSContext`. O evento capturado foi `loader/add_plugin_install_prompt` para `Trainer Relay`, versão `.28`, hash esperado e tipo de update `2`; a confirmação retornou sem erro e o arquivo instalado passou a reportar `.28`.
- O runtime privado allowlisted foi movido do cache diagnóstico para `/home/deck/.local/share/TrainerRelay/runtimes/mortal-shell-ge11-mono10`; tamanho observado `1.7G`, com `wine-mono` apontando para `wine-mono-10.4.1`. O prefixo do jogo e o Mono global não foram alterados.
- Ensaio live isolado anterior do caminho privado produziu a janela FLiNG real `780x666` e o triplet Gamescope `[46137345,2476768691,58715]` enquanto o jogo permaneceu vivo. Esse ensaio terminou com status `143` antes da prova de estabilidade; por isso o gate oficial continua pendente.
- O próximo gate é o usuário relançar Mortal Shell normalmente pelo UniFiDeck. Depois devem ser coletados `runtime_profile=mortal_shell_ge11_mono10`, `trainer_running`, o triplet do trainer em `GAMESCOPE_FOCUSABLE_WINDOWS` e a confirmação física de alternância/clique ON/OFF. Não usar Force Compatibility, `RunGame`, desktop virtual ou cliques sintéticos.
## Atualização `.29` — causa live fechada em TDD

- A sessão real foi observada viva com `Dungeonhaven.exe` PID 62105, `Dungeonhaven-Win64-Shipping.exe` PID 62115, `wineserver` PID 62021 e app Steam `2476768691`; o jogo continuou funcionando pelo UniFiDeck.
- O diagnóstico do plugin registrou `candidate_accepted`, `container_reentry_verified` e depois `trainer_spawned.runtime_profile=umu_direct`. Não houve processo/janela FLiNG em `GAMESCOPE_FOCUSABLE_WINDOWS`, reproduzindo a falha da `.28`.
- Verificação somente leitura no Deck confirmou hash e arquitetura exatos do trainer, symlink Mono 10.4.1, DLL Mono x64 e igualdade SHA-256 dos cinco arquivos críticos entre o clone privado e GE-Proton 11-6.
- A única pré-condição falsa era `/files/lib64`: ela não existe no layout real, embora `lib` e `lib/wine` existam. O teste foi alterado primeiro e falhou pelo motivo esperado; a implementação agora inclui `lib64` no `LD_LIBRARY_PATH` somente quando presente e confinado ao runtime privado.
- Próximo passo exato: rodar gates completos, empacotar `.29`, instalar pelo prompt oficial do Decky e relançar Mortal Shell pelo UniFiDeck. Aceitar somente se o evento indicar `mortal_shell_ge11_mono10`, a janela aparecer no Gamescope e o usuário confirmar fisicamente alternância e ON/OFF pela tela.

## Atualização `.30` — causa do exit 1 da `.29` corrigida

- A outra sessão instalou de fato `.29`; o Decky e os arquivos instalados confirmaram `0.1.0-experimental.29`.
- O journal sanitizado da sessão real PID 64148/start 4154462 mostrou: `container_reentry_verified`, `trainer_spawned.runtime_profile=mortal_shell_ge11_mono10`, `umu_exit_diagnostics` com `wine: Bad server socket 22 : Bad file descriptor`, e `trainer_exited` código 1 após 1102 ms. A falha ocorreu antes de processo persistente, janela, Gamescope ou clique.
- Causa-raiz: `build_sanitized_environment()` permitia qualquer chave com prefixo `WINE`, inclusive `WINESERVERSOCKET=22`. Wine 11 trata esse valor como número de descritor herdado; o novo processo não possuía o FD 22 e encerrou. O caminho privado historicamente funcional não reciclava essa variável.
- TDD RED: `python -m unittest tests_backend.test_environment.EnvironmentTests.test_does_not_replay_inherited_wine_server_file_descriptor -v` falhou porque o resultado ainda continha `WINESERVERSOCKET: 22`.
- Correção mínima: `trainer_relay/environment.py` remove somente `WINESERVERSOCKET` do ambiente reproduzido. `WINEPREFIX`, runtime privado, reentrada e atalho UniFiDeck permanecem inalterados.
- GREEN focado: 84 testes de ambiente/runner/watcher passaram. Gates completos: backend 299/299; packaging 8/8; frontend 217/217; Biome 75 arquivos; TypeScript produção/testes; Rollup build.
- `.30` empacotada com SHA-256 `f01f1df5946a425665bf7ce24d8eca0e246eb392e75b30b6eeea35bb6441b458`, transferida com hash idêntico e instalada pelo prompt oficial do Decky. O loader confirma `.30` carregada.
- Rollback da instalação `.29`: `/home/deck/Downloads/TrainerRelay-rollback-20260906-2054/TrainerRelay.experimental.29`.
- Probe reproduzível adicionado em `tools/diagnostics/deck_live_probe.ps1`. Com o jogo fechado, retornou `VERDICT=WAITING_FOR_GAME`; isso é espera, não PASS nem RED do novo runtime.
- Pesquisa causal: `docs/research/2026-09-06-fling-bad-server-socket-report-source.md`. O agente Luna solicitado atingiu o limite antes de entregar; a afirmação crítica foi verificada diretamente no código oficial do Wine 11.
- Estado de retomada: `.30` está instalada e aguardando uma sessão nova. O usuário deve abrir Mortal Shell pelo atalho normal do UniFiDeck, Force Compatibility desligado. Rodar o probe imediatamente; somente depois avançar, uma hipótese por vez, para janela/associação e toque/efeito. Não declarar consertado antes da validação física completa e do GOG.

## Atualização `.31` — crash do jogo ao anexar cedo demais

- A `.30` removeu o erro `Bad server socket` e alcançou `trainer_running`, mas duas execuções físicas repetiram um novo RED. Na primeira, o trainer foi lançado às `23:55:08.169Z`, ficou `running` em 3,523 s e o jogo desapareceu às `23:55:12.841Z`. Na segunda, os mesmos marcos ocorreram às `23:55:43.038Z`, 3,545 s e `23:55:47.734Z`.
- A ordem do encerramento está provada: primeiro o processo `Dungeonhaven.exe` cai; depois o watcher registra `session_ended` e envia `SIGTERM` apenas ao process group do trainer. Não há `trainer_exited` anterior nem sinal do TrainerRelay contra o grupo do jogo.
- O `CrashReportClient.log` da segunda execução abriu às `20:55:43`, exatamente no segundo do `trainer_spawned`, e fechou às `20:55:47`. O `484d2f02.game.log` contém as exceções de acessibilidade/Xalia resultantes da queda. O UniFiDeck reportou o UMU do jogo encerrando com código 0 após 15,9 s; não houve Force Compatibility.
- Diferencial causal: o mesmo executável, prefixo e clone privado GE11/Mono10 funcionaram no ensaio manual histórico quando o jogo já estava carregado. A integração automática `.30` anexava o FLiNG imediatamente na primeira detecção, cerca de 12 s após o UMU iniciar o jogo, durante a inicialização do Unreal/EOS.
- TDD RED: dois novos testes falharam porque `RelayWatcher` não possuía contrato de estabilização. GREEN: o watcher agora rastreia `session_observed_at`, reinicia a contagem quando PID/start time mudam e aceita `launch_stabilization_seconds` por identidade.
- `main.py` configura 30 s somente para `epic:0055e45ce7654c55aade646467349e83`. Jogos GOG e qualquer outra identidade mantêm atraso zero. Durante a espera o status é `waiting_for_game/game_stabilizing`; não há spawn, alteração de prefixo, Force Compatibility ou mudança no UniFiDeck.
- Gates `.31`: testes focados 2/2; watcher/environment/runtime/runner 88/88; wiring 11/11; backend 301/301; packaging 8/8; frontend 217/217; Biome 75 arquivos; TypeScript produção/testes; Rollup.
- Ferramentas de coleta: `tools/diagnostics/deck_live_probe.ps1` e `tools/diagnostics/deck_recent_logs.ps1`. A segunda filtra os eventos de ciclo de vida e journals sem despejar ambientes completos.
- Próximo gate: empacotar/instalar `.31`, lançar Mortal Shell normalmente, confirmar que não há `trainer_spawned` nos primeiros 30 s e que jogo + trainer permanecem vivos depois do attach. Só então validar janela no seletor Steam, clique físico ON/OFF e regressão GOG.
- Artefato `.31`: `TrainerRelay-v0.1.0-experimental.31.zip`, 788358 bytes, SHA-256 `9d7af1b29476b543db77c28d38e49c8647a2d6756308e89898f501146d619716`; hash idêntico no PC e em `/home/deck/Downloads/`.
- Rollback `.30` preservado em `/home/deck/Downloads/TrainerRelay-rollback-20260906-2114/TrainerRelay.experimental.30`; `package.json` verificado como `0.1.0-experimental.30`.
- Instalação `.31` concluída pelo fluxo autenticado `utilities/install_plugin` + `utilities/confirm_plugin_install`; prompt capturado com nome, versão, hash e `installType=2`, sem erro.
- Pós-instalação: `loader/get_plugins` reporta `Trainer Relay 0.1.0-experimental.31`, `load_type=1`, `disabled=false`; RPC retorna `waiting_for_game`; `package.json` e `main.py` instalados reportam `.31`; backend novo PID 68377 estava vivo.
- Checkpoint humano atual: o usuário deve iniciar Mortal Shell pelo atalho normal do UniFiDeck e não ativar Force Compatibility. Aguardar sem interagir; o agente deve observar remotamente os primeiros 30 s e pelo menos 60 s após o trainer aparecer.

## Atualização `.32` — teste host-direct e correção da leitura de timing

- O teste físico da `.31` manteve o PID 68841/start 4457160 aceito por 30,651 s antes do spawn. `container_reentry_verified` ocorreu às `00:19:20.416Z`, `trainer_spawned` às `00:19:20.425Z`, `trainer_running` 3,566 s depois e `session_ended` às `00:19:25.168Z`. Só depois o watcher enviou SIGTERM ao PGID 69253 do trainer.
- O journal do UniFiDeck confirma `steam force-compat lookup -> None`, GE-Proton11-6 selecionado e encerramento do UMU do jogo com código 0 após 47 s. Logs filtrados não contêm fatal, segfault ou exceção não tratada. O CrashReportClient já estava monitorando desde o início do jogo; ele não nasceu no attach, corrigindo a leitura anterior.
- Correção de conclusão: `.31` refutou apenas a suficiência de um PID estável por 30 segundos; não refutou a prontidão real do jogo. O PASS manual histórico anexou o trainer quando o jogo já estava aberto havia horas. `.31` anexou em cerca de 30 segundos e a sessão inteira terminou em cerca de 47 segundos. Topologia e prontidão continuam variáveis confundidas.
- TDD RED `.32`: três testes falharam pelo comportamento antigo (argv com launch-client, wineserver privado e watcher repassando launch-client). GREEN: quatro testes focados passaram após a correção.
- Implementação `.32`: `ScopedWineRuntime.launch_mode=host_direct`; o resolvedor retorna o wineserver da árvore GE11 selecionada; o runner reduz o ambiente do processo ao contexto host/display/locale, `WINEPREFIX`, `WINEDEBUG`, `WINESERVER` e `LD_LIBRARY_PATH`; o watcher marca essa rota exata como já pronta e registra `container_reentry=bypassed`. Nenhum `UMU_*`, `SteamGameId`, `PROTON_*`, `WINEFSYNC` ou outro estado derivado do jogo é reproduzido no processo host-direct.
- Escopo permanece fail-closed pela identidade Epic, SHA-256 x64 exato e GE-Proton11-6. Outros jogos, inclusive GOG, não recebem o perfil privado e mantêm o fluxo existente.
- Gates até este checkpoint: RED 3/3; GREEN focado 4/4; conjunto environment/runtime/runner/watcher/main 100/100. Ainda faltam suíte completa, frontend/package, empacotamento, instalação e validação física `.32`.
- Próximo passo: concluir gates, gerar/validar ZIP `.32`, preservar rollback `.31`, instalar pelo fluxo Decky e pedir novo lançamento normal do Mortal Shell. Aceitação: jogo e trainer vivos por 60 s, janela completa no seletor Steam, clique físico ON/OFF com efeito real, encerramento limpo e regressão GOG.
- Gates completos `.32`: backend 302/302; packaging 8/8; frontend 217/217; Biome 75 arquivos sem erro; TypeScript produção/testes passou; Rollup passou. ZIP `TrainerRelay.zip`: 791098 bytes, SHA-256 `81f40ee54afa11dfdaefa7d9c0368245b90e9a561a0249fdd10d908b8aad07af`, idêntico no PC e Deck.
- Rollback `.31` confirmado em `/home/deck/Downloads/TrainerRelay-rollback-20260906-2133/TrainerRelay.experimental.31`, com `package.json` reportando `0.1.0-experimental.31`.
- Instalação `.32` concluída pelo fluxo autenticado `utilities/install_plugin` + `utilities/confirm_plugin_install`; prompt capturado com hash correto, `installType=2` e sem erro. Loader confirma `0.1.0-experimental.32`, `load_type=1`, `disabled=false`; RPC está `waiting_for_game`.
- Checkpoint humano: iniciar Mortal Shell pelo atalho normal do UniFiDeck, Force Compatibility desligado. O agente deve observar a sessão por pelo menos 60 s depois do `trainer_running`; ainda não há PASS físico da `.32`.

## Atualização 2026-09-07 — `.32` é RED físico; pesquisa upstream integrada

- A execução física `.32` aceitou o jogo PID 70726/start 4558969. `container_reentry_verified` ocorreu às `00:36:18.961Z`, `trainer_spawned` às `00:36:18.970Z`, `trainer_running` às `00:36:22.619Z` e `session_ended` às `00:36:23.807Z`. O `SIGTERM` ao PGID 71154 do trainer veio somente às `00:36:23.864Z`.
- A ordem refuta o cleanup do TrainerRelay como causa do encerramento do jogo: o jogo desapareceu primeiro; depois o watcher encerrou somente o grupo que possuía. O UMU do jogo saiu com código 0 após aproximadamente 47,9 s. Logs filtrados não contêm fatal, segfault, exceção não tratada ou crash dump.
- A rota `.32` host-direct não reproduz configuração equivalente da sessão: remove `UMU_*`, `PROTON_*`, Steam vars e `WINEFSYNC`. A FAQ oficial do UMU exige `runinprefix`/`run` e configuração Proton/Wine equivalente para um segundo processo no mesmo prefixo. Isso torna `.32` um experimento histórico útil, mas não uma integração upstream-suportada.
- O banco oficial do UMU não contém `Mortal Shell`, o ID Epic observado nem `Dungeonhaven`; não existe protonfix conhecido ali para aplicar diretamente.
- Wine Mono e Gamescope continuam relevantes para os sintomas anteriores de renderização e clique deslocado, mas não explicam adequadamente o encerramento limpo atual. Não instalar .NET/vcrun via Winetricks no prefixo real.
- Pesquisa consolidada: `docs/research/2026-09-07-upstream-sidecar-lifecycle-investigation.md`.
- Coletor somente leitura criado para inventário de logs/crash: `.debug/deck_recent_crash_inventory.ps1`. Nenhum arquivo de produção foi alterado neste bloco.
- Próximo gate exato: iniciar o jogo normalmente, aguardar confirmação visual de que chegou ao menu e só então executar uma vez a rota manual privada historicamente funcional. Aceitar apenas com jogo + trainer vivos por 60 s. Se passar, substituir o atraso fixo por gate explícito/observável em TDD; se falhar, testar `runinprefix` com ambiente equivalente primeiro em cópia descartável.
- Preservação obrigatória: não ativar Force Compatibility, não alterar launch options do UniFiDeck, não executar winetricks no prefixo real, não trocar Proton do jogo e não alterar Mono global.

## Atualização 2026-09-07 — checkpoint humano aguardando reautenticação SSH

- O usuário confirmou que o jogo chegou ao estado pronto para o ensaio pós-menu.
- A tentativa automática de coleta via `192.168.1.247` falhou antes de executar qualquer comando remoto: `ssh: connect to host 192.168.1.247 port 22: Permission denied`. A chave temporária usada anteriormente foi rejeitada nesta sessão.
- Nenhuma alteração foi feita no Deck, no UniFiDeck, no jogo, no prefixo ou no plugin durante esta tentativa.
- Retomada: no terminal do usuário, executar `ssh -o PubkeyAuthentication=no deck@192.168.1.247`, digitar a senha diretamente no prompt (ela não aparece enquanto é digitada) e aguardar `(deck@steamdeck)$`. Depois disso, continuar a coleta somente leitura e executar o A/B pós-menu definido no relatório upstream.

## Atualização 2026-09-07 — SSH restaurado e RED reproduzido após habilitar Epic

- A conexão automatizada foi corrigida. A causa local foi dupla: o sandbox bloqueava TCP/22 sem escalonamento e a primeira chave foi criada com ACLs incompatíveis com o OpenSSH do Windows. Uma nova chave ED25519 foi criada no perfil do usuário e o host key previamente fixado continuou válido.
- A coleta remota mostrou a causa do ensaio sem attach: `settings.json` tinha `gog:1482265668.enabled=true` e `epic:0055e45ce7654c55aade646467349e83.enabled=false`. O watcher estava processando BioShock 2 GOG enquanto Mortal Shell Epic estava aberto.
- Para o A/B, somente o booleano Epic foi habilitado via atualização atômica. O jogo foi aceito no PID 29599/start 228528; `container_reentry_verified`/`trainer_spawned` ocorreram às `08:07:29.401Z`/`08:07:29.405Z`, `trainer_running` às `08:07:32.930Z` e `session_ended` às `08:07:34.065Z`. O SIGTERM do Relay veio depois, às `08:07:34.116Z`, no PGID do trainer.
- Resultado: RED reproduzido mesmo com o perfil correto e após o watcher conseguir anexar. O intervalo entre `trainer_running` e `session_ended` foi `1,135 s`; a ordem continua provando que o cleanup do Relay vem depois do encerramento do jogo.
- Após o RED, `settings.json` foi restaurado atomicamente para `epic...enabled=false`, com backup remoto do estado habilitado em `/home/deck/homebrew/settings/TrainerRelay/settings.json.bak-20260907-epic-enabled-state`. O próximo lançamento não será anexado automaticamente até haver uma nova correção deliberada.
- Não houve alteração no UniFiDeck, Force Compatibility, Proton selecionado, prefixo do jogo, Mono global ou launch options.
- Próximo passo técnico: instrumentar o boundary do attach para comparar o ambiente/sessão do PID 29599 com a rota `runinprefix` oficial, ou testar uma execução manual post-menu com o perfil Epic explicitamente habilitado apenas durante a janela controlada. Não declarar corrigido com base no attach atual.

## Atualização 2026-09-07 — baseline Epic também encerra sem TrainerRelay

- Após restaurar `epic...enabled=false`, o jogo foi iniciado pelo UniFiDeck sem qualquer evento `candidate_accepted`/`trainer_spawned` do perfil Epic.
- O UMU registrou `attempt 1 exit code: 0 (ran 47.2s)` e o systemd registrou apenas o consumo normal do escopo `app-steam-app2476768691-29316`; não houve `SIGTERM`, `kill`, `reap`, crash fatal ou encerramento pelo TrainerRelay.
- O `494334e2.game.log` contém inicialização normal de `Dungeonhaven-Win64-Shipping.exe`, superfícies Gamescope e EOSOverlay; há avisos `UNKNOWN (umu-0)`, `steam app id: 0` e falhas de bus name Steam no início, mas nenhum erro fatal.
- `CrashReportClient.log` terminou por `CrashReportClientApp RequestExit`, sem crash report. Isso é monitor do Unreal, não prova de crash do jogo.
- Conclusão atual: há um RED baseline independente do trainer — Mortal Shell Epic fecha sozinho após aproximadamente 47 s com TrainerRelay Epic desativado. O problema do trainer continua real e adicional, mas não explica este último encerramento.
- Não alterar mais o TrainerRelay até separar o baseline do UniFiDeck/UMU. Próxima coleta deve focar no caminho de lançamento Epic (`UNKNOWN/umu-0`, `SteamAppId=0`, bus name ausente) e não em Mono, Gamescope ou cliques.

## Atualização 2026-09-07 — comparação histórica e pesquisa UniFiDeck

- A comparação de logs confirmou uma sessão Epic estável em `2026-08-31`: mesmo prefixo, `GE-Proton11-6`, `Force Compatibility -> None` e a mesma linha resumida `argc=18 (game=0 user=0 egl=10)`; o UMU permaneceu vivo por `1161.4s`. Portanto, `game=0/user=0` isoladamente não é causa suficiente e não deve ser alterado às cegas.
- As sessões recentes curtas são diferentes apenas no resultado temporal: `15.9s`, `47.0s`, `47.2s`, `47.9s` e `50.4s`, todas com retorno UMU `0` quando não foram encerradas manualmente/por sinal. Isso caracteriza uma regressão/interação temporal do caminho atual, não um erro de carregamento imediato do Proton.
- A instalação remota do UniFiDeck é `0.7.4`. A documentação upstream descreve o caminho Epic como UniFiDeck -> Legendary -> UMU -> Proton, e a issue upstream #318 registra o mesmo padrão de container Epic que encerra com código `0` apesar de caminho de executável válido. Fontes: `https://github.com/mubaraknumann/unifideck/issues/318`, `https://github.com/mubaraknumann/unifideck/releases`.
- A varredura de `CrashContext` encontrou arquivos de sessões anteriores, mas sem `ErrorMessage`/`CrashType` útil e sem um `Dungeonhaven.log` correspondente disponível no prefixo. O `CrashReportClient` da sessão de `47.2s` apenas encerrou seu monitor após o processo do jogo terminar; não é evidência de que ele tenha causado a saída.
- O diagnóstico somente leitura confirmou novamente: plugin `0.1.0-experimental.32` vivo, Epic desativado, jogo ausente, `VERDICT=WAITING_FOR_GAME`; nenhuma nova alteração foi aplicada.
- Segurança: os CrashContext contêm argumentos de autenticação emitidos pelo launcher. Eles não foram copiados para este handoff nem devem ser reproduzidos em relatórios ou commits.

### Estado atual e retomada

1. Manter `epic:0055e45ce7654c55aade646467349e83.enabled=false` até o baseline Epic ficar estável; GOG permanece fora do escopo desta falha.
2. Não ativar Force Compatibility, não trocar Proton, não usar Winetricks no prefixo real e não alterar launch options do UniFiDeck.
3. O próximo ensaio deve ser uma única abertura normal pelo UniFiDeck, com coleta temporal do processo e do journal desde o clique até a saída. Se repetir `exit code 0`, investigar o caminho UniFiDeck/UMU (incluindo a issue #318) antes de reativar o trainer.
4. Só depois que o jogo permanecer vivo por pelo menos 60 s com Relay Epic desligado, reabrir o experimento do trainer com uma variável por vez e comparar o ambiente suportado por `runinprefix`.

## Atualização 2026-09-07 — diferença de runtime observada, sem correção aplicada

- A sessão estável de `2026-08-31` e a sessão que encerrou usaram UMU `1.4.4`, SteamRT4, GE-Proton11-6 e o mesmo prefixo. Ambas reportaram `UNKNOWN (umu-0)`, `steam app id: 0` e o aviso benigno sobre o parent de `/home`.
- A diferença observada nos logs é que a sessão curta registrou cinco tentativas de `Failed to find bus name com.steampowered.App...` e depois iniciou `steam-runtime-launch-client`; a sessão estável não registrou essas linhas. Isso é uma hipótese de topologia/serviço do runtime, não causa fechada: a documentação do UMU/Proton também usa `steam-runtime-launch-client` em sessões normais de depuração.
- A busca upstream encontrou a issue `mubaraknumann/unifideck#318`, com o mesmo padrão de jogos Epic detectados, executável válido e encerramento do container com código `0`. Ela permanece uma referência de investigação, não uma solução comprovada para Mortal Shell.
- Não foram alterados launch options, Steam, UniFiDeck, Proton, prefixo, runtime ou arquivos de jogo. O Trainer Relay permaneceu com Epic desativado.

## Atualização 2026-09-07 — retomada do objetivo completo

- O objetivo original continua aberto: janela real do FLiNG no seletor Steam, alternância jogo/trainer e toggles físicos pela tela, preservando o UniFiDeck e sem Force Compatibility.
- Auditoria local confirmou que a `.32` instalada usa `ScopedWineRuntime.launch_mode=host_direct`, executa o Wine privado diretamente e marca `container_reentry=bypassed`. Esse caminho foi apenas um experimento de isolamento e ainda não é a integração UMU/Proton equivalente ao jogo.
- O estado remoto atual está limpo para novo ensaio: `epic...enabled=false`, nenhum processo `Dungeonhaven`, FLiNG ou `umu-run` ativo, nenhum serviço de diagnóstico antigo ativo e o probe retorna `WAITING_FOR_GAME`. Não foram enviados sinais nem alterados processos.
- Não foi aplicada correção de código nesta retomada. O próximo ensaio humano necessário é abrir Mortal Shell uma vez pelo UniFiDeck normal, sem Force Compatibility e sem tocar em Steam/cheats, deixando-o aberto no menu. A coleta deve capturar a árvore do processo, janela, bus UMU e saída; só depois disso será escolhida e testada a menor correção entre `runinprefix` equivalente e uma espera por prontidão real.

## Atualização 2026-09-07 — nova reprodução ao vivo `.32` e separação temporal

- No ensaio iniciado após o checkpoint humano, o plugin `.32` aceitou o processo Epic PID `33509`/start `1467537`; houve `container_reentry_verified` e `trainer_spawned` às `11:33:59.815Z`/`11:33:59.818Z`, com `runtime_profile=mortal_shell_ge11_mono10` e `container_reentry=bypassed`.
- O trainer foi marcado como `trainer_running` às `11:34:03.411Z`, após `3559 ms`. Isso mostra que o Wine privado chegou a manter o processo do trainer vivo naquele intervalo; não houve `trainer_exited` antes do fim da sessão.
- A sessão do jogo terminou às `11:34:04.552Z`; somente depois, às `11:34:04.607Z`, o watcher enviou `SIGTERM` ao PGID próprio `33940`. O UMU registrou `exit code: 0 (ran 47.6s)`. A ordem novamente não sustenta que o cleanup do Relay tenha matado o jogo.
- O jogo foi iniciado por `/home/deck/Games/MortalShell/Dungeonhaven.exe` com `argc=18 (game=0 user=0 egl=10)`. O log contém `Dungeonhaven-Win64-Shipping.exe`, mas não um erro fatal novo. A sessão histórica estável `adebe218` teve os mesmos avisos Proton/parent `/home` e durou `1161.4s`; portanto esses avisos não são causa suficiente.
- A janela do trainer não apareceu na lista Gamescope observada após o encerramento. Como a associação só é tentada nos atrasos de `5/10/15 s` após a confirmação de reentrada, essa sessão acabou aproximadamente `4.7 s` depois do spawn: não houve tempo para o primeiro `window_association`. Isso explica por que este ensaio não valida nem refuta a seleção Steam.
- O estado remoto foi verificado após a limpeza: `epic...enabled=false`, GOG permanece habilitado, nenhum processo do jogo/trainer/UMU ativo. Nenhuma configuração do UniFiDeck, Force Compatibility, Proton, prefixo ou Mono global foi alterada neste bloco.
- Próxima ação segura: repetir uma abertura normal com Epic desativado para confirmar se o baseline ainda termina perto de `47 s`; se terminar, continuar a investigação UniFiDeck/UMU antes de reativar o trainer. Não trocar ainda `host_direct` por `container_reentry` sem um teste RED específico, pois a rota container já teve falha histórica de `Bad server socket`.

## Atualização 2026-09-07 — atalho recuperado e correção TDD interrompida

- Foi comprovado que o suposto baseline com Epic desativado ainda estava contaminado pelo launch option persistente `UMU_CONTAINER_NSENTER=1 %command% epic:0055...`. A comparação entre a sessão estável `adebe218` e a curta `ab1998d9` mostrou falhas de bus e uso de `command-launcher service` somente na sessão curta.
- `.debug/restore-mortal-shell-launch-options.ps1` validou app ID, launcher UniFiDeck e valor exato antes de restaurar `epic:0055e45ce7654c55aade646467349e83`. A API Steam retornou `status=restored` e `verified=true`.
- Depois da restauração, o usuário abriu o jogo normalmente. O probe observou `Dungeonhaven.exe`/`Dungeonhaven-Win64-Shipping.exe` vivos e a janela `Mortal Shell`; nenhum trainer novo foi iniciado porque o perfil Epic continua desativado.
- Causa arquitetural isolada: `ProcessDiscoverer` exige reentrada, mas o perfil `.32` comprovado usa `launch_mode=host_direct` e a ignora. Assim, o Relay alterava a topologia do UniFiDeck sem necessidade para esse perfil exato.
- TDD RED confirmado para a correção: 2 testes, 0 passaram, 1 falhou e 1 terminou em erro esperado por API ausente. Depois disso foram feitas alterações parciais em `trainer_relay/process.py`, `trainer_relay/watcher.py`, `tests_backend/test_process.py` e `tests_backend/test_watcher.py`.
- A implementação foi interrompida a pedido do usuário antes de ligar a política à descoberta e reorganizar `_spawn()`. Nenhum teste pós-alteração, pacote, instalação ou mudança remota foi feito. Não instalar o working tree atual.
- Relatório consolidado criado em `docs/notes/2026-09-07-mortal-shell-fling-outcomes-report.md` com sucessos, falhas, evidências, incertezas e protocolo de retomada.

## Atualização 2026-09-07 — correção allowlisted concluída localmente, Deck ainda não atualizado

- A execução do plano `docs/superpowers/plans/2026-09-07-mortal-shell-fling-evidence-first-correction-plan.md` avançou pelas tarefas de evidência, runtime e política.
- Foi criado `tools/diagnostics/evaluate_mortal_shell_run.py` com veredito conservador: `PASS` somente após baseline/menu/recipe/access confirmados, identidades de jogo e trainer estáveis por 60 s, amostras sem lacunas >45 s e sem saída prematura. Testes: 6/6.
- O backend agora expõe `get_relay_launch_policy({identity, trainerPath})`. Para o par exato Epic + trainer SHA-256 `872935c570a105d81db056264e540ffc254b2ee3cf63407afa9be65eaca41fb8` + PE x64, retorna `host_direct_candidate`; divergência retorna `blocked`; GOG e demais identidades retornam `container_reentry`.
- O frontend consulta essa política antes de preparar o atalho. O candidato exato não adiciona `UMU_CONTAINER_NSENTER`; uma divergência ou erro bloqueia. O fluxo GOG permanece com a preparação de contêiner existente.
- A exceção host-direct ficou ligada ao watcher somente para o mesmo identity/hash/arquitetura e exige runtime privado resolvido; ela não chama probe de contêiner, não usa bus falso, não cria comando de contêiner e falha fechado como `scoped_runtime_unavailable`/`scoped_runtime_host_invalid`.
- O contexto de cheats do host-direct falha fechado como `command_route_unsupported`, sem alegar autoridade de toggle. O modo genérico mantém o caminho de comandos existente.
- TDD/GREEN local: Vitest `224/224`; backend afetado `181/181`; backend completo `315/315`; packaging `8/8`; Biome `75 arquivos`; TypeScript produção/testes; Rollup; `TrainerRelay.zip` gerado localmente.
- O working tree continua deliberadamente sujo com alterações anteriores do projeto. Nenhum `git reset`, `git restore` amplo ou Force Compatibility foi usado. O pacote novo ainda não foi instalado no Deck.

### Próximo checkpoint físico

1. Não substituir o plugin instalado enquanto o jogo estiver aberto; fechar o jogo de forma normal e preservar o rollback remoto existente.
2. Antes de instalar, registrar versão/hash do pacote e fazer backup somente do pacote/configuração do plugin; não alterar launch options do Steam.
3. Instalar o ZIP pelo prompt oficial do Decky, reiniciar/recarregar apenas o plugin se o fluxo exigir e confirmar que Epic permanece desabilitado até o pacote novo estar carregado.
4. Abrir Mortal Shell pelo UniFiDeck normal, Force Compatibility desligado. Selecionar o trainer pelo plugin e deixar o jogo chegar ao menu; observar o probe sem tocar nos toggles.
5. Aceitar somente se o registro produzir duas identidades estáveis por 60 s e o jogo não sair. Depois confirmar janela completa no seletor Steam, alternância, clique físico/touch/trackpad e toggle ON/OFF com efeito real. Repetir GOG e persistência do atalho.

### Estado GitHub

- Branch: `feat/trainer-relay`.
- Nenhum commit/push deste bloco. Fazer staging explícito somente após a validação física e revisar arquivos anteriores antes de qualquer commit.

## Atualização 2026-09-07 — candidato `.33` pronto; validação remota bloqueada

- A versão foi incrementada para `0.1.0-experimental.33` em `package.json`, `main.py`, README e teste de layout para não colidir com o `.32` instalado.
- Gates finais locais: Vitest `225/225`; backend completo `315/315`; packaging `8/8`; Biome `75 arquivos`; TypeScript produção/testes; `compileall`; Rollup; empacotamento concluído.
- ZIP: `C:/Users/slvma/Downloads/Github/TrainerRelay/TrainerRelay.zip`.
- SHA-256 do ZIP `.33`: `030C7DA3D6EC62E7DE0BD8CECB1A70681492D5393847C438033A05957AA8E484`.
- O teste remoto somente leitura não pôde conectar em `192.168.1.247:22` e `Test-Connection` também falhou. Nenhuma instalação, reinício, alteração de settings, launch option, Force Compatibility, Proton, prefixo ou Mono foi feita nesta etapa.
- Para retomar: fechar Mortal Shell normalmente, acordar/verificar o Deck na rede, confirmar que SSH responde, então transferir o ZIP com hash, instalar pelo prompt oficial do Decky e iniciar a sequência física dos gates. Não instalar enquanto a sessão atual estiver aberta.

## Atualização 2026-09-07 — `.33` instalada e pronta para ensaio

- O Deck voltou à rede; o probe inicial confirmou `WAITING_FOR_GAME`, sem processo Mortal Shell/FLiNG ativo.
- O ZIP `.33` foi transferido para `/home/deck/Downloads/TrainerRelay-v0.1.0-experimental.33.zip` e o SHA-256 remoto coincidiu com o local: `030c7da3d6ec62e7de0bd8cecb1a70681492d5393847c438033a05957aa8e484`.
- Rollback criado e verificado em `/home/deck/Downloads/TrainerRelay-rollback-20260907-1009/`: plugin `.32` e settings presentes.
- A instalação oficial via `SharedJSContext`/`utilities/install_plugin` + confirmação retornou prompt da versão `.33`, hash correto, `installType=2` e nenhum erro.
- Probe pós-instalação: loader/backend reportam `0.1.0-experimental.33`, processo Trainer Relay vivo, runtime privado presente e Mono `wine-mono-10.4.1`; jogo ainda fechado.
- Próximo checkpoint humano: iniciar Mortal Shell pelo UniFiDeck normal, Force Compatibility desligado, chegar ao menu e não tocar nos cheats. Depois observar estabilidade, janela no seletor Steam e interação física.

## Atualização `.34` — detecção do bus host e resultado RED após attach (2026-09-07)

- A versão `.34` foi construída para detectar o barramento da sessão real do usuário (`/run/user/<uid>/bus`) quando o processo Decky não exporta `DBUS_SESSION_BUS_ADDRESS`; a implementação valida `HOME`, `PATH`, `XDG_RUNTIME_DIR`, `DISPLAY`, `WINEPREFIX` e o prefixo esperado antes do host-direct.
- Gates locais após essa alteração: 20 testes backend/packaging direcionados passaram; TypeScript de produção/testes, build e empacotamento passaram. ZIP local: `TrainerRelay.zip`; SHA-256: `053fd786880f2dc89b78a63f7f3efc7a1deb401ccfcda32a1b9445b57879ea04`.
- O `.34` foi instalado pelo fluxo oficial do Decky e carregado; a comparação do hash precisou usar a string hexadecimal minúscula exata esperada pelo Decky. O plugin remoto reporta `0.1.0-experimental.34`.
- Com Mortal Shell aberto, o `.34` avançou até `trainer_spawned` (`runtime_profile=mortal_shell_ge11_mono10`, `container_reentry=bypassed`) e `trainer_running`; porém a sessão do jogo terminou cerca de 1,8 s depois. Não houve `trainer_exited` antes de `session_ended`, portanto a evidência indica que o jogo morreu primeiro e o watcher apenas limpou o trainer.
- Estado seguro atual: plugin `.34` ativo; perfil Epic temporariamente desabilitado via RPC oficial para impedir attach precoce; GOG continua habilitado. Nenhuma alteração de Force Compatibility, launch option do UniFiDeck, Proton global, prefixo global ou Mono global foi feita.
- Retomada: iniciar Mortal Shell normalmente, sem Force Compatibility, chegar ao menu principal e confirmar esse checkpoint; então reativar apenas o perfil Epic e observar o attach controlado.

## A/B pós-menu `.34` — RED reproduzido (2026-09-07)

- O usuário confirmou o menu principal; o perfil Epic foi reativado somente pelo RPC oficial, sem alterar launch options.
- Segunda execução `.34`: `trainer_spawned` às `13:52:54.008Z`, `trainer_running` às `13:52:57.582Z` (`elapsed_ms=3546`), `session_ended` às `13:52:58.726Z`. O processo do jogo desapareceu primeiro; não houve `trainer_exited` antes do fim da sessão.
- Os PIDs/start-times da sessão foram `42140/2278662`; o grupo criado para o trainer foi `42762`. A rota reportou `runtime_profile=mortal_shell_ge11_mono10` e `container_reentry=bypassed`.
- Resultado: host-direct falha mesmo após confirmação do menu. Não fazer nova tentativa de atraso fixo nem manter essa rota como correção física.
- Após a coleta, Epic foi desabilitado novamente via RPC oficial; GOG continua `enabled=true`. Estado atual seguro para o próximo ensaio: sem attach automático.
- Próximo passo: iniciar o jogo normalmente, confirmar o menu, e executar uma única receita manual pós-menu com o runtime privado GE11/Mono10 e o wineserver GE11, coletando apenas estabilidade e processo. Se o manual passar, portar a receita para uma rota suportada; se falhar, capturar a causa antes de outra alteração.

## Reprodução observada pelo usuário — trainer e jogo fecharam juntos (2026-09-07)

- Após o usuário confirmar que estava pronto, o perfil Epic foi habilitado pelo RPC oficial sem alterar Force Compatibility, UniFiDeck, launch options, Proton global, prefixo ou Mono global.
- Linha do Relay: `trainer_spawned` às `14:12:31.295Z` para `PID 45471/start_time=2408386`; `trainer_running` às `14:12:35.506Z` (`elapsed_ms=4173`); `window_association` às `14:12:36.885Z`; `session_ended` às `14:12:37.994Z`.
- O usuário observou que o trainer abriu e fechou junto com o jogo. Não houve `trainer_exited` antes de `session_ended`; portanto o log não atribui o primeiro encerramento ao executável do trainer. A sessão foi encerrada pelo lado do jogo/host e a limpeza fechou o restante.
- Resultado: RED reproduzido, com janela alcançada mas estabilidade perdida em aproximadamente 6,7 s após o spawn. Não aumentar delay e não promover `host_direct`.
- Após a coleta, o perfil Epic foi desabilitado novamente pelo RPC oficial; GOG permanece habilitado.

## Correção local `.35` — abandonar host-direct e usar reentrada oficial (2026-09-07)

- O RED físico mostrou que `host_direct` abre a janela, mas encerra a sessão do Mortal Shell em poucos segundos. O caminho foi retirado da política do trainer exacto.
- O perfil exacto agora exige `container_reentry`; o runtime privado GE11/Mono10 é passado pelo `steam-runtime-launch-client` com o bus verificado e `PROTON_VERB=runinprefix`.
- A política RPC do hash/arquitetura allowlisted agora retorna `container_reentry`, e a migração prepara `UMU_CONTAINER_NSENTER=1 %command% ...`; Force Compatibility, UniFiDeck, Proton global, prefixo e Mono global não são alterados pelo código.
- TDD/GREEN local: Vitest `225/225`; backend completo sem falhas; packaging `8/8`; Biome `75 arquivos`; TypeScript de produção/testes; `compileall`; Rollup/build.
- Pacote local `0.1.0-experimental.35`: `TrainerRelay.zip`, SHA-256 `227A1257AF320CB62EBAE71718598A17F8048C6EE62EB2491B2CD66145E60A57`.
- O `.35` ainda não foi instalado no Deck. Manter Epic desabilitado até criar rollback, transferir o ZIP e confirmar o hash remoto.

## `.35` instalado e rota UMU preparada (2026-09-07)

- Pacote `.35` transferido para `/home/deck/Downloads/TrainerRelay-v0.1.0-experimental.35.zip`; SHA-256 remoto conferido: `227a1257af320cb62ebae71718598a17f8048c6ee62eb2491b2cd66145e60a57`.
- Rollback por cópia criado em `/home/deck/Downloads/TrainerRelay-rollback-20260907-1125/`, contendo plugin `.34` e settings antes da instalação.
- Instalação oficial Decky confirmou `0.1.0-experimental.35`, hash correto e `installType=2`; probe confirmou backend `.35`, runtime privado presente e `wine-mono-10.4.1`.
- Launch options foram lidas como o original e então preparadas/verificadas pela API oficial da Steam para `UMU_CONTAINER_NSENTER=1 %command% epic:0055e45ce7654c55aade646467349e83`. Nenhuma Force Compatibility foi alterada.
- Perfil Epic foi habilitado via RPC oficial; no momento do registro não havia jogo/trainer em execução. Próximo checkpoint humano: iniciar pelo UniFiDeck normal e confirmar o menu; depois observar a rota `container_reentry` antes de testar controles.

## Resultado do ensaio oficial `.35` — RED de estabilidade e restauração segura (2026-09-07)

- A launch option preparada pela API oficial foi verificada como `UMU_CONTAINER_NSENTER=1 %command% epic:0055e45ce7654c55aade646467349e83`; o perfil Epic foi habilitado somente durante o ensaio. Force Compatibility não foi usado.
- A rota oficial confirmou a infraestrutura esperada: `container_reentry_verified` às `14:35:03.741Z`, `trainer_spawned` às `14:35:03.749Z` com `runtime_profile=mortal_shell_ge11_mono10`, `container_reentry_confirmed` às `14:35:05.868Z` (`elapsed_ms=16`) e `trainer_running` às `14:35:08.079Z` (`elapsed_ms=4318`).
- Mesmo com a reentrada confirmada, a sessão terminou às `14:35:09.972Z`. Não houve `trainer_exited` antes de `session_ended`; depois disso, o watcher enviou o sinal de limpeza ao grupo do trainer. O relato físico foi: jogo e trainer fecharam juntos.
- Portanto, o `.35` corrigiu a topologia de lançamento (a reentrada UMU ocorreu), mas não corrigiu a estabilidade do jogo. O problema restante não é mais “bus ausente” nem apenas host-direct; ainda não há prova de que o FLiNG seja o primeiro processo a encerrar.
- A coleta encontrou `CrashReportClient.log` iniciado no mesmo intervalo, mas o trecho final apenas registra a saída normal do próprio CrashReportClient (`RequestExit`); isso não identifica a causa do encerramento de `Dungeonhaven.exe`.
- `gameprocess_log.txt` mostra os PIDs do launcher UniFiDeck acompanhados pelo Steam e encerrados aproximadamente no mesmo intervalo (`exit code -1` para o wrapper e `exit code 0` para o launcher). Isso confirma o fim da sessão, mas não fornece a exceção do jogo.
- Após a coleta, o perfil Epic foi desabilitado pelo RPC oficial e a launch option foi restaurada/verificada como `epic:0055e45ce7654c55aade646467349e83`. GOG permaneceu habilitado. O plugin `.35` continua instalado; não há jogo, trainer ou UMU ativo.
- Estado seguro de retomada: não iniciar outro ensaio até separar a causa no log do jogo/CrashReport e comparar a receita de reentrada com e sem o runtime privado/Mono10. Não alterar Force Compatibility, Proton global, prefixo ou Mono global.

### Próxima investigação obrigatória

1. Ler somente os artefatos do prefixo Mortal Shell e os logs Steam/Proton no intervalo do RED, priorizando `Dungeonhaven`/`Saved/Logs`, `Saved/Crashes`, `coredumpctl` e linhas associadas aos PIDs; não tratar `CrashReportClient.log` como causa sem evidência.
2. Fazer uma A/B mínima e reversível da receita oficial: jogo sem trainer, trainer com reentrada usando o ambiente do jogo, e somente depois runtime privado/Mono10 se necessário. Cada ensaio deve ter baseline e rollback claros.
3. Só após estabilidade de 60 s repetir os gates de janela no seletor Steam, alternância, clique/toggle e efeito real; o clique deslocado continua um problema separado e ainda não foi revalidado nesta rota.

## Encerramento desta retomada — sem correção física comprovada (2026-09-07)

- A leitura adicional do `journalctl` mostrou o fluxo normal do UniFiDeck: GE-Proton11-6 selecionado, `steam force-compat lookup -> None`, comando do jogo iniciado com `env -u LD_LIBRARY_PATH`, e `umu` encerrando com código `0` após aproximadamente 50,3 s. Não apareceu exceção de `Dungeonhaven`, dump ou causa fatal.
- O mesmo intervalo contém apenas avisos conhecidos do overlay Steam sobre `LD_PRELOAD`/classe ELF e sincronização de saves; eles não foram demonstrados como causa e não foram alterados.
- O usuário decidiu desistir da investigação neste momento. Nenhuma nova alteração de código ou configuração remota foi feita após o teste `.35`.
- Estado final seguro confirmado na retomada: jogo/trainer/UMU fechados; Epic desabilitado; launch option restaurada ao valor original; GOG habilitado; Force Compatibility não usado; rollback `.34` preservado; `.35` permanece instalado, mas não está sendo exercitado.
- Objetivo final permanece **não comprovado**: estabilidade de 60 s, alternância no seletor Steam, clique/toggle físico e efeito real dos cheats na rota Epic não foram validados nesta versão.

## `.36` — ACK real de reentrada e checkpoint físico pendente (2026-09-07)

- Corrigido o falso positivo do runner: a rota `container_reentry` agora confirma somente após ACK emitido dentro do launch-client, vinculado ao PID/start-time da sessão e ao bus exato; host-direct não fabrica `container_reentry_confirmed`.
- Validação local aprovada: runner `22/22`, módulos afetados `134/134`, Vitest `225/225`, backend, packaging, lint, TypeScript, compileall e build aprovados.
- `.36` instalada oficialmente no Deck; SHA-256 `68c989eb3b8c183ca58930680a8bd7a4a06420bb2993601b19b7e94b31b8f3e6`; rollback em `/home/deck/Downloads/TrainerRelay-rollback-20260907-1205/`.
- Estado de teste: atalho temporariamente preparado com `UMU_CONTAINER_NSENTER=1`, Epic habilitado, GOG habilitado, Force Compatibility não usado; jogo aguardando abertura humana.
- Não declarar estabilidade nem interação até observar o novo ACK, manter jogo/trainer vivos por 60 s, alternar no seletor Steam, clicar nos toggles e comprovar Infinite Stamina ON/OFF.

## Resultado da receita manual (2026-09-07)

- A receita manual passou as validações do trainer/runtime e abriu a janela FLiNG `780x666`, mas o jogo desapareceu enquanto o trainer continuou vivo. O log do unit registrou uma asserção Mono `gpath.c:115`.
- A tentativa foi encerrada e limpa; não houve alteração de Force Compatibility, UniFiDeck, launch options, prefixo real ou Mono global.
- A hipótese “somente o watcher host-direct mata o jogo” foi enfraquecida. Ainda falta separar menu de cena jogável e comparar a rota oficial de sessão (`runinprefix`) antes de promover qualquer correção.

## Resultado do ensaio físico `.36` — ACK real, estabilidade ainda RED (2026-09-07)

- O `.36` foi exercitado com a opção temporária `UMU_CONTAINER_NSENTER=1 %command% epic:0055e45ce7654c55aade646467349e83`, Epic habilitado apenas durante o ensaio, GOG habilitado e Force Compatibility intocado.
- A correção de telemetria foi confirmada: `container_reentry_verified` às `15:04:00.920Z`, `trainer_spawned` às `15:04:00.929Z`, ACK real `container_reentry_confirmed` às `15:04:02.966Z` (`elapsed_ms=27`) e `trainer_running` às `15:04:05.016Z`.
- Mesmo com o ACK emitido pelo comando dentro do `steam-runtime-launch-client`, a sessão terminou às `15:04:06.755Z`. Não houve `trainer_exited` antes de `session_ended`; o watcher enviou `SIGTERM` ao PGID `50728` somente na limpeza (`15:04:06.811Z`). O usuário confirmou que jogo e trainer fecharam.
- O inventário do intervalo encontrou `CrashReportClient.log` iniciado e encerrado normalmente, além de `77b099ad.game.log` com cancelamentos de tarefas Xalia durante o encerramento. Não apareceu exceção fatal, dump, sinal externo ou erro explícito de `Dungeonhaven.exe`; isso não identifica a causa do término.
- A opção Steam foi restaurada e verificada como `epic:0055e45ce7654c55aade646467349e83`; o perfil Epic foi desabilitado novamente por RPC oficial. Probe final: `WAITING_FOR_GAME`, nenhum jogo/trainer/UMU ativo. GOG permanece habilitado.
- Conclusão: o `.36` eliminou o falso positivo de confirmação, mas não resolveu a estabilidade. A evidência atual desloca a investigação para a interação entre o processo Wine do FLiNG, o wineserver/prefixo compartilhado e o processo do jogo; não há base para atribuir o encerramento ao `SIGTERM` do Relay.

### Próxima retomada segura

1. Manter o Deck nesse estado restaurado; não usar Force Compatibility, não trocar Proton global e não instalar Mono/.NET.
2. Fazer uma A/B com baseline do jogo sem sidecar, depois um processo Wine inofensivo no mesmo `launch-client`/bus e somente depois o FLiNG, coletando PID/PPID/PGID/cgroup/sinal do jogo e do trainer.
3. Não testar clique, toggles ou janela do Steam antes de a sessão sobreviver pelo menos 60 s.
