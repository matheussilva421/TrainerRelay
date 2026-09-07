# Mortal Shell / FLiNG — pesquisa upstream e resolução após .36

Data: 2026-09-07. **Pesquisa concluída; causa física do encerramento ainda não identificada.** Foram encontrados defeitos locais reproduzíveis, diferenças de contrato e um patch Gamescope relevante para investigar o clique deslocado. Nenhuma alteração de produto ou execução no Deck foi feita.

## Conclusão

A rota privada .36 usa o transporte oficial de reentrada, mas executa uma receita Wine própria. O ACK comprova execução da shell; não comprova ambiente equivalente, inicialização CLR, mesmo wineserver ou estabilidade. O próximo trabalho deve corrigir o instrumento de diagnóstico, separar ambiente UMU de ambiente Wine e localizar a primeira diferença entre um processo Wine simples e o FLiNG.

Há também uma pista específica para o input: o commit Gamescope `33b4eff0fb577608b6f71c6adc0f615782aa48ef`, de 2026-09-02, corrige escala de ponteiro absoluto. Sua aplicação depende da versão e do caminho de upscale efetivos no Deck. Ele não explica por si o jogo fechando.

[Plano executável após .36](../superpowers/plans/2026-09-07-mortal-shell-post36-resolution-plan.md) · [Handoff](../notes/2026-09-07-mortal-shell-upstream-research-handoff.md)

## Baseline reconciliado

Os relatórios fornecidos, CONTEXT, ADR 0001 e pesquisas locais anteriores foram lidos cronologicamente. Recomendações internas foram tratadas como histórico, sem executar instruções de instalação/retomada.

| Evidência registrada | Resultado | Consequência |
|---|---|---|
| .34 host-direct após menu | Jogo saiu cerca de 4,7 s após spawn | Menu/delay não resolveram |
| Manual posterior fora do watcher | UI 780×666; jogo ausente; trainer vivo; mensagem Mono | PASS manual antigo não é receita estável preservada |
| .35 | Sessão caiu; confirmação antiga tinha defeito | Telemetria antiga não prova execução real |
| .36 | ACK real; jogo saiu; cleanup veio depois | ACK já corrigido; estabilidade continua RED |

Última sequência documentada: spawn `15:04:00.929Z`, ACK `15:04:02.966Z`, running `15:04:05.016Z`, fim da sessão `15:04:06.755Z`, SIGTERM do Relay ao trainer `15:04:06.811Z`. Polling não identifica instante exato ou autor da saída; a ordem não sustenta atribuir o início ao cleanup do Relay.

Último estado remoto **documentado, não reconsultado**: .36 instalada, Epic desabilitado, atalho original restaurado, GOG habilitado, jogo/trainer/UMU fechados. Rollback `/home/deck/Downloads/TrainerRelay-rollback-20260907-1205/`. Fonte: [relatório consolidado, seção final](../notes/2026-09-07-mortal-shell-fling-outcomes-report.md).

Git inicial: `feat/trainer-relay`, HEAD `3eec791`; pacote local declara `.36`. Muitas alterações preexistentes foram preservadas. Código inspecionado inclui arquivos ainda não publicados.

## Método e versões

Pesquisa paralela de runtime/UMU, Mono/input e integração Steam/Decky/CheatDeck; revisão principal cruzou resultados com código local e GE/Wine. Buscas dirigidas por Mortal Shell, Dungeonhaven, ID Epic, AppID Steam 1110910, runinprefix, launch-client, wineserver, gpath.c, input scaling e lifecycle. Issues de usuários são precedentes, não reprodução desta build. A triagem não é auditoria exaustiva dos 21 projetos.

| Componente | Referência inspecionada |
|---|---|
| GE-Proton11-6 | [7e88cefffc122ea1584c2156b8d7bae6cf69b2a7](https://github.com/GloriousEggroll/proton-ge-custom/tree/7e88cefffc122ea1584c2156b8d7bae6cf69b2a7) |
| Wine vinculado ao GE | [9358696fe9a2261329f4a83aa6a65fd436106154](https://github.com/ValveSoftware/wine/tree/9358696fe9a2261329f4a83aa6a65fd436106154) |
| UMU 1.4.4 | [cf3d1b107147480c447ffbfb3f789dc74335074c](https://github.com/Open-Wine-Components/umu-launcher/blob/cf3d1b107147480c447ffbfb3f789dc74335074c/umu/umu_run.py) |
| steam-runtime-tools v0.20260903.0 | [06a2477429fe271c5b254399caffdab8b7737e99](https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/tree/06a2477429fe271c5b254399caffdab8b7737e99) |
| Steam Runtime | [8ac0d033e3e14150188ac676d7ac1a60cf8dbb74](https://github.com/ValveSoftware/steam-runtime/tree/8ac0d033e3e14150188ac676d7ac1a60cf8dbb74) |
| umu-runtime v0.1.0 | [5d61edd7221cb41e9076b3fe4cb741ddfc663144](https://github.com/Open-Wine-Components/umu-runtime/tree/5d61edd7221cb41e9076b3fe4cb741ddfc663144) |

Esses pins identificam fontes, não o build instalado no Deck. GitLab apresentou proteção de acesso em algumas rotas; páginas específicas acessíveis e fontes oficiais GitHub/API foram usadas. O portal bloqueado não foi classificado como ausência de projeto. Downloads de texto ficaram em `.debug/`; nenhum código upstream foi executado.

## 1. Raiz UMU entregue ao Wine direto — RED local

[`environment.py`](../../trainer_relay/environment.py) prepara `WINEPREFIX` e `STEAM_COMPAT_DATA_PATH` com a raiz compatdata, adequada para uma nova chamada UMU. Porém [`runner.py`](../../trainer_relay/runner.py), ramo privado, monta `launch-client → sh → env → wine privado → trainer`. Não chama Proton para transformar raiz em prefixo filho.

O harness chamou sanitizer e runner reais com Popen falso:

```text
actual direct-Wine WINEPREFIX: /fixture/compatdata
observed game WINEPREFIX: /fixture/compatdata/pfx
PROTON_VERB assignment: True
executable after env assignments: /private/files/bin/wine
RED contract: direct Wine receives UMU root instead of observed Wine prefix
```

Isso demonstra contrato incorreto quando as localizações diferem. **Não demonstra que diferem fisicamente neste Deck:** symlinks podem torná-las o mesmo objeto. Comparar realpath, device/inode, namespace e socket. Alterar só a string pode não mudar o caso real.

O Wine exato usa device/inode do diretório de configuração e UID para descobrir servidor; no Linux desta revisão, `/tmp/.wine-<uid>/server-<dev>-<ino>`. Mesmo texto em namespaces diferentes não garante o mesmo socket. Fonte: [Wine server.c](https://github.com/ValveSoftware/wine/blob/9358696fe9a2261329f4a83aa6a65fd436106154/dlls/ntdll/unix/server.c#L1315-L1479).

**Correção planejada:** separar raiz para UMU de prefixo efetivo para Wine direto, validado contra a sessão, conservando GOG/UMU. Não criar pfx nem mudar symlinks por tentativa.

## 2. Bibliotecas e ambiente divergem do GE exato

GE configura prefixo filho, bibliotecas ELF multiarch, WINEDLLPATH e sincronização antes de executar `runinprefix`. A lista inclui `lib/x86_64-linux-gnu` e `lib/i386-linux-gnu`. O Relay substitui LD_LIBRARY_PATH por `lib:lib/wine[:lib64]`. Definir `PROTON_VERB=runinprefix` junto de Wine direto não executa o verbo. Fonte: [GE proton](https://github.com/GloriousEggroll/proton-ge-custom/blob/7e88cefffc122ea1584c2156b8d7bae6cf69b2a7/proton#L2023-L2044).

A [FAQ UMU](https://github.com/Open-Wine-Components/umu-launcher/wiki/Frequently-asked-questions-%28FAQ%29#how-do-i-run-more-than-one-game-in-the-same-wine-prefix) exige configurações equivalentes entre clientes no mesmo prefixo e explica a espera pelo wineserver no verbo padrão. Isso sustenta comparação do ambiente; não recomenda desligar sincronização ao acaso.

[`runtime_profile.py`](../../trainer_relay/runtime_profile.py) compara cinco arquivos críticos e valida symlink Mono. Isso não verifica todas as bibliotecas ou módulos carregados. Diretórios ausentes da variável podem ser resolvidos por RPATH/defaults; portanto, não há prova de carregamento errado apenas pela lista.

**Próxima medição:** mapas do processo, origem dos módulos, ambiente permitido dentro do serviço e sincronização efetiva. GE11-6 inclui WINENTSYNC; não aplicar receitas antigas de fsync/esync sem conferir essa versão. Somente uma divergência causal deve virar correção física.

## 3. CWD e sanitização não atravessam automaticamente launch-client

Na API launcher-service, o comando herda o ambiente salvo pelo serviço quando não se usa `--clear-env`. `--env` sobrescreve, `--unset-env` remove, `--pass-env` transporta valores do cliente. O valor vazio em `--directory=` significa usar o CWD do serviço. Fonte: [launch-client.md](https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/06a2477429fe271c5b254399caffdab8b7737e99/bin/launch-client.md).

A rota local usa `env KEY=VALUE ...` dentro da shell, sem limpeza da base. Portanto, remover WINESERVERSOCKET do mapa enviado ao Popen externo não prova sua ausência no ambiente interno. A presença dessa variável no serviço .36 **não foi medida**. Também `cwd=Path(trainer).parent` define o diretório do cliente local, enquanto `--directory=` seleciona o do serviço. Essa é uma diferença contratual confirmada, mas ainda não causal.

O serviço mantém os PIDs lançados e pode enviar SIGINT ao grupo remoto quando a conexão do cliente desaparece; também há encerramento ligado ao comando principal/parent. `start_new_session=True` do Popen local não prova o PGID do filho criado pelo serviço. Fontes: [launcher-service.c](https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/06a2477429fe271c5b254399caffdab8b7737e99/bin/launcher-service.c), [launcher-service.md](https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/06a2477429fe271c5b254399caffdab8b7737e99/bin/launcher-service.md).

**Decisão:** registrar separadamente cliente de controle e filho real: ambiente permitido, CWD, PID/PPID/PGID/SID, cgroup, namespace, NameOwnerChanged e ProcessExited. Não aplicar `env -i` genericamente: pode remover variáveis necessárias do contêiner. Não atribuir morte do jogo ao cleanup posterior.

## 4. Avaliador mascara saída precoce — RED local separado

[`evaluate_mortal_shell_run.py`](../../tools/diagnostics/evaluate_mortal_shell_run.py) exige amostra até attach + 60 s antes de examinar `game_exit_observed`. Uma entrada com identidade válida, amostra inicial e saída conhecida aos 6 s retorna:

```text
{'status': 'INVALID', 'reason': 'stability_window_incomplete'}
```

Esse evento validado deve produzir FAIL. Não é um PASS falso, mas oculta a classificação do sintoma que encerra a coleta. Os testes existentes usam amostras até 60 s mesmo em cenários de saída, deixando a lacuna passar.

**Correção planejada:** validar identidade/tempo e classificar saída antes de exigir duração completa. Conservar INVALID para coleta insuficiente sem evento confiável. O plano contém o teste RED e seus casos de controle.

## 5. Mono: pista de renderização, causa física não provada

Nos dois pins comparados, `gpath.c:115` exige `filename != NULL` em `g_path_get_basename`. A mensagem não identifica caller ou PID do jogo. O trecho não tem abort explícito; fatalidade depende do macro/build/tratamento. Fontes: [Mono usado por 10.4.1](https://github.com/wine-mono/mono/blob/1c2dfe7443db0c9d4d0c3195f657d567ca7c3ebb/mono/eglib/gpath.c#L115), [Mono usado por 11.2.0](https://github.com/wine-mono/mono/blob/775a29a0d864061a40438e38830c0afaadf9ae79/mono/eglib/gpath.c#L115).

Nenhum fix específico desse erro foi identificado. Guarda igual não exclui mudança no caller. A [release 10.4.1](https://github.com/wine-mono/wine-mono/releases/tag/wine-mono-10.4.1) corrige WPF, incluindo reversão de renderização D3D9; isso não prova que este FLiNG use WPF nem explica a saída de Dungeonhaven.

No Wine exato, Mono local no prefixo e RuntimePath do registro precedem o diretório de dados. Symlink privado não garante seleção final. Medir caminho/inode de mscoree/libmono e correlacionar PID/caller da mensagem. Fonte: [metahost.c](https://github.com/ValveSoftware/wine/blob/9358696fe9a2261329f4a83aa6a65fd436106154/dlls/mscoree/metahost.c#L747-L885).

[Wine Mono #167](https://github.com/wine-mono/wine-mono/issues/167) relata diferenças entre trainers FLiNG antigos/novos, sem match causal deste hash. Não justifica dotnet40/dotnet48 no prefixo real. Winetricks pode remover Mono e alterar registro/DLLs: [remove_mono](https://github.com/Winetricks/winetricks/blob/5a59ea07513b24093bd90fad943ecf9543cf05bc/src/winetricks#L17556-L17593).

## 6. Gamescope: patch concreto para o clique deslocado

O commit [33b4eff0fb577608b6f71c6adc0f615782aa48ef](https://github.com/ValveSoftware/gamescope/commit/33b4eff0fb577608b6f71c6adc0f615782aa48ef), verificado pela API oficial, muda a transformação de input absoluto para usar a janela, separada da textura da camada desenhada. Trata o caso em que a camada já foi ampliada para a saída e sua escala deixa de representar o tamanho da janela. O commit usa OpenVR como exemplo.

É compatível com a classe “ponteiro chega a outra coordenada”, mas não identifica a causa no FLiNG. Exige versão instalada, presença do patch, input absoluto/upscale e dimensões/foco medidos. Só então testar escala 1:1 ou build contendo o patch, com rollback. Não atualizar globalmente SteamOS/Gamescope por analogia.

A [fonte de foco/escala](https://github.com/ValveSoftware/gamescope/blob/ff6b924fd0634a51d0fb3755c56c01dca1daadc1/src/steamcompmgr.cpp) distingue janela visual e de input. Seletor Steam, superfície renderizada e contador de eventos não provam clique entregue ao controle. Essa etapa vem depois da estabilidade.

## 7. Lifecycle e precedentes

[CheatDeck features.ts](https://github.com/SheffeyG/CheatDeck/blob/main/src/domain/features.ts) configura PROTON_REMOTE_DEBUG_CMD e permissões de diretório; seu [backend](https://github.com/SheffeyG/CheatDeck/blob/main/main.py) não implementa reaper de jogo. No GE, o caminho normal cria o remote debug com o ambiente preparado e encerra seu Popen após o alvo principal retornar; runinprefix segue outro ramo. Referência de integração, não substituto automático do Relay. Fonte: [GE Session.run](https://github.com/GloriousEggroll/proton-ge-custom/blob/7e88cefffc122ea1584c2156b8d7bae6cf69b2a7/proton#L2790-L2901). Código CheatDeck consultado em main é móvel; release v2.0.0 foi identificado separadamente.

[Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/plugin/plugin.py) supervisiona o backend; o [template](https://github.com/SteamDeckHomebrew/decky-plugin-template/blob/main/main.py) fornece hooks. Arquivos focados não demonstram reaper que mate Mortal Shell. [steam-for-linux](https://github.com/ValveSoftware/steam-for-linux) é tracker, sem código suficiente para atribuir ação ao reaper fechado do Steam.

Wine tem caminhos explícitos de término por handle e por fechamento de objeto debug configurado para terminar depurados. São mecanismos a rastrear se houver evidência de attach/terminação, não prova de uso pelo FLiNG. Fontes: [process.c](https://github.com/ValveSoftware/wine/blob/9358696fe9a2261329f4a83aa6a65fd436106154/server/process.c#L1524-L1538), [debugger.c](https://github.com/ValveSoftware/wine/blob/9358696fe9a2261329f4a83aa6a65fd436106154/server/debugger.c). Um segundo cliente no mesmo wineserver não implica encerramento automático do primeiro.

O helper [GE umu.c](https://github.com/GloriousEggroll/proton-ge-custom/blob/7e88cefffc122ea1584c2156b8d7bae6cf69b2a7/umu_helper/umu.c) acompanha o alvo e obtém seu exit code. Um código 0 em outra camada/wrapper não determina a causa inicial. Medir o processo principal e também o launcher.

[Steam Runtime #529](https://github.com/ValveSoftware/steam-runtime/issues/529) descreve GUI Wine fechando com BadWindow em chamadas repetidas. É Proton 7/Soldier antigo e assinatura X11 específica; comparador útil, não match GE11/Mortal Shell. O [guia oficial de logs](https://github.com/ValveSoftware/steam-runtime/blob/master/doc/reporting-steamlinuxruntime-bugs.md) orienta coleta de runtime/Proton. Registrar build IDs reais; o [umu-runtime](https://github.com/Open-Wine-Components/umu-runtime/blob/5d61edd7221cb41e9076b3fe4cb741ddfc663144/README.md) é um derivado reconstruído, e o pin do repositório não fixa a imagem instalada.

## Cobertura dos 21 endereços

| # | Fonte | Resultado delimitado |
|---:|---|---|
| 1 | [ValveSoftware/Proton](https://github.com/ValveSoftware/Proton) | Script/verbos comparados; GE exato priorizado |
| 2 | [ValveSoftware/wine](https://github.com/ValveSoftware/wine) | Loader, servidor, processos, Mono, debugger e wineboot no pin GE |
| 3 | [WineHQ/wine](https://gitlab.winehq.org/wine/wine) | Proteção de acesso; não inferida ausência de código |
| 4 | [gamescope](https://github.com/ValveSoftware/gamescope) | Foco/escala e patch 33b4eff; aplicação ao Deck pendente |
| 5 | [GE-Proton](https://github.com/GloriousEggroll/proton-ge-custom) | GE11-6 pinado; diferenças de contrato identificadas |
| 6 | [umu-launcher](https://github.com/Open-Wine-Components/umu-launcher) | 1.4.4, reentrada e FAQ de equivalência |
| 7 | [wine-mono GitHub](https://github.com/wine-mono/wine-mono) | Releases/trees 10.4.1/11.2.0 e #167 |
| 8 | [WineHQ/wine-mono](https://gitlab.winehq.org/mono/wine-mono) | Proteção de acesso; usada fonte oficial GitHub |
| 9 | [steam-runtime](https://github.com/ValveSoftware/steam-runtime) | Guia de logs e #529, sem fix específico demonstrado |
| 10 | [steam-runtime-tools](https://gitlab.steamos.cloud/steamrt/steam-runtime-tools) | Arquivos específicos consultados apesar de bloqueios em outras rotas; CWD/env/lifecycle documentados |
| 11 | [umu-protonfixes](https://github.com/Open-Wine-Components/umu-protonfixes) | README/listagem EGS; nenhum fix exato localizado na triagem |
| 12 | [umu-runtime](https://github.com/Open-Wine-Components/umu-runtime) | Runtime derivado; pin fonte não fixa imagem do Deck |
| 13 | [SteamOS](https://github.com/ValveSoftware/SteamOS) | Tracker comunitário; sem match causal localizado |
| 14 | [portal SteamOS GitLab](https://gitlab.steamos.cloud/) | Access Denied/Anubis; portal interno não auditado |
| 15 | [índice de fontes SteamOS](https://steamdeck-packages.steamos.cloud/archlinux-mirror/sources/) | Índice acessível; nenhum pacote baixado/auditado |
| 16 | [steam-for-linux](https://github.com/ValveSoftware/steam-for-linux) | Comparadores de ambiente/launch-client/FDs; reaper fechado não inspecionado |
| 17 | [decky-loader](https://github.com/SteamDeckHomebrew/decky-loader) | Supervisão backend; sem nexo causal com jogo |
| 18 | [decky-plugin-template](https://github.com/SteamDeckHomebrew/decky-plugin-template) | Hooks; não fornece solução de attach |
| 19 | [CheatDeck](https://github.com/SheffeyG/CheatDeck) | Launch options delegadas ao Proton |
| 20 | [Winetricks](https://github.com/Winetricks/winetricks) | Verbos mutam Mono/prefixo |
| 21 | [umu-database](https://github.com/Open-Wine-Components/umu-database) | CSV sem match exato localizado; cobertura declaradamente incompleta |

Não encontrar um fix na triagem não prova que nenhum exista. GitLab inacessível e pacotes não auditados permanecem limites explícitos.

## Hipóteses e ensaio discriminante

A ordem prioriza informação obtida com poucas mudanças, não probabilidades medidas.

| Prioridade | Hipótese | Previsão | Refutação relevante |
|---|---|---|---|
| 1 | Contexto privado difere do jogo | Mesmo probe simples passa no runtime selecionado e falha no privado, com diferença medida | Ambos estáveis e contextos equivalentes |
| 2 | Inicialização CLR/seleção Mono | Probe gerenciado reproduz erro; não gerenciado passa | Gerenciado estável, falha exclusiva do FLiNG |
| 3 | Comportamento específico FLiNG/attach | Controles passam; FLiNG exato gera saída/SEH/terminação rastreada | Falha sem trainer ou com probe simples |
| 4 | Preparação/container/launcher | Preparação ou probe simples já falha; sinal/saída precede Relay | Controle preparado estável e falha restrita ao FLiNG |

Sequência adaptativa: jogo normal → jogo só com reentrada preparada → probe Wine simples no runtime selecionado → mesmo probe privado → probe gerenciado → FLiNG. Parar na primeira diferença conclusiva; não executar combinações por rotina. Cada caso fixa build, checkpoint e receita. Cópia descartável ajuda na inicialização CLR, mas cria outro prefixo/wineserver e não prova attach ao jogo original.

Critério final: estabilidade, seletor Steam, clique correto, toggle, Infinite Stamina com efeito ON/OFF, regressão GOG e nova sessão. O patch Gamescope só entra após estabilidade e medição de sua condição de aplicação.

## Verificações desta pesquisa

```text
python -m unittest tests_backend.test_environment tests_backend.test_runtime_profile tests_backend.test_runner tests_backend.test_mortal_shell_run_verdict -q
42 executados; 42 passaram; 0 falharam; 1,458 s.

python .debug/research_contract_probe.py
2 asserções de pesquisa; 2 falhas esperadas.
Prefixo Wine direto e saída precoce mascarada; exit code 1 intencional.
```

O harness usa funções locais reais com Popen falso. Não iniciou Wine e não reproduz o fechamento físico. As skills de debugging ainda exigem um reproducer do sintoma real antes de chamar qualquer hipótese de correção validada. O plano preserva essa etapa pendente.

Revisão manual: cronologia, argv, fontes pinadas, diff Gamescope, caminhos e limites de alegações. Não executados: suíte completa/frontend/build/pacote ou jogo, pois esta etapa alterou documentação. Harness/fontes/notas dos três agentes permanecem em `.debug/`, fora do commit; o plano contém a reprodução necessária para o próximo trabalho.

## Decisões de continuidade

1. .36 já corrigiu ACK; não repetir essa implementação.
2. PASS manual antigo não é referência reproduzível depois do RED posterior.
3. Corrigir avaliador e contratos sob TDD, medir manifesto e só então testar outra receita física.
4. Não instalar Mono/.NET nem atualizar Gamescope/Proton globalmente por analogia.
5. A/B que inicia Wine é execução mutável, mesmo que a coleta seja somente leitura.
6. Pesquisa/plano prontos; causa física, implementação e gates do produto continuam pendentes.
