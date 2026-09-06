# TrainerRelay — handoff completo do FLiNG na Epic/Mortal Shell

**Data:** 2026-09-06  
**Branch:** `feat/trainer-relay`  
**Estado:** objetivo ainda não concluído; este documento consolida as tentativas, os resultados comprovados e a retomada segura.

## Objetivo do usuário

No Steam Deck, ao iniciar Mortal Shell pela loja Epic através do UniFiDeck:

- abrir a janela real do FLiNG Trainer com texto, botões e lista de cheats;
- alternar entre jogo e trainer pelo seletor/tela da Steam, como já ocorre no baseline GOG;
- ativar e desativar os cheats pela própria tela do trainer;
- deixar a implementação da sidebar para depois.

Restrições explícitas:

- não ativar **Force the use of a specific Steam Play compatibility tool** no shortcut do UniFiDeck; isso fez o jogo deixar de iniciar;
- não substituir o fluxo normal do UniFiDeck nem migrar o prefixo real;
- preservar o jogo, o prefixo e os settings existentes;
- testar com backup/hash/rollback e distinguir processo vivo de janela visível e funcional.

## Resultado resumido

A cadeia Epic/UniFiDeck consegue iniciar o jogo e também consegue criar um processo/janela X11 do FLiNG. O problema restante é a apresentação dessa janela no gamescope/seletor da Steam e a confirmação de interação real.

O estado mais recente observado pelo agente foi:

- jogo Mortal Shell vivo no `DISPLAY=:1`, usando GE-Proton11-6 pelo fluxo do UniFiDeck;
- processo de teste do FLiNG vivo como serviço de usuário;
- janela X11 do FLiNG mapeada em `780x666`, com o título completo;
- usuário ainda relata: **a tela do Steam Deck mostra somente o jogo**;
- portanto `xwininfo`/`WM_STATE=Normal` não é tratado como PASS de visibilidade;
- cheats e efeito no jogo ainda não foram validados.

Não existe, até este ponto, um conserto permanente comprovado para o objetivo.

## Baselines que funcionaram

### GOG

O usuário confirmou que o FLiNG funciona para um jogo GOG e que consegue alternar entre o jogo e o trainer pelo botão da Steam. Esse é o baseline físico de comparação. O BioShock 2 GOG também foi observado como funcional sob GE-Proton11-6.

### Epic/Mortal Shell — partes que funcionam

- O shortcut Epic do Mortal Shell inicia normalmente quando o Force Compat fica desmarcado e o UniFiDeck continua controlando o ambiente.
- O jogo normal aparece no gamescope em `DISPLAY=:1`.
- A preparação de reentrada com `UMU_CONTAINER_NSENTER=1 %command%` permitiu sessões em que o jogo e o trainer foram lançados; isso é evidência de uma sessão funcional, não de persistência após reboot.
- O executável exato do trainer foi identificado e seu SHA-256 foi usado para o adapter/catalogo.
- Um lançamento direto com os binários Wine do GE11-6, prefixo real e `DISPLAY=:1` criou uma janela do FLiNG.
- Um A/B isolado com GE-Proton10-34 renderizou a interface completa do FLiNG e os 16 controles de Mortal Shell.
- O plugin foi empacotado, instalado pelo caminho autenticado do Decky e respondeu a RPC de diagnóstico.

## Linha do tempo e tentativas

### 1. Diagnóstico inicial e acesso ao Deck

Foi lido o handoff de 2026-09-05, o baseline GOG e os diagnósticos exportados. O Deck foi acessado por SSH temporário, com host fingerprint confirmado pelo usuário (`SHA256:YkrB6o3zby/e8NdZ/Kzx3yBDH01ZFQEg9XBTl/0/8mI`). O acesso usou chave dedicada, `BatchMode`, `StrictHostKeyChecking` e sem reutilizar a senha das fotografias.

A evidência inicial mostrou que:

- o jogo Epic podia estar rodando enquanto o Steam reconhecia apenas a janela do jogo;
- `trainer_running` do plugin antigo descrevia o processo externo `umu-run`, não necessariamente o executável Windows real;
- snapshots de X11 truncados não bastavam para provar visibilidade na Steam;
- a janela sem nome inicialmente encontrada era `EOSOverlayRenderer`, não o trainer.

### 2. Preparação da reentrada UMU

Foi usada a rota CEF/Steam suportada para ler os detalhes do shortcut e, em uma sessão controlada, alterar apenas as opções de lançamento para incluir `UMU_CONTAINER_NSENTER=1 %command%` antes do identity Epic. O valor foi lido de volta por callback e a assinatura foi removida ao terminar.

Resultado:

- funcionou em uma sessão fresca: `trainer_spawned`, `reentry_confirmed` e `trainer_running` foram registrados;
- não provou persistência através de reboot;
- não resolveu a associação da janela no seletor Steam;
- não foi usado para justificar alteração direta de `shortcuts.vdf`.

### 3. Associação manual da janela à Steam

Foram comparados `m_mapAppWindows`, `_NET_WM_PID`, `WM_NAME`, `WM_CLASS`, `WM_STATE`, `STEAM_GAME`, tipo da janela e geometria.

Tentativas:

- definir `STEAM_GAME=2476768691` na janela do trainer;
- confirmar a propriedade por `xprop`;
- verificar novamente o mapa CEF;
- tentar trazer a janela para o seletor.

Resultado:

- a propriedade podia ser escrita, mas o mapa CEF continuou contendo apenas a janela do jogo;
- uma tentativa posterior criou uma segunda janela Steam, porém o usuário viu uma superfície preta;
- a associação manual isolada não foi considerada correção e foi revertida;
- a implementação baseada na premissa de mesmo process group foi marcada como não validada, porque o `steam-runtime-launcher-service` cria uma sessão/grupo separado na reentrada.

As builds experimentais .23/.24 não são uma solução física validada.

### 4. Teste de compatibilidade Proton

Foi feita uma troca A/B temporária para GE-Proton11-1, sem aceitar essa troca como solução. O usuário alertou que o UniFiDeck deixa de iniciar o jogo quando a compatibilidade é forçada.

Resultado:

- o setting foi restaurado para o estado normal do UniFiDeck;
- a tentativa deixou claro que nomear GE-Proton no shortcut não é equivalente ao fluxo UniFiDeck/UMU;
- uma execução programática `RunGame` também usou contexto errado e lançou processos em `DISPLAY=:0`; esses PIDs exatos foram encerrados;
- não repetir `RunGame` nem ativar Force Compat neste shortcut.

### 5. Experimental.25 — desktop Wine para Epic

Foi criado primeiro um teste em prefixo descartável. O comando com Wine desktop gerou um parent `TrainerRelay - Wine Desktop` e um child `FLiNG Trainer`, aparentemente oferecendo uma segunda janela ao gamescope.

Implementação:

- `OwnedTrainerRunner.spawn` passou a aceitar `virtual_desktop`;
- o watcher usou o desktop apenas para identities `epic:`;
- GOG manteve o argv direto existente;
- versão `0.1.0-experimental.25`.

Gates automatizados antes da instalação:

- 69 testes focados runner/watcher passaram;
- 291 testes backend passaram;
- 217 testes frontend em 30 arquivos passaram;
- lint, TypeScript, Rollup e 7 testes de packaging passaram;
- ZIP com 34 entradas e hash `94D8521318987F9C2546F3A1DD1DF7761F76DB6DFC5B80AE8BA7B95D92463BA5`;
- backup .22 e settings preservados no Deck.

Resultado físico:

- o gamescope registrou o parent, mas o usuário viu somente um desktop branco/azul;
- o child FLiNG publicou `WS_EX_LAYERED` e `_NET_WM_WINDOW_OPACITY=0`;
- escrever opacidade máxima produziu uma superfície preta;
- a opacidade original foi restaurada;
- .25 não resolveu o objetivo e foi mantido somente como rollback.

### 6. A/B isolado com GE-Proton10-34

O mesmo executável e hash foram usados em um prefixo descartável com GE10-34.

Resultado comprovado:

- todos os controles da interface FLiNG foram renderizados;
- os 16 cheats de Mortal Shell ficaram visíveis;
- a janela não publicou a opacidade zero observada no caminho GE11;
- o teste não provou que esse trainer poderia escrever no processo do jogo real, porque o prefixo era isolado;
- o prefixo descartável e o serviço transitório foram removidos;
- o runtime compartilhado `steamrt3` foi atualizado automaticamente pelo UMU durante o teste; nenhum novo teste de download/runtime deve ser iniciado sem autorização.

Essa foi a evidência mais forte de uma diferença de renderização Wine 11/GE11 para este executável, mas ainda não é uma correção de produto.

### 7. Experimental.26 — catálogo/InputHelper

Como a superfície FLiNG estava quebrada, foi preparada uma alternativa que expõe no Trainer Relay os 16 hotkeys observados no render GE10 e usa o caminho InputHelper, sem desktop Wine.

Implementação:

- catálogo vinculado por SHA-256 ao identity Epic exato;
- x64, 16 controles de Mortal Shell;
- Epic voltou ao lançamento direto, sem o desktop branco;
- GOG permaneceu no caminho direto;
- versão `0.1.0-experimental.26`.

Gates:

- 107 testes focados passaram;
- 292/292 backend passaram;
- 217/217 frontend passaram;
- 7/7 packaging passaram;
- Biome, TypeScript e Rollup passaram;
- ZIP com 34 entradas e hash `FEEEFC686ED96502E9C8789A4ADB50BE86D7D970E668A14FDA5AC1A1401552BF`.

A instalação foi feita pelo caminho autenticado do Decky a partir do target CEF correto, com rollback .25 preservado. O RPC pós-instalação confirmou `waiting_for_game`/`relay_not_running` sem jogo aberto.

Limite:

- .26 não cumpre o pedido de ver a janela real do FLiNG;
- nenhum cheat foi comprovado fisicamente por efeito no jogo;
- não declarar .26 como solução final do objetivo atual.

### 8. Lançamento direto, Mono e sobrevivência do processo

Para separar o problema de renderização do problema de sessão SSH, o trainer foi executado diretamente com os binários Wine do GE11-6, prefixo real e `DISPLAY=:1`.

Foi descoberto que `/etc/systemd/logind.conf.d/killuserprocesses.conf` contém `KillUserProcesses=True`. Isso matava testes destacados quando a sessão SSH caía e invalidou conclusões anteriores de que o trainer necessariamente morria durante a inicialização do Mono.

Mitigação de teste:

- `systemd-run --user --unit=trainerrelay-test` manteve o processo vivo após a queda da sessão SSH;
- não é ainda uma integração permanente do plugin.

Também foi descoberto que uma tentativa de trocar o Mono havia deixado um symlink quebrado `wine-mono -> wine-mono-10.4.1`. O diretório foi então copiado do GE10-34 para o GE11-6; o backup do Mono GE11 original ficou como `wine-mono.ge11-6.bak -> wine-mono-11.2.0`.

Com o diretório corrigido:

- CLR inicializou;
- o trainer ficou vivo por mais de 30 minutos como serviço;
- a janela `Mortal Shell v1.0-Build.08.25.21 Plus 16 Trainer` apareceu em `780x666`;
- `_NET_WM_WINDOW_OPACITY` deixou de aparecer;
- o usuário, porém, continuou vendo somente o jogo no seletor/tela;
- ativação via `xdotool windowactivate` não funcionou porque o steamcompmgr não expõe `_NET_ACTIVE_WINDOW`;
- unmap/map foi tentado para forçar remapeamento, sem confirmação de visibilidade para o usuário.

O Mono trocado e o serviço são estado de diagnóstico, não um fix permanente.

## Tentativas que não devem ser repetidas como solução

- Forçar compatibilidade no shortcut UniFiDeck.
- Usar Steam `RunGame` para este shortcut.
- Escrever diretamente `shortcuts.vdf` enquanto a Steam está rodando.
- Considerar `WM_STATE=Normal`, `MapState=IsViewable` ou processo vivo como prova de que o usuário consegue selecionar a janela.
- Alterar opacidade/remap de qualquer janela sem identificar PID, owner e rollback.
- Instalar .23/.24 como se já fossem correções físicas.
- Tratar o caminho InputHelper de .26 como cumprimento do pedido da janela FLiNG.
- Fazer novos downloads/updates do runtime compartilhado sem autorização.

## Estado atual conhecido

Última leitura somente leitura do Deck em 2026-09-06 13:01 (-03):

- jogo Mortal Shell/`Dungeonhaven.exe` vivo em GE-Proton11-6;
- processo `Mortal Shell ... Trainer.exe` vivo;
- `trainerrelay-test.service` ativo;
- janela do jogo `0x2600003`, `1280x800`;
- janela do trainer `0x3600001`, `780x666`, título completo;
- `wine-mono` do GE11-6 resolve para `wine-mono-10.4.1`;
- `sshd` ainda está ativo para o diagnóstico;
- a última observação humana é que apenas o jogo aparece para seleção.

A leitura foi sanitizada neste documento: não registrar argumentos de autenticação ou tokens encontrados em linhas de comando. Futuras sondagens devem usar apenas `pid`, `comm`, janela e propriedades necessárias.

## Alterações no repositório

Commits relevantes já presentes na branch:

- `8202f34` — handoff da tentativa de associação;
- `e5464f5` — verificação de lançamento após preparação;
- `53dbf34` — registro da falha preta e restauração do UniFiDeck;
- `5ac0c53` — desktop Wine para Epic (.25);
- `1b83153` — controles de Mortal Shell (.26);
- `1e0e598` — registro da instalação de .26.

Notas existentes importantes:

- `2026-09-05-live-cef-gog-baseline-handoff.md`;
- `2026-09-05-live-cef-steam-umu-research.md`;
- `2026-09-05-steam-window-association-fix-v24-handoff.md`;
- `2026-09-06-running-lifecycle-research.md`;
- `2026-09-06-export-current-session-evidence.md`;
- `2026-09-06-current-reentry-missing-handoff.md`.

Ao criar este arquivo, não incluir `.codex-remote-attachments/`, `.debug/` ou `.steam-cdp-eval.ps1` no commit; são artefatos locais existentes.

## Pendências e limpeza

Antes de considerar o trabalho encerrado:

1. Confirmar visualmente uma janela FLiNG real no seletor Steam e alternar jogo/trainer pelo botão Steam.
2. Clicar ou alternar um cheat seguro pela tela e confirmar efeito no jogo; depois desativá-lo e confirmar reversão.
3. Implementar uma correção permanente somente após um RED reproduzível e um teste de regressão adequado; a solução deve preservar GOG e UniFiDeck.
4. Decidir, com evidência, se o Mono GE10 é compatível com o GE11; se não for parte do fix, restaurar o symlink original a partir do backup.
5. Parar o `trainerrelay-test` e remover os scripts/logs temporários do Deck quando não forem mais necessários.
6. Remover apenas a chave pública temporária adicionada ao `authorized_keys` e desabilitar/parar o `sshd` habilitado para o diagnóstico, preservando outras chaves/configurações.
7. Revalidar que o shortcut UniFiDeck inicia Mortal Shell com Force Compat desmarcado.
8. Fazer commit/push desta documentação sem incluir artefatos ou segredos.

## Procedimento de retomada

1. Ler este handoff e o `2026-09-06-current-reentry-missing-handoff.md`.
2. Não alterar o UniFiDeck, o shortcut, o Proton forçado ou o prefixo real.
3. Se o teste atual ainda estiver vivo, primeiro capturar estado somente leitura usando `pid/comm`, `xwininfo` e propriedades da janela, sem comandos que revelem a linha completa do processo.
4. Priorizar a reprodução do caminho Steam selector: a condição RED é o usuário ver somente o jogo; a condição GREEN exige trainer selecionável, conteúdo visível e alternância jogo/trainer.
5. Só depois testar ativação/desativação de um cheat e confirmar efeito físico.
6. Se uma nova mudança for necessária, criar RED automatizado antes, alterar uma variável por vez, preservar rollback e validar GOG + Epic.
7. Atualizar este handoff após cada marco e antes de encerrar.

## Critério de conclusão

O objetivo só pode ser marcado como concluído quando houver evidência física contemporânea de todos os itens: jogo Epic inicia normalmente pelo UniFiDeck sem Force Compat; FLiNG aparece com conteúdo; botão Steam alterna entre as duas janelas; um cheat é ativado pela tela, produz efeito observável, é desativado e o efeito reverte; GOG continua funcionando; testes e artefato final estão registrados; e o estado temporário de diagnóstico foi limpo.

