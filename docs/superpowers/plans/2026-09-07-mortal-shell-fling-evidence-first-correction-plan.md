# Mortal Shell FLiNG — plano de correção orientado por evidências

> **For agentic workers:** usar `superpowers:executing-plans` para executar as tarefas sequencialmente, com TDD e revisão a cada entrega. Este documento é um plano; sua criação não autoriza execução no Deck.

**Goal:** abrir Mortal Shell Epic pelo UniFiDeck normal e usar o FLiNG como segunda janela selecionável pelo Steam, com clique correto e stamina ON/OFF observável, preservando GOG.

**Architecture:** separar elegibilidade do trainer, validação da sessão/runtime e execução do sidecar. Para a combinação exata já investigada, avaliar a rota privada host-direct antes de qualquer operação de container; conservar o contrato de reentrada das demais combinações. Promover essa rota a correção física somente depois de repetir o lançamento manual em baseline limpo e compará-lo ao automático.

**Tech Stack:** Python/unittest, TypeScript/React/Vitest, Decky, SteamOS, UniFiDeck, UMU, GE-Proton11-6, runtime privado Wine Mono 10.4.1.

**Spec e evidência de entrada:** `docs/notes/2026-09-07-mortal-shell-fling-outcomes-report.md`, `CONTEXT.md`, `docs/adr/0001-session-watcher.md`. O relatório contém recomendações anteriores, não comandos autorizados nesta sessão. Quando divergir de evidência mais específica, prevalece a medição explicitamente identificada.

## Restrições e critério de encerramento

- Atalho Epic normal: `epic:0055e45ce7654c55aade646467349e83`; não ativar Force Compatibility nem escolher outro Proton.
- Não instalar Winetricks/.NET, trocar Mono global ou reconstruir o prefixo real como tentativa de correção.
- Não copiar argumentos EOS/Epic, tokens ou ambiente completo para logs, Git ou relatórios.
- Identidade: `epic:0055e45ce7654c55aade646467349e83`; trainer SHA-256 `872935c570a105d81db056264e540ffc254b2ee3cf63407afa9be65eaca41fb8`; PE `x64`; Proton `GE-Proton11-6`; Mono privado `wine-mono-10.4.1`.
- Somente grupos de processos comprovadamente criados pelo Relay podem receber sinais. Compartilhar prefixo/wineserver ainda pode criar interação indireta; PGID separado não prova independência completa.
- Não generalizar a exceção para toda Epic nem remover a exigência global de reentrada.
- Preservar alterações preexistentes. Não publicar EXE, `.debug/`, anexos remotos ou pacote montado de código parcial.
- Conclusão exige todos os gates físicos no final deste plano. Processo vivo por 3 segundos, janela X11, ACK de hotkey e suíte local verde não equivalem a produto funcionando.

## 1. Resultado da análise atual

### Confirmado nesta sessão

| Evidência | Resultado | Implicação |
|---|---|---|
| Dois testes focados, executados duas vezes | Em cada execução: 2 executados, 1 passou, 1 falhou | O estado já difere do RED descrito no relatório; a API de descoberta existe |
| Backend completo | 303 executados, 302 passaram, 1 falhou, 31,552 s | A única falha observada é a integração do perfil host-direct no watcher |
| Frontend focado | 4 arquivos, 35 testes, 35 passaram | Os testes atuais aprovam o contrato genérico de preparação; falta o caso exato sem alterar atalho |
| `watcher.py`, `_poll_identity` | Não passa `require_container_reentry` à descoberta | O valor padrão continua `True`, apesar do predicado parcial existente |
| `watcher.py`, `_spawn` | Executa `_container_probe.verify` antes do resolvedor privado | A rota host-direct continua dependente de um serviço que não usa para executar |
| `watcher.py`, resolução privada | `None`/exceções podem seguir para `umu_direct` | Uma exceção à descoberta sem corrigir esse fallback abre uma rota diferente da pretendida |
| `watcher.py`, lifecycle e command context | Confirmação de reentrada e bus continuam pressupostos | Corrigir só o primeiro spawn deixa revalidação/estado/comandos inconsistentes |
| `migration.ts` → `viewModel.ts` → controller | Trainer configurado gera preparação NSENTER; enable depende dela | A interface pode bloquear o fluxo normal ou voltar a propor a alteração do atalho |
| `_build_watcher` / `_host_environment` | Há `home` do usuário, mas o ambiente novo nasce de `os.environ` | É necessário verificar UID/HOME/DBus/XDG reais do processo Decky; o teste injeta valores e não prova isso |

Comando reproduzível, sem alterar implementação:

```powershell
python -m unittest tests_backend.test_process.ProcessDiscoveryTests.test_allows_a_matching_session_without_reentry_only_when_caller_explicitly_opts_out tests_backend.test_watcher.WatcherTests.test_exact_runtime_profile_bypasses_container_reentry_for_the_proven_host_launch -v
```

Saída relevante: `Ran 2 tests`; `FAILED (failures=1)`; `tests_backend/test_watcher.py:497`, `[True] != [False]`. A primeira execução durou 0,132 s; a segunda, 0,030 s. Este é um loop RED local da integração, **não uma reprodução da saída do jogo**.

### Histórico que ainda exige confirmação física

O relatório consolidado registra janela completa, alternância e stamina funcional em lançamento manual. O ledger `docs/research/2026-09-06-fling-toggle-root-cause-ledger.md` qualifica o PASS de stamina como histórico, sem caminho reproduzível preservado. Portanto, existe evidência favorável de compatibilidade, mas não uma receita versionada que permita declarar o resultado repetível.

Os documentos também registram jogo encerrando antes do SIGTERM enviado pelo Relay ao trainer. Isso enfraquece a explicação específica de cleanup matar primeiro o jogo; não exclui efeitos anteriores do attach, ambiente, wineserver ou cgroup. A restauração do atalho seguida de jogo vivo é evidência favorável à topologia, mas não isola topologia e attach em condições idênticas.

O estado do Deck — versão `.32`, Epic desativado, GOG habilitado, atalho restaurado — é histórico do relatório e **não foi consultado nesta sessão**. Não usar IP ou PID antigo como estado atual.

### Fonte primária reconsultada

A [FAQ oficial do UMU](https://github.com/Open-Wine-Components/umu-launcher/wiki/Frequently-asked-questions-%28FAQ%29) exige `runinprefix`/`run` e configuração Proton/Wine equivalente para processos adicionais no mesmo prefixo. Isso justifica medir sincronização e ambiente. Não demonstra, isoladamente, que toda execução direta de Wine é inválida ou que descartar determinada variável causou esta saída. Os documentos anteriores avançam além da fonte quando tratam isso como diagnóstico fechado.

## 2. Decisão de diagnóstico

Não lançar outra versão apenas terminando os dois testes. Há dois resultados diferentes a obter:

1. **Contrato local:** selecionar o caminho correto sem depender de reentrada, sem fallback e sem preparar atalho indevidamente. Há RED local para começar o TDD.
2. **Sintoma físico:** jogo continuar vivo após attach e controles funcionarem. Ainda falta um loop atual que reproduza esse sintoma com os fatores controlados.

As skills solicitadas exigem loop RED antes de avançar à causa. Assim, a fase física permanece em coleta/reprodução; os fatores abaixo são variáveis a discriminar, não causas confirmadas nem autorização para aplicar correções experimentais.

| Prioridade de medição | Variável | Evidência que permite decidir |
|---|---|---|
| 1 | Caminho manual versus automático no atalho original | Mesmo runtime, prefixo, cenário carregado e entrada; manual passa e automático falha, com diff de argv/ambiente/UID/cwd/cgroup |
| 2 | Prontidão de engine/EOS | Attach após confirmação visual funciona repetidamente; PID estável por tempo fixo, sozinho, não prevê o resultado |
| 3 | Configuração Wine e contexto do host | Diferença observada em fsync/esync, overrides, usuário, server ou prefixo distingue execução boa e ruim |
| 4 | Encerramento do jogo versus perda de descoberta | PID/start-time continua vivo quando o watcher registra `session_ended`, ou saída real tem evento de causa anterior ao cleanup |

Não recolocar NSENTER no atalho real para provar uma tese. Se uma comparação destrutiva de topologia se tornar indispensável, realizá-la somente em ambiente descartável explicitamente autorizado.

## 3. Tarefa A — construir a referência física e o veredito

**Arquivos:** revisar `tools/diagnostics/deck_live_probe.ps1` e `watch_mortal_shell_session.ps1`; criar `tools/diagnostics/evaluate_mortal_shell_run.py`, `tests_backend/test_mortal_shell_run_verdict.py` e um registro saneado em `docs/research/2026-09-07-mortal-shell-controlled-runs.md` durante a execução futura.

**Interface do avaliador proposto:** `evaluate_run(run: dict) -> dict`, com campos `status` (`PASS`, `FAIL`, `INVALID`, `BLOCKED`) e `reason`. Entrada contém `run_id`, `baseline_verified`, `menu_confirmed`, `attach_monotonic`, `samples`, `game_exit_observed` e `trainer_exit_observed`. Cada amostra contém tempo monotônico e identidade PID/start-time dos dois processos; identidade nova não conta como sobrevivência da anterior.

- [ ] Recuperar a receita manual e hashes dos artefatos anteriores. `.debug/scoped-mono-env.sh` contém operações `systemctl stop` e depende de `/tmp/tr_direct.sh`; não é um probe somente leitura nem uma receita autossuficiente. Se o arquivo original não existir, marcar referência ausente e montar uma receita revisável antes do ensaio; não chamar uma reconstrução de replay idêntico.
- [ ] Verificar acesso existente e estado atual em leitura. Não instalar chave, autenticar ferramenta nova ou habilitar Epic como efeito colateral do coletor.
- [ ] Capturar identificação dos arquivos, versão efetiva, appid, launch options saneadas, UID, caminho/inode do prefixo, PID/start-time, wineserver, cwd, cgroup e presença/valores técnicos permitidos de ambiente. Comparar ambiente **na entrada efetiva de `Popen`**, pois o runner o filtra novamente.
- [ ] Escrever testes do avaliador antes de implementá-lo: duas identidades sobrevivem 60 s → PASS de estabilidade; saída real antes do prazo → FAIL; amostras insuficientes/lacuna de coleta → INVALID; falta de menu/receita/acesso → BLOCKED. Um log `trainer_running` sem amostras nunca passa. Isso testa o avaliador, não prova o comportamento físico.
- [ ] Rodar RED, implementar somente avaliação, rodar GREEN:

```powershell
python -m unittest tests_backend.test_mortal_shell_run_verdict -v
```

- [ ] Em ensaio físico autorizado, manter Epic automático desligado e atalho original; aguardar menu/cenário carregado com confirmação humana registrada. Observar baseline por pelo menos 60 s.
- [ ] Fazer uma única execução da receita manual revisada, sem toggles. Observar ambos por 60 s e salvar registro. Repetir em três inicializações independentes, sem outras mudanças. Sessão encerrada pelo usuário é INVALID para sobrevivência, não FAIL.
- [ ] Executar o avaliador via `python tools/diagnostics/evaluate_mortal_shell_run.py CAMINHO_DO_REGISTRO_JSON`. O caminho é o artefato real produzido pela coleta, nunca PID/estado histórico codificado no script.
- [ ] Se o manual pós-menu falhar, parar promoção de host-direct e coletar a causa do término. Não compensar com mais delay. Se passar, congelar receita/hash e comparar com o automático posterior no mesmo cenário.
- [ ] Atualizar ledger/handoff e criar commit apenas dos scripts, testes e evidência saneada.

**Saída:** referência repetível ou bloqueio explicitamente identificado. Não é obrigatório provocar novamente uma falha no Deck para aceitar um histórico; é obrigatório não alegar reprodução atual sem executá-la.

## 4. Tarefa B — fechar a seleção e a execução da rota exata em TDD

**Arquivos:** `trainer_relay/process.py`, `runtime_profile.py`, `watcher.py`, `runner.py`, `main.py`, `diagnostics.py`; testes correspondentes em `tests_backend/`.

**Interfaces existentes a preservar:** `ProcessDiscoverer.discover(..., expected_session=None, require_container_reentry=True)`, `resolve_scoped_wine_runtime(home, *, identity, trainer_sha256, trainer_arch, proton_path, runtime_files=None) -> ScopedWineRuntime | None`, `OwnedTrainerRunner.spawn(..., expected_reentry_bus=None, scoped_runtime=None)`.

**Separação necessária:** identidade/hash/arquitetura elegíveis permitem **somente descoberta provisória** sem NSENTER. Depois de observar a sessão, o resolvedor valida GE e arquivos privados; somente o perfil integralmente válido autoriza spawn. A descoberta não tem `PROTONPATH` antes de ler o candidato, portanto não fingir validação integral antecipada.

- [ ] Usar o RED já existente. Acrescentar teste com `ProcessDiscoverer` real e `/proc` temporário, adaptando `test_real_proc_session_survives_main_thread_rename_until_running`; `FakeDiscoverer` sozinho aceita sessão mesmo com política errada.
- [ ] Casos negativos: outra identidade/hash/x86 mantêm `True`; arquivo ilegível não autoriza bypass; candidato exato com Proton diferente/runtime ausente/arquivo crítico divergente falha fechado e não chama probe nem runner; múltiplas sessões e PID reciclado continuam bloqueados.
- [ ] Testar `_spawn` isoladamente com probe que lança `AssertionError` se consultado na rota exata. Testar resolvedor retornando `None` e levantando erro, com `runner.spawn_calls == []` e diagnóstico `scoped_runtime_unavailable`.
- [ ] Passar o parâmetro explícito à descoberta; após observar a sessão, resolver o runtime privado **antes** de UMU/preflight de container. Para candidato exato inválido: registrar diagnóstico limitado, travar retry automático nessa sessão e retornar. Para demais perfis: executar a rota existente.
- [ ] Na rota validada host-direct, usar `expected_reentry_bus=None`, sem `launch_client`. Preservar `DISPLAY` e `WINEPREFIX` da sessão e o ambiente host verificado; não normalizar cegamente o prefixo como se fosse argumento de uma nova chamada UMU. Comparar os inodes com a âncora esperada.
- [ ] Verificar o ambiente real de Decky e injetá-lo por `host_environment` em `main.py`. Não assumir que `Path.home()`, `os.environ['HOME']` ou `/run/user/1000` identificam corretamente o usuário. Ambiente incompleto/incoerente deve produzir `scoped_runtime_host_invalid`, sem spawn.
- [ ] Manter a remoção de `WINESERVERSOCKET`. Comparar `WINEFSYNC`, `WINEESYNC` e `WINEDLLOVERRIDES` com a referência antes de decidir preservar/remover; a documentação não substitui esse diferencial.
- [ ] Testar a chamada real ao runner com `Popen` substituído: argv `[runtime.wine, trainer]`, Wine/server corretos, ambiente final esperado, grupo próprio, nenhum launch-client ou bus. Não basta verificar o ambiente intermediário recebido pelo FakeRunner.

Esqueleto de decisão para orientar implementação, sem alterar produto nesta sessão:

```python
requires_reentry = self._requires_container_reentry(identity, trainer_path)
discovery = self._process_discoverer.discover(
    identity, entry.executable, prefix,
    expected_session=state.session,
    require_container_reentry=requires_reentry,
)
# Somente depois de validar discovery.session e seu environment:
# candidato privado -> resolver perfil completo -> bloquear se None -> host spawn
# demais candidatos -> contrato de preflight/reentrada existente
```

- [ ] Rodar RED/GREEN em cada incremento; depois rodar:

```powershell
python -m unittest tests_backend.test_process tests_backend.test_runtime_profile tests_backend.test_environment tests_backend.test_runner tests_backend.test_watcher tests_backend.test_main -v
```

- [ ] Registrar diff da receita manual versus argv/ambiente final automático com campos saneados, atualizar handoff e commit explícito. Não empacotar ainda.

## 5. Tarefa C — manter o contrato ao longo da sessão

**Arquivos:** `trainer_relay/watcher.py`, `runner.py`, `types.py`, `diagnostics.py`; `tests_backend/test_watcher.py`, `test_runner.py`, `test_diagnostics.py`, `test_cheat_service.py` e `test_command_runner.py` conforme o contrato existente.

- [ ] Antes de mudar estado, acrescentar testes para segundo poll sem NSENTER, retry, mudança PID/start-time, troca do trainer após aprovação e saída do jogo. Cada ciclo deve usar a mesma política validada e invalidar evidência quando identidade/hash/sessão muda.
- [ ] Separar prontidão do processo de confirmação de container. Acrescentar `launch_mode: str | None` em `_RelayState`, limpar no reset e persistir somente depois do preflight. Host-direct não deve emitir `container_reentry_confirmed` nem exigir bus fictício para manter a janela viva; reentry genérico conserva marker/deadline.
- [ ] Manter os metadados Steam usados pelo associador de janela separados do ambiente mínimo do processo. Excluir `SteamGameId` do subprocesso não pode apagar a identidade que o associador precisa.
- [ ] Testar contexto de comando: controles nativos na janela FLiNG não dependem de `_command_context_unlocked`. Para o helper RPC que atualmente exige bus, conservar bloqueio explícito `command_route_unsupported` no modo host-direct até existir transporte validado. Não fabricar bus nem remover guardas globais para fazê-lo passar. A UI deve comunicar indisponibilidade dessa rota, sem impedir uso do trainer nativo.
- [ ] Testar que sinal só atinge grupo próprio; registrar saída observada do jogo separadamente de candidato rejeitado. Se PID existe mas falhou revalidação, não chamar isso de prova de crash.
- [ ] Rodar módulos afetados; atualizar handoff/commit. Testes devem reprovar o comportamento antigo antes de qualquer correção.

## 6. Tarefa D — configurar o perfil pela interface sem contaminar o atalho

**Arquivos:** `trainer_relay/runtime_profile.py`, `rpc.py`, `main.py`; `src/infra/relayRpc.ts`, `src/domain/relay/types.ts`, `migration.ts`, `viewModel.ts`, `src/hooks/useRelayPageController.tsx`, `src/views/RelayPage.tsx`; `tests_backend/test_rpc.py`, `test_main.py`, `tests/relay-rpc.test.ts`, `relay-migration.test.ts`, `relay-view-model.test.ts`, `relay-page.test.ts`.

**Contrato proposto:** RPC somente leitura `get_relay_launch_policy({identity, trainerPath})` lê hash/arquitetura no backend e responde campos `identity`, `trainerPath`, `trainerSha256`, `policy`, `diagnostic`. `policy` é `host_direct_candidate`, `container_reentry` ou `blocked`. Candidato não significa runtime pronto; B faz a validação integral com a sessão ativa. O frontend nunca concede a exceção por nome de arquivo ou identidade sozinha.

```typescript
type RelayLaunchPolicy = {
  identity: LaunchIdentity;
  trainerPath: string;
  trainerSha256: string | null;
  policy: "host_direct_candidate" | "container_reentry" | "blocked";
  diagnostic: { code: string } | null;
};
```

- [ ] Testar o RPC com arquivo real de fixture e digest calculado; hash recebido do cliente não pode conferir autorização. Falha de leitura → blocked; trainer não allowlisted → contrato genérico. Invalidar resposta na troca de identity/path e revalidar hash no backend no spawn.
- [ ] Adicionar quarto argumento opcional `launchPolicy` a `buildTrainerRelayViewModel` e argumento de política a `planLegacyMigration`, preservando o comportamento genérico quando ausente. Somente resposta correspondente a identity/path atuais pode liberar o candidato privado. Resposta atrasada de outra escolha deve ser descartada.
- [ ] Criar teste RED do modelo: atalho original + trainer exato + policy candidata → `migration.status == 'none'`, enable disponível; caso GOG continua exigindo preparação; policy bloqueada não habilita.
- [ ] Criar teste RED do controller: selecionar/habilitar/desabilitar candidato privado não chama `writeLaunchOptions`. O texto deixa de pedir reentrada para esse candidato. Payload inválido nunca libera o fluxo.
- [ ] Exemplo de expectativa que falta hoje, dentro de `relay-view-model.test.ts`:

```typescript
const identity = "epic:0055e45ce7654c55aade646467349e83";
const trainerPath = "/home/deck/Trainers/MortalShell.exe";
const model = buildTrainerRelayViewModel(
  { status: "ready", snapshot: {
    command: "/usr/bin/unifideck-launcher", launchOptions: identity,
  } },
  { enabled: false, trainerPath },
  undefined,
  { identity, trainerPath,
    trainerSha256: "872935c570a105d81db056264e540ffc254b2ee3cf63407afa9be65eaca41fb8",
    policy: "host_direct_candidate", diagnostic: null },
);
expect(model.kind).toBe("supported");
if (model.kind !== "supported") throw new Error("expected supported model");
expect(model.migration).toEqual({ status: "none" });
expect(model.controls.enable).toBe(true);
```

- [ ] Se ainda houver NSENTER/legado no atalho, bloquear e apresentar restauração revisável. Preservar confirmação e leitura de retorno; nunca remover opções desconhecidas ao desativar. `.debug/restore-mortal-shell-launch-options.ps1` usa valor/appid exatos e não deve ser executado automaticamente por este plano.
- [ ] Implementar o mínimo, rodar os testes abaixo, atualizar CONTEXT/ADR explicando candidato versus runtime validado e commit explícito:

```powershell
python -m unittest tests_backend.test_rpc tests_backend.test_main -v
node node_modules/vitest/vitest.mjs run tests/relay-rpc.test.ts tests/relay-migration.test.ts tests/relay-view-model.test.ts tests/relay-page.test.ts
```

## 7. Tarefa E — decidir prontidão com o diferencial físico

Dependência: referência A e integração B–D. Não aumentar `MORTAL_SHELL_LAUNCH_STABILIZATION_SECONDS` para declarar solução.

- [ ] Repetir manual e automático após o mesmo marco visual, sem toggles. Usar o avaliador de A. Se ambos passam, avaliar startup automático normal separadamente.
- [ ] Se só pós-menu passa, especificar uma ação de iniciar trainer para a sessão atual antes de implementá-la. O clique deve vincular PID/start-time/hash e expirar na troca de sessão; testar stale request e clique duplo antes de criar o botão. Esta é uma entrega condicional orientada pela medição, não requisito já comprovado.
- [ ] Se manual passa e automático falha, comparar apenas diferenças efetivas capturadas e testar uma variável por vez. Se ambas falham, não promover host-direct; revisar configuração da sessão e evidência de saída antes de experimentar outra rota.
- [ ] Um ensaio `runinprefix` em prefixo descartável pode investigar inicialização/compatibilidade, mas não prova attach ao jogo no prefixo real. Não transformá-lo em fallback automático.

## 8. Tarefa F — gates de entrega e validação do produto

**Arquivos:** `docs/STEAM-DECK-VALIDATION.md`, `docs/adr/0001-session-watcher.md`, `CONTEXT.md`, `README.md`, handoff da execução e `package.json` somente quando houver candidato validável.

- [ ] Revisar toda a alteração preexistente incluída na futura release. Os arquivos parciais estão fora de HEAD; um checkout limpo de `10e3269` não contém o mesmo código analisado. Isolar com cópia seletiva revisada ou snapshot explícito; não transportar `.debug/` indiscriminadamente.
- [ ] Executar backend completo, frontend completo, packaging, lint, typecheck e build. Repetir Python 3.12/Linux no CI: nesta análise o backend rodou em Python 3.14/Windows.

```powershell
python -m unittest discover -s tests_backend -p 'test_*.py'
python -m compileall -q main.py trainer_relay tests_backend tests_packaging
pnpm run check
python -m unittest discover -s tests_packaging -p 'test_*.py'
```

- [ ] Somente depois dos gates, versionar/empacotar pelo script existente. Registrar hash do ZIP, commit e manifesto. Conferir que `runtime_profile.py` e dependências estão no pacote; uma árvore privada existente no Deck é pré-requisito a verificar, não prova de que o ZIP a fornece.
- [ ] Preparar backup verificável de plugin/settings/atalho e instruções de rollback. Instalar pelo fluxo oficial do Decky somente na fase autorizada; não publicar tag antes dos gates. O workflow atual publica tags dependendo de `build-plugin`, sem depender dos jobs backend/frontend; portanto não tratar publicação automática como prova de validação completa.
- [ ] Testar fisicamente nesta ordem, interrompendo no primeiro gate falho:

| Gate | Critério de aprovação |
|---|---|
| Baseline | Atalho original confirmado; jogo carregado sem attach por 60 s |
| Estabilidade | Jogo + trainer por 60 s após attach em 3 inicializações independentes; complementar com 5 min de gameplay |
| Seletor Steam | Usuário alterna jogo → trainer → jogo; não basta X11/STEAM_GAME |
| Clique | Touch e trackpad avaliados separadamente, posição/escala registradas; clique acerta controle visado |
| Toggle | Infinite Stamina ON e OFF mudam o controle visível |
| Efeito | Mesmo cenário e ação: OFF consome stamina, ON não consome, OFF volta a consumir; registrar condições e observação |
| GOG | Caminho anterior, seleção de janela e comportamento conhecido repetidos; enable/disable/retry sem regressão |
| Persistência | Reabrir configuração e reiniciar sessão preserva atalho original e seleciona política correta |

- [ ] Se coordenadas falharem com processos estáveis, abrir subdiagnóstico de input com evento/posição/geometria e teste próprio. Não misturar ajuste de escala, Mono ou hotkey sintética ao teste de lifecycle.
- [ ] Atualizar documentação, handoff e GitHub com resultados reais. Qualquer gate não executado continua pendente, mesmo com todas as suítes locais verdes.

## 9. Verificação desta sessão de planejamento

- Dois testes focados: executados duas vezes, 1 PASS / 1 FAIL em cada execução.
- Backend completo: 303 testes; 302 PASS / 1 FAIL, falha esperada do watcher.
- Frontend focado: `node node_modules/vitest/vitest.mjs run tests/relay-migration.test.ts tests/relay-view-model.test.ts tests/relay-page.test.ts tests/relay-rpc.test.ts`; 35 PASS / 0 FAIL.
- Tentativa equivalente via `pnpm exec vitest ...` não produziu saída e foi interrompida; executado o Vitest 4.1.10 já instalado diretamente via Node. Causa do bloqueio do launcher não diagnosticada; nenhuma dependência instalada nesta sessão.
- Nenhum teste físico, build, packaging ou suíte frontend completa foi executado nesta análise. Não há correção implementada nem novo pacote.
- Erros exploratórios de caminho `.ts` foram resolvidos usando o caminho real `src/hooks/useRelayPageController.tsx`; não representam falha de produto.

## 10. Ordem de retomada

Ler este plano e o handoff da mesma data; conferir Git e estado atual. A e a coleta local de B podem avançar independentemente, mas nenhuma aprovação local substitui A/E/F. Terminar B–D com RED/GREEN e revisão; comparar execução física em E; liberar somente após F. O próximo passo físico depende de acesso disponível e do usuário confirmar o cenário carregado; o próximo passo local não depende de modificar o Deck.
