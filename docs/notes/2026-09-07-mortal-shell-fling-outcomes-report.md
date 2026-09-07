# Relatório consolidado — Mortal Shell Epic + FLiNG no Trainer Relay

Data: 2026-09-07
Estado: diagnóstico parcialmente fechado; correção final ainda não concluída nem instalada.

## Objetivo e limites

O objetivo é abrir o Mortal Shell Epic pelo atalho normal do UniFiDeck e executar o FLiNG Trainer como uma segunda janela selecionável pelo botão Steam, com toggles clicáveis e cheats produzindo efeito real. O jogo deve continuar funcionando sem Force Compatibility.

Limites mantidos:

- não forçar compatibilidade no atalho Steam;
- não substituir o Proton selecionado pelo UniFiDeck;
- não alterar o prefixo real com Winetricks/.NET;
- não trocar o Wine Mono global;
- não considerar renderização, inspeção estática ou hotkey sintética como prova de cheat funcional;
- preservar rollback antes de instalações no Deck.

## O que deu certo

### 1. O caminho funcional foi demonstrado fisicamente

Uma execução manual controlada usando:

- o prefixo real do Mortal Shell;
- Wine client privado baseado no mesmo GE-Proton11-6 do jogo;
- wineserver do GE-Proton11-6 selecionado;
- Wine Mono 10.4.1 isolado no clone privado;
- `DISPLAY=:1`;
- associação da janela ao Steam app `2476768691`;

produziu a janela real e completa do FLiNG (`780x666`) no seletor do Gamescope. O usuário confirmou que conseguia alternar entre jogo e trainer pelo botão Steam. Em um dos passes anteriores, o usuário também confirmou que `Infinite Stamina` ligava, produzia efeito e voltava ao normal quando desligado.

Conclusão: o executável do trainer, o prefixo, o jogo e os cheats são compatíveis. O problema atual não é “o FLiNG nunca funciona no Deck”; é a integração automática ter divergido do lançamento manual comprovado.

### 2. O perfil privado foi isolado sem alterar o Mono global

O runtime privado foi validado por identidade Epic, SHA-256 exato do trainer, arquitetura x64 e GE-Proton11-6. Arquivos críticos foram comparados byte a byte com a árvore selecionada do Proton. O symlink privado aponta para `wine-mono-10.4.1`; o Mono global permaneceu intacto.

### 3. Várias falhas intermediárias foram identificadas corretamente

- A ausência de `lib64` no layout real do GE-Proton11-6 era uma validação incorreta do perfil; `lib64` passou a ser opcional.
- `WINESERVERSOCKET=22` era um descritor herdado inválido. Reproduzi-lo no novo processo causava `wine: Bad server socket 22 : Bad file descriptor`; a variável foi removida do ambiente sanitizado.
- O watcher foi endurecido para não morrer silenciosamente após uma exceção inesperada.
- A janela do trainer pôde ser associada ao app Steam por `STEAM_GAME`/`GAMESCOPE_FOCUSABLE_WINDOWS` em ensaio controlado.

### 4. O atalho do UniFiDeck foi recuperado

Foi descoberto que o atalho permanecia com:

```text
UMU_CONTAINER_NSENTER=1 %command% epic:0055e45ce7654c55aade646467349e83
```

mesmo quando o perfil Epic do Relay estava desativado. Um script guardado conferiu app ID, launcher UniFiDeck e valor exato antes de restaurar:

```text
epic:0055e45ce7654c55aade646467349e83
```

A resposta da API Steam confirmou `status=restored` e `verified=true`. Não houve alteração de Force Compatibility, Proton, prefixo, jogo ou Mono.

Após a restauração, o usuário abriu o jogo normalmente. O probe de 2026-09-07 observou `Dungeonhaven.exe` e `Dungeonhaven-Win64-Shipping.exe` vivos, janela `Mortal Shell` em `1280x800` e app Steam `2476768691`. O trainer não foi iniciado porque o perfil Epic continuava desativado; esse era o estado seguro esperado.

## O que deu errado

### 1. A integração passou a exigir algo que o caminho funcional não usa

Na versão experimental `.32`, `ProcessDiscoverer` rejeita qualquer sessão sem `UMU_CONTAINER_NSENTER=1`. Depois dessa exigência, o watcher resolve o perfil privado como `launch_mode=host_direct` e ignora a reentrada de container ao iniciar o trainer.

Isso é uma contradição de arquitetura:

1. o jogo é obrigado a mudar sua topologia de lançamento para expor a reentrada;
2. o trainer comprovado não usa essa reentrada;
3. a mudança fica persistida no atalho do UniFiDeck e afeta o jogo mesmo com o Relay Epic desativado.

Esta é a explicação mais forte e diretamente demonstrada para a regressão “antes funcionava, agora abre e fecha”.

### 2. O baseline anterior estava contaminado

Um teste tratado inicialmente como “Epic desativado” não era um baseline limpo: desativar o perfil no `settings.json` impedia o spawn do trainer, mas não removia `UMU_CONTAINER_NSENTER=1` do atalho Steam. Portanto, a execução ainda usava a topologia modificada.

Comparação dos logs:

- sessão histórica estável `adebe218.game.log`: aproximadamente `1161,4 s`;
- sessão curta `ab1998d9.game.log`: aproximadamente `47,6 s`;
- somente na sessão curta apareceram cinco falhas `Failed to find bus name com.steampowered.App...` e `Starting program with command-launcher service`.

Os logs não mostram o Relay matando o jogo: primeiro o processo do jogo desaparece; só depois o watcher envia `SIGTERM` ao grupo próprio do trainer.

### 3. As versões automáticas corrigiram sintomas diferentes, mas não reproduziram o PASS completo

- `.28`: perfil real não era selecionado por causa da suposição incorreta sobre `lib64`; caiu em `umu_direct` e não mostrou janela útil.
- `.29`: selecionou o perfil, mas o trainer terminou com `Bad server socket` por reutilizar `WINESERVERSOCKET`.
- `.30`: removeu o socket inválido e chegou a `trainer_running`, mas o jogo terminou poucos segundos depois do attach.
- `.31`: adicionou atraso de 30 s. O atraso estabilizou o PID, mas não resolveu o encerramento porque prontidão real e topologia continuavam confundidas.
- `.32`: lançou a rota privada `host_direct`, mas ainda exigiu/provou reentrada antes disso. O trainer ficou vivo por cerca de 3,6 s; a sessão do jogo terminou em seguida e o cleanup do trainer ocorreu depois.

### 4. Renderização e input foram problemas reais, porém separados

Em tentativas anteriores a janela apareceu preta, branca ou parcialmente desenhada. Em outras, a UI ficou visível, sliders responderam, mas toque/trackpad acertavam outra coordenada — às vezes a região `English` — em vez dos toggles. Issues do Gamescope sobre scaling são compatíveis com esse clique deslocado, mas isso ainda não foi fechado por uma reprodução controlada.

Esses sintomas não devem ser misturados com o encerramento atual. A ordem correta dos gates é:

1. jogo e trainer vivos;
2. janela selecionável;
3. coordenadas de clique corretas;
4. toggle ON/OFF;
5. efeito real no jogo;
6. regressão GOG.

## Estado atual do Steam Deck

- IP usado: `192.168.1.247`.
- Plugin instalado observado: `0.1.0-experimental.32`.
- Perfil Trainer Relay Epic: desativado na última verificação.
- Perfil GOG: preservado e habilitado na última verificação.
- Force Compatibility: não deve ser ativado.
- Launch options do Mortal Shell: restauradas e verificadas para o valor original do UniFiDeck.
- Runtime privado GE11/Mono10: presente e íntegro na última verificação.
- Último estado físico: jogo aberto e vivo; somente a janela do jogo estava presente, como esperado com Epic desativado.

## Estado atual do código local

Branch: `feat/trainer-relay`
HEAD: `10e3269` (`docs: consolidate FLiNG visibility handoff`)
Working tree: já estava sujo com várias mudanças e documentos anteriores; não usar `git restore`/`reset` amplo.

Uma correção TDD foi iniciada e interrompida a pedido do usuário:

- teste novo em `tests_backend/test_process.py` exige opt-out explícito da reentrada;
- teste refeito em `tests_backend/test_watcher.py` exige que o perfil exato host-direct não consulte o container e use ambiente host;
- RED confirmado: 2 testes executados, 0 passaram, 1 falhou e 1 terminou em erro por API ainda ausente;
- implementação parcial em `trainer_relay/process.py`: parâmetro `require_container_reentry` adicionado com default seguro `True`;
- implementação parcial em `trainer_relay/watcher.py`: constantes allowlisted, estado/predicado do perfil e ambiente host começaram a ser adicionados;
- a ligação do predicado à descoberta e a reorganização de `_spawn()` ainda não foram feitas;
- nenhum teste foi executado após essa implementação parcial;
- nada desse bloco foi empacotado, instalado ou ativado no Deck.

Portanto, o código atual não é candidato de release e não deve ser enviado ao Deck.

## Diagnóstico final deste relatório

### Demonstrado

- Existe um lançamento manual que entrega janela, alternância e cheats funcionais.
- O jogo funciona novamente após remover Force Compatibility quando ela havia sido ativada em uma tentativa anterior.
- O atalho persistente `UMU_CONTAINER_NSENTER=1 %command% ...` alterou o fluxo normal do UniFiDeck.
- A `.32` exige reentrada para descobrir o jogo, mas usa host-direct para o perfil comprovado.
- O cleanup do Relay ocorre depois do fim do processo do jogo, não antes.

### Provável, mas ainda não validado como correção final

- Remover a exigência de reentrada somente para a identidade/hash/arquitetura allowlisted e iniciar diretamente o perfil privado deve reproduzir o PASS manual sem contaminar o atalho.
- A janela ainda poderá precisar da associação Steam já implementada.
- O clique deslocado poderá exigir uma correção específica de escala/tamanho depois da estabilidade.

### Não demonstrado

- Que instalar .NET nativo/Winetricks resolveria o caso.
- Que Wine Mono sozinho causa o encerramento do jogo.
- Que um atraso fixo maior resolveria a integração.
- Que os toggles permanecem funcionais de forma reproduzível na versão automática `.32`.
- Que o GOG continua verde após todas as mudanças locais recentes; esse gate ainda precisa ser repetido.

## Retomada recomendada

1. Manter Epic desativado e o jogo no atalho original enquanto o código está incompleto.
2. Concluir a exceção somente para identidade `epic:0055...`, hash `872935...`, x64 e GE-Proton11-6.
3. Resolver o runtime privado antes de qualquer probe de container; se o runtime exato não resolver, falhar fechado sem fallback e sem editar atalho.
4. Usar `HOME/PATH/DBus/XDG` do host Decky e `DISPLAY/WINEPREFIX` da sessão observada, reproduzindo o lançamento manual mínimo.
5. Rodar os dois testes RED até GREEN, depois suítes backend, packaging, frontend, lint, TypeScript e build.
6. Só então empacotar uma nova versão, preservar rollback e instalar pelo fluxo oficial do Decky.
7. Validar fisicamente na ordem dos gates: estabilidade por 60 s, seletor Steam, clique, toggle ON/OFF, efeito de stamina e regressão GOG.

## Arquivos de evidência principais

- `docs/notes/2026-09-06-fling-native-toggle-correction-handoff.md`
- `docs/research/2026-09-06-fling-toggle-root-cause-ledger.md`
- `docs/research/2026-09-06-mortal-shell-fling-runtime-fingerprint.md`
- `docs/research/2026-09-07-upstream-fling-runtime-investigation.md`
- `docs/research/2026-09-07-upstream-sidecar-lifecycle-investigation.md`
- `tools/diagnostics/deck_live_probe.ps1`
- `.debug/restore-mortal-shell-launch-options.ps1`

## GitHub

Nenhum commit ou push foi feito neste bloco. O working tree contém alterações anteriores e a implementação parcial acima; staging deve ser explícito e só depois de concluir e validar a correção.

## Atualização de implementação local — 2026-09-07

Depois do relatório original, a correção foi concluída localmente sob TDD, sem instalação no Deck:

- o backend mede identidade, caminho, SHA-256 e arquitetura antes de escolher `host_direct_candidate`, `container_reentry` ou `blocked`;
- a UI consulta essa política e não adiciona `UMU_CONTAINER_NSENTER` para o candidato exato do Mortal Shell;
- o watcher resolve o runtime privado antes de qualquer probe e falha fechado se o runtime host-direct não estiver disponível;
- a rota de comandos do host-direct não simula barramento nem promete toggles; retorna `command_route_unsupported`;
- GOG e identidades não allowlisted permanecem no fluxo anterior de reentrada de contêiner.

Validação local: Vitest 225/225, backend completo 315/315, packaging 8/8, Biome sem erros, TypeScript de produção/testes, `compileall` e Rollup aprovados. O candidato `.33` foi gerado em `TrainerRelay.zip`, SHA-256 `030C7DA3D6EC62E7DE0BD8CECB1A70681492D5393847C438033A05957AA8E484`. A validação física — jogo + trainer estáveis por 60 s, janela no seletor Steam, clique/toggle real e regressão GOG — continua pendente porque o Deck `192.168.1.247` está inacessível (timeout na porta 22 e ping sem resposta). Nenhuma alteração remota foi feita.

## Atualização de execução `.34` (2026-09-07)

- A correção de descoberta do bus da sessão do usuário permitiu que o `.34` passasse da validação de ambiente e realmente criasse o trainer host-direct.
- O Decky instalou e carregou `0.1.0-experimental.34`; o ZIP usado foi conferido por SHA-256: `053fd786880f2dc89b78a63f7f3efc7a1deb401ccfcda32a1b9445b57879ea04`.
- Evidência remota: `trainer_spawned` → `trainer_running` → `session_ended`. O jogo encerrou primeiro, aproximadamente 1,8 s após `trainer_running`; a ausência de `trainer_exited` antes de `session_ended` descarta, nesta execução, o trainer como primeiro encerramento observado.
- Resultado: RED runtime. A instalação/ambiente host-direct foi corrigida, mas a topologia ainda não é estável o suficiente para declarar sucesso.
- Estado remoto: Epic desabilitado via RPC oficial para o próximo A/B no menu; GOG habilitado; plugin `.34` permanece instalado; não foi usado Force Compatibility nem alterada a configuração do UniFiDeck.
- Próximo passo obrigatório: confirmar que o jogo está no menu principal; reativar somente Epic; observar pelo menos 60 s antes de testar a janela Steam e os toggles físicos.

## A/B controlado pós-menu — `.34` continua RED (2026-09-07)

- O usuário confirmou o menu principal antes da reativação. O perfil Epic foi habilitado pelo RPC oficial e o jogo não recebeu Force Compatibility nem nova launch option.
- Linha temporal observada: `trainer_spawned` `13:52:54.008Z` → `trainer_running` `13:52:57.582Z` → `session_ended` `13:52:58.726Z`; sessão `PID 42140/start 2278662`, PGID do trainer `42762`.
- O encerramento em aproximadamente 4,7 s após o spawn reproduz o RED das execuções anteriores, agora sem a hipótese de “attach antes do menu”. A limpeza do Relay ocorreu depois do desaparecimento do jogo.
- O perfil Epic foi desabilitado novamente após a coleta; GOG permaneceu habilitado. Nenhum rollback de UniFiDeck, Force Compatibility, Proton global, prefixo real ou Mono global foi feito.
- Decisão: não promover `host_direct` e não aumentar delays. O próximo experimento autorizado pelo plano é o manual pós-menu usando o runtime privado GE11/Mono10, com o mesmo prefixo e o wineserver GE11; essa é a última referência histórica positiva antes de decidir a implementação.
- Foi criada a receita diagnóstica local `.debug/manual-mortal-shell-post-menu-trial.sh`; ela valida hash/runtime/prefixo, inicia somente o FLiNG via `systemd-run --user` e não altera launch options, UniFiDeck ou conteúdo do prefixo.

## Estado do próximo ensaio (2026-09-07)

- O Deck está acessível novamente e o probe observou Mortal Shell vivo com Epic desabilitado e sem trainer; a sessão atual tem `Dungeonhaven.exe`/`Dungeonhaven-Win64-Shipping.exe` ativos.
- O script manual foi copiado para `/home/deck/Downloads/manual-mortal-shell-post-menu-trial.sh`. Ainda não foi executado: a confirmação humana de que a tela chegou ao menu continua necessária para preservar o A/B pós-menu.

## Ensaio manual pós-menu executado — RED de estabilidade (2026-09-07)

- O menu foi confirmado e a receita manual iniciou o FLiNG fora do watcher, usando o runtime privado GE11/Mono10, o `WINESERVER` GE11 e o prefixo real; hash/runtime/prefixo passaram as pré-condições.
- A janela FLiNG apareceu com a geometria esperada `780x666`, demonstrando que a receita manual alcança a UI nativa.
- Na coleta seguinte, o jogo já não existia, enquanto o trainer permanecia vivo; o unit manual registrou `ActiveState=active`, e o log continha a asserção Mono `gpath.c:115: assertion 'filename != NULL' failed`.
- O unit diagnóstico foi encerrado/limpo; nenhuma configuração do UniFiDeck, launch option, Force Compatibility ou Mono global foi alterada.
- Interpretação: “host-direct privado após o menu” não é uma referência estável nesta sessão. O próximo ensaio deve ocorrer após o usuário carregar uma cena jogável (não somente o menu), para separar prontidão de engine de incompatibilidade da rota; depois disso, a implementação deve preferir a rota de sessão equivalente ao jogo ou um gate explícito, sem novo atraso cego.

## Reprodução automática `.34` — janela abriu e sessão morreu (2026-09-07)

- O usuário confirmou que o trainer abriu e que tudo fechou em seguida.
- Evidência: `trainer_spawned` `14:12:31.295Z` → `trainer_running` `14:12:35.506Z` → `window_association` `14:12:36.885Z` → `session_ended` `14:12:37.994Z`.
- A janela chegou a ser associada, mas a sessão durou apenas cerca de 6,7 s desde o spawn. Não houve `trainer_exited` antes de `session_ended`, então não há evidência de que o FLiNG tenha sido o primeiro processo a cair; o fechamento conjunto foi observado pelo usuário.
- Classificação: `RED_RUNTIME_PROFILE`/instabilidade de sessão. A rota host-direct alcança a UI, mas não mantém o jogo vivo. O perfil Epic foi desabilitado novamente pelo RPC oficial; GOG continuou habilitado.
- Próxima investigação: não repetir a mesma rota nem usar atraso cego. É necessário comparar uma rota oficial de sessão (`runinprefix`/mesmo ambiente do jogo) em contexto controlado ou capturar o erro do processo do jogo antes de qualquer promoção.

## `.35` preparada localmente — rota oficial de sessão (2026-09-07)

- Depois do RED automático, a política exacta foi corrigida de `host_direct_candidate` para `container_reentry`; o runtime privado não é mais lançado como um segundo Wine host-direct.
- O watcher voltou a exigir a marca de reentrada para todas as identidades, valida o bus/launch-client e usa o perfil privado em modo `container_reentry`. A UI/migração prepara `UMU_CONTAINER_NSENTER=1` para o atalho, sem Force Compatibility.
- Validação local: Vitest `225/225`; backend completo sem falhas; packaging `8/8`; lint/Biome `75 arquivos`; TypeScript; `compileall`; build e ZIP aprovados.
- Artefato: `TrainerRelay.zip`, versão `0.1.0-experimental.35`, SHA-256 contínuo `227A1257AF320CB62EBAE71718598A17F8048C6EE62EB2491B2CD66145E60A57`.
- Estado remoto ainda seguro: `.34` antigo instalado, Epic desabilitado após a reprodução, GOG habilitado. Próximo passo: instalar `.35` via fluxo oficial Decky após backup e então validar reentrada, estabilidade, seletor Steam, clique/toggle e GOG.

## `.35` instalado no Deck (2026-09-07)

- O ZIP foi transferido e validado remotamente pelo SHA-256 `227a1257af320cb62ebae71718598a17f8048c6ee62eb2491b2cd66145e60a57`.
- Rollback criado em `/home/deck/Downloads/TrainerRelay-rollback-20260907-1125/`; instalação oficial Decky confirmou versão `.35` e hash.
- A launch option original foi preservada como referência e preparada/verificada para `UMU_CONTAINER_NSENTER=1 %command% epic:0055e45ce7654c55aade646467349e83`; Force Compatibility não foi usado.
- Probe pós-instalação: `.35` carregado, runtime/Mono10 presentes, nenhum jogo/trainer ativo. Epic foi habilitado para o próximo lançamento normal; GOG segue habilitado.
- Gate pendente: iniciar Mortal Shell pelo UniFiDeck, observar `container_reentry` e estabilidade por pelo menos 60 s; só depois testar seletor Steam, clique/toggle e efeito real.

## Ensaio oficial `.35` — reentrada confirmada, jogo ainda encerra (2026-09-07)

### O que foi testado

- Plugin `.35` instalado pelo fluxo oficial do Decky, com hash conferido e rollback preservado.
- Mortal Shell iniciado pelo UniFiDeck com Force Compatibility desligado.
- Launch option temporariamente preparada pela API oficial da Steam para `UMU_CONTAINER_NSENTER=1 %command% epic:0055e45ce7654c55aade646467349e83`.
- Perfil Epic habilitado apenas durante o ensaio; GOG permaneceu habilitado.

### Resultado observado

- A rota passou pela verificação de reentrada: `container_reentry_verified` → `trainer_spawned` → `container_reentry_confirmed` → `trainer_running`.
- A sessão não permaneceu estável: `session_ended` ocorreu cerca de 1,9 s depois de `trainer_running`. O usuário observou que tudo fechou.
- Não houve `trainer_exited` antes de `session_ended`; a evidência disponível aponta primeiro para o término da sessão do jogo, seguido pela limpeza do trainer, mas não prova a causa inicial.
- O `CrashReportClient.log` encontrado no prefixo termina com uma saída normal do próprio CrashReportClient e não contém, no trecho coletado, a falha de `Dungeonhaven.exe`.
- O `gameprocess_log.txt` confirma o encerramento dos processos de lançamento UniFiDeck/Steam no mesmo período, porém sem uma exceção útil do jogo.

### Estado após o teste

- Epic desabilitado via RPC oficial.
- Launch option restaurada e verificada como `epic:0055e45ce7654c55aade646467349e83`.
- GOG habilitado; nenhum processo do jogo, trainer ou UMU ativo.
- Nenhuma mudança em Force Compatibility, Proton global, prefixo real ou Mono global.

### Conclusão

O `.35` demonstrou que a reentrada oficial do contêiner está funcionando, mas não entregou estabilidade. O caso deixou de ser somente uma falha de descoberta/bus ou de janela: agora é necessário localizar a causa do encerramento do jogo antes de qualquer nova alteração de código. A janela, seleção Steam, cliques e efeito ON/OFF continuam sem validação nesta rota.

### Próximos passos

1. Extrair os logs específicos de `Dungeonhaven`/Unreal e possíveis dumps no intervalo exato do RED.
2. Comparar, em ensaios controlados, a reentrada com o ambiente nativo do jogo contra a mesma rota com o runtime privado GE11/Mono10.
3. Manter o atalho original e Epic desabilitado entre ensaios; só retomar os gates físicos após 60 s de estabilidade.

## Encerramento da investigação atual (2026-09-07)

- A consulta ao `journalctl` não encontrou falha fatal do jogo: o UniFiDeck selecionou GE-Proton11-6 sem Force Compatibility, iniciou o comando Epic normal e o UMU terminou com código `0` após aproximadamente 50,3 s.
- Não foram encontrados dump ou log próprio de `Dungeonhaven`; o `CrashReportClient` apenas recebeu solicitação normal de saída. Os avisos do overlay Steam e do sync de saves ficaram sem relação causal demonstrada.
- O usuário decidiu não prosseguir. Não houve nova alteração remota após a restauração.
- Estado final: Epic desabilitado, launch option original restaurada, GOG habilitado, nenhum processo ativo, Force Compatibility não usado e rollback preservado.
- Status honesto: a correção permanece inconclusiva; não declarar o trainer Epic funcional. A estabilidade, alternância Steam, cliques/toggles e efeito ON/OFF continuam pendentes.

## Relatório final — encerramento por desistência do usuário (2026-09-07)

### Objetivo

Usar o FLiNG de Mortal Shell pela cópia Epic iniciada pelo UniFiDeck, mantendo o jogo aberto, exibindo o trainer como segunda janela selecionável pelo Steam, permitindo clique/toggle físico e comprovando um cheat ON/OFF. A cópia GOG deveria continuar preservada.

Restrições mantidas durante a investigação: não usar Force Compatibility, não trocar Proton global, não substituir o UniFiDeck, não trocar Mono global e não reconstruir o prefixo real por tentativa.

### O que funcionou

- O SSH ao Deck foi estabelecido e o fingerprint foi conferido diretamente no Deck.
- O UniFiDeck continuou iniciando o Mortal Shell quando a opção de forçar compatibilidade foi removida; essa opção nunca foi usada como correção.
- O diagnóstico identificou e separou processos do jogo, overlay, launcher e trainer, em vez de tratar qualquer `steam_app_0` como o jogo.
- O GOG funcionou historicamente com o fluxo existente; o perfil GOG permaneceu habilitado em todos os ensaios finais.
- A receita manual com runtime privado GE-Proton11/Mono10 conseguiu abrir uma janela FLiNG visível (`780x666`), embora o jogo tenha desaparecido depois.
- A rota `.34` host-direct conseguiu abrir a UI do trainer e chegar à associação de janela, mas matou a estabilidade do jogo.
- A rota `.35`/`.36` conseguiu executar a reentrada pelo `steam-runtime-launch-client`.
- A `.36` corrigiu um defeito real de telemetria: o runner deixou de declarar confirmação antes de iniciar o filho e passou a exigir ACK emitido dentro do launch-client, vinculado à sessão e ao bus.
- As validações locais da `.36` passaram: runner `22/22`, módulos afetados `134/134`, Vitest `225/225`, backend, packaging, Biome/lint, TypeScript, `compileall` e build.

### O que não funcionou

- O trainer inicialmente apareceu preto/branco ou como quadrado sem controles.
- Em execuções posteriores, os sliders respondiam, mas os cliques nos toggles eram deslocados para outra região, inclusive para “English”; touch e trackpad apresentaram o mesmo problema.
- Houve uma confirmação histórica do usuário de que a alternância Steam e Infinite Stamina funcionaram em uma execução anterior, mas essa receita não foi preservada de modo reproduzível e o teste posterior de clique/toggle não pôde ser concluído.
- O caminho host-direct `.34` abriu o trainer, porém o jogo encerrou poucos segundos depois; aumentar atraso não foi uma solução.
- A receita manual pós-menu abriu o FLiNG, mas deixou o jogo fechado e o trainer vivo; o log do unit registrou `gpath.c:115` no Mono.
- O caminho oficial de reentrada `.35` confirmou a infraestrutura, mas o jogo e o trainer fecharam juntos em poucos segundos.
- O `.36` confirmou o ACK real de reentrada, mas o resultado físico permaneceu RED: o jogo terminou logo após o trainer atingir `running`.
- Não foi possível comprovar a causa inicial do encerramento. Não apareceu dump, exceção fatal de `Dungeonhaven.exe` ou sinal externo explícito. Os cancelamentos do Xalia aparecem no fechamento, mas não foram demonstrados como causa.

### Último ensaio `.36`

O ensaio usou temporariamente `UMU_CONTAINER_NSENTER=1 %command%`, com Epic habilitado somente durante o teste e Force Compatibility desligado. A linha de eventos foi:

| Evento | UTC |
|---|---|
| Reentrada verificada | `15:04:00.920Z` |
| Trainer criado | `15:04:00.929Z` |
| ACK real recebido | `15:04:02.966Z` (`27 ms`) |
| Trainer marcado como running | `15:04:05.016Z` |
| Sessão do jogo terminou | `15:04:06.755Z` |
| Limpeza do grupo do trainer | `15:04:06.811Z`, `SIGTERM`, PGID `50728` |

Não houve `trainer_exited` antes de `session_ended`. Isso indica que o Relay só limpou o trainer depois que a sessão do jogo já havia desaparecido; não prova qual componente provocou o primeiro encerramento.

### Estado final seguro

- Plugin `.36` permanece instalado no Deck.
- Rollback preservado em `/home/deck/Downloads/TrainerRelay-rollback-20260907-1205/`.
- Launch option restaurada e verificada como `epic:0055e45ce7654c55aade646467349e83`.
- Perfil Epic desabilitado novamente; GOG habilitado.
- Jogo, trainer e UMU fechados; probe final retornou `WAITING_FOR_GAME`.
- Force Compatibility não foi usado nem alterado.
- Nenhuma alteração global de Proton, Mono, prefixo ou UniFiDeck foi feita.

### Conclusão honesta

O problema não foi resolvido. A investigação corrigiu a telemetria e documentou que a reentrada oficial chega a executar o trainer, mas ainda não há estabilidade física. Portanto, não declarar o trainer Epic funcional, nem declarar clique/toggle ou cheats comprovados na rota final.

### Se outra investigação for retomada

Começar por uma A/B somente leitura: jogo sem sidecar; processo Wine inofensivo no mesmo launch-client/bus; FLiNG. Coletar PID, PPID, PGID, cgroup e sinal de cada processo. Só depois de 60 s de estabilidade repetir seletor Steam, clique, toggle, efeito ON/OFF e GOG. Não repetir delay, host-direct, troca de Proton ou instalação de Mono sem uma causa evidenciada.
