# Mortal Shell após .36 — plano de diagnóstico e correção

> Para execução por agentes: usar `superpowers:executing-plans` ou `superpowers:subagent-driven-development`, com TDD nas alterações de comportamento. Este documento descreve trabalho futuro; sua criação não inicia testes no Deck.

**Objetivo:** localizar e corrigir o encerramento do Mortal Shell Epic ao iniciar o FLiNG; depois validar seleção Steam, clique físico e Infinite Stamina ON/OFF, preservando GOG.

**Arquitetura:** manter o watcher independente do lançamento UniFiDeck. Separar os contratos de controle do launcher e de execução do processo Wine. Corrigir defeitos locais demonstrados, medir a sessão efetiva e só alterar a integração física segundo o primeiro experimento discriminante.

**Stack:** Python/unittest, TypeScript/Vitest, UMU 1.4.4, GE-Proton11-6, Steam Runtime, Wine Mono e Gamescope.

**Especificação:** [pesquisa upstream](../../research/2026-09-07-mortal-shell-upstream-resolution-research.md), [resultado físico .36](../../notes/2026-09-07-mortal-shell-fling-outcomes-report.md), `CONTEXT.md`, ADR 0001.

## Estado e limites

Este plano substitui a sequência operacional do plano anterior `2026-09-07-mortal-shell-fling-evidence-first-correction-plan.md`. A .36 já corrigiu o ACK falso; host-direct pós-menu e o ensaio manual posterior falharam. Não reconstruir essas etapas como se fossem referências verdes.

- Identidade Epic `epic:0055e45ce7654c55aade646467349e83`; trainer x64 SHA-256 `872935c570a105d81db056264e540ffc254b2ee3cf63407afa9be65eaca41fb8`; GE `GE-Proton11-6`.
- Manter Force Compatibility desligado, UniFiDeck e Proton selecionado intactos; nenhuma instalação de .NET/Winetricks nem alteração de Mono global/prefixo real como tentativa.
- Preservar dirty tree preexistente. Commits com staging explícito; nenhum EXE, dump bruto, token, `.debug/` ou ZIP experimental no commit documental.
- Estado final remoto apenas documentado: .36 instalada, Epic desabilitado, atalho original, GOG habilitado. Revalidar antes de execução física.
- Um processo Wine pode escrever no prefixo mesmo sem instalar nada. Coleta de arquivos é somente leitura; ensaio A/B não é. Backup/rollback e escopo físico devem estar definidos antes do ensaio.
- Só receber sinais nos processos/grupos de propriedade demonstrada. PID local do launch-client não prova que o filho criado pelo serviço D-Bus está no mesmo PGID.
- Os RED locais abaixo não reproduzem o encerramento real. A fase de reprodução física das skills de debugging permanece pendente; nenhuma hipótese de crash está confirmada.

## Tarefa 1 — tornar o resultado da coleta confiável

**Arquivos:** `tools/diagnostics/evaluate_mortal_shell_run.py`, `tests_backend/test_mortal_shell_run_verdict.py`.

**Contrato:** `evaluate_run(run) -> {status, reason}` conserva PASS/FAIL/INVALID/BLOCKED. Uma saída positiva, válida e pertencente à sessão observada deve produzir FAIL mesmo quando impede a coleta de completar 60 s. Coleta ausente ou evento de outro PID não deve fabricar FAIL/PASS.

- [ ] Adicionar à classe de testes existente:

```python
def test_known_early_exit_does_not_require_sixty_seconds_of_live_samples(self):
    run = _stable_run()
    run['samples'] = run['samples'][:1]
    run['game_exit_observed'] = {
        'monotonic': 106.0, 'pid': 10, 'start_time': 20,
    }
    self.assertEqual(evaluate_run(run), {
        'status': 'FAIL', 'reason': 'game_exited_before_stability',
    })
```

- [ ] Executar `python -m unittest tests_backend.test_mortal_shell_run_verdict -v`. RED esperado no código pesquisado: `INVALID/stability_window_incomplete` em vez de FAIL.
- [ ] Validar estrutura, tempo finito e identidade do evento; avaliar saída conhecida após estabelecer a identidade inicial e antes de exigir janela completa. Não simplesmente mover qualquer timestamp sem validar PID/start-time.
- [ ] Acrescentar casos paralelos de saída do trainer aos 6 s, evento de outra sessão, evento anterior ao attach e ausência de evento com coleta curta. Os três últimos devem ser INVALID, nunca PASS. Preservar os testes existentes de baseline/menu, ordem, lacunas e identidade.
- [ ] Rodar a suíte do avaliador e reproduzir o exemplo local de pesquisa. Salvar fixture sanitizada e resultado; commit separado da integração Wine.

**Entrega verificável:** uma coleta que termina porque o jogo morreu registra FAIL com identidade; coleta interrompida sem causa permanece INVALID. Isso melhora o instrumento, não corrige o jogo.

## Tarefa 2 — separar ambiente de controle e ambiente do Wine

**Arquivos:** `trainer_relay/environment.py`, `trainer_relay/runner.py`, `trainer_relay/watcher.py`, `trainer_relay/runtime_profile.py`; testes correspondentes de environment, runner, watcher e runtime_profile.

**Contrato:** o UMU novo recebe a raiz compatdata; Wine direto recebe o prefixo Wine efetivo da sessão. HOME/PATH/DBus usados para consultar o serviço não substituem automaticamente o contexto do processo dentro do contêiner. Sanitização precisa valer na fronteira final.

- [ ] Transformar o primeiro caso de `.debug/research_contract_probe.py` em teste de integração local entre sanitizer e runner. Usar Popen falso e analisar o argv; não executar Wine.
- [ ] Entrada explícita do teste: raiz `/fixture/compatdata`, prefixo observado `/fixture/compatdata/pfx`, rota privada `container_reentry`; exigir `WINEPREFIX=/fixture/compatdata/pfx` no comando Wine direto. Manter teste separado exigindo a raiz na rota que realmente chama UMU.
- [ ] Rodar `python -m unittest tests_backend.test_environment tests_backend.test_runner tests_backend.test_watcher -q`. O novo caso deve falhar pelo prefixo errado, não por import ou mock inválido.
- [ ] Transportar os dois valores separadamente entre descoberta e spawn; validar vínculo com a sessão. Não alterar globalmente `build_sanitized_environment`, pois o contrato UMU existente usa a raiz corretamente. Não concatenar `/pfx` cegamente nem mudar symlinks.
- [ ] Para ambiente interno, construir teste com variáveis extras no serviço falso: a ausência de `WINESERVERSOCKET`/comando remoto deve continuar verdadeira após a fronteira launch-client. Preservar variáveis necessárias do contêiner; não aplicar `env -i` como correção genérica sem definir o conjunto completo.
- [ ] Verificar CWD real na versão instalada e no contêiner. A fonte upstream pesquisada confirma que `--directory=` vazio herda CWD do serviço; o `cwd=` do Popen externo não define o diretório interno. Se divergir do diretório do trainer, teste o caminho explícito e válido no namespace antes de promover a mudança.
- [ ] Na fixture de GE, acrescentar diretórios multiarch. Comparar o comando com o layout da versão exata; não confundir `lib/wine` com as bibliotecas ELF em `lib/x86_64-linux-gnu` e `lib/i386-linux-gnu`.
- [ ] Rodar os quatro módulos afetados. Commit somente dos contratos demonstrados. Nenhum claim de estabilidade física.

**Entrega verificável:** relatório do comando final com valores permitidos, origem de cada valor e testes da fronteira externa/interna. A mudança de prefixo só resolve uma diferença física se root e pfx forem objetos distintos na sessão real.

## Tarefa 3 — estabelecer observação antes do próximo FLiNG

**Arquivos:** estender o coletor existente `tools/diagnostics/deck_live_probe.ps1`; criar, se necessário, um coletor limitado em `tools/diagnostics/collect_mortal_shell_session.py` com teste `tests_backend/test_mortal_shell_session_evidence.py`.

**Entrada/saída do coletor:** identidade do jogo e run ID; JSON sanitizado com hora monotônica, PID/start-time, PPID, PGID, SID, UID, cgroup, namespace de PID/mount, prefixo real/device/inode, socket do wineserver, CWD, executável e caminhos dos módulos carregados. Sem argv completo/EOS, ambiente bruto, credenciais ou dump publicado.

- [ ] Revalidar versão instalada, ZIP/hash, trainer/hash, GE, UMU, Mono carregado, Gamescope e VERSIONS.txt do runtime. Mapear ambos `Dungeonhaven.exe` e `Dungeonhaven-Win64-Shipping.exe`; perder um launcher não equivale automaticamente a perder o jogo.
- [ ] Com jogo sem trainer, ler `/proc` e artefatos já disponíveis. Ler prefix root/pfx com `realpath` e `stat` dentro do namespace relevante. Registrar se são o mesmo objeto. Não iniciar Wine para fazer essa medição.
- [ ] Coletar o ambiente final permitido em uma shell de diagnóstico no serviço, sem iniciar Wine. Comparar UID/CWD/PATH/DISPLAY/XDG, prefixo, `WINEDLLPATH`, `LD_LIBRARY_PATH`, `WINENTSYNC`/fsync/esync e presença de FDs transitórios. Medir presença de variáveis rejeitadas sem registrar conteúdo sensível.
- [ ] Para o futuro coletor, testar uma fixture com PID reciclado e uma com processo principal encerrado. Exigir INVALID no primeiro caso e evento vinculado à identidade no segundo. Rejeitar dados inacessíveis como desconhecidos; não tratá-los como zero/ausência.
- [ ] Definir o observável de término antes do ensaio: log fatal de Unreal/Wine, coredump existente ou traço autorizado do evento de saída/sinal. `gameprocess_log` e `/proc` podem mostrar a saída sem identificar seu autor. `strace`/eBPF/ptrace alteram condições e permissões; só escolher após verificar disponibilidade e necessidade, sem instalar ferramentas por suposição.
- [ ] Se for necessário habilitar logs, limitar o intervalo e usar as opções documentadas do Steam Runtime/Proton. Sanitizar antes de anexar; não publicar dump nem log completo do launcher.

**Entrega verificável:** manifesto de uma sessão, cobertura e lacunas explícitas. Sem observável de causa, não concluir “Mono”, “Steam reaper” ou “wineserver matou o jogo”.

## Tarefa 4 — experimento mínimo e adaptativo

**Local de resultados:** `docs/notes/YYYY-MM-DD-mortal-shell-run-<id>.md` e fixtures sanitizadas do avaliador. Cada linha abaixo usa nova sessão, mesma build/save/checkpoint e somente uma diferença por comparação. Restaurar o estado entre ensaios; não persistir tentativa de migração ao desabilitar Epic.

| Ordem | Ensaio | Pergunta e condição de parada |
|---|---|---|
| A0 | Atalho UniFiDeck original, Epic desabilitado, sem sidecar | O jogo sobrevive 60 s no checkpoint? Se falhar, investigar jogo/launcher antes de trainer. |
| A1 | Mesmo jogo, apenas reentrada preparada, sem sidecar | A preparação sozinha muda estabilidade? Se falhar, interromper a linha FLiNG e investigar UMU/runtime. |
| B | Mesma sessão preparada, pequeno processo Wine não gerenciado pelo mesmo launch-client e runtime selecionado | A entrada de outro cliente é suficiente? Evitar winecfg/regedit como controle porque alteram configuração. Usar probe mínimo previamente inspecionado que apenas permanece vivo e sai. |
| C | Mesmo controle, apenas runtime privado no lugar do selecionado | A diferença pertence ao clone/layout/bibliotecas? Se falhar, coletar módulos e resolver antes de FLiNG. |
| D | Rota estável, pequeno probe gerenciado com Mono medido | A inicialização CLR é suficiente? Não instalar Mono no prefixo para realizar o controle. |
| E | Mesma rota e checkpoint, FLiNG exato, sem interação | Só o FLiNG provoca o encerramento? Coletar sua inicialização, attach e falha do jogo. |

- [ ] Começar por A0/A1; executar a próxima linha somente se acrescentar informação. Não repetir todos os casos se a primeira divergência já localizou a fronteira.
- [ ] B e C formam comparação do mesmo executável. Para D, manter runtime/namespace/CWD constantes; distinguir gerenciado de não gerenciado. Para E, manter runtime constante e verificar qual Mono foi efetivamente carregado.
- [ ] Registrar saídas aos poucos segundos como FAIL; observação perdida como INVALID. 60 s é gate inicial, não prova de funcionamento prolongado nem de cheats.
- [ ] Se B passar e C falhar, priorizar bibliotecas/módulos do clone. Se C passar e D falhar, priorizar CLR. Se D passar e E falhar, investigar o trainer exato/attach; outra versão de trainer não é comparação de uma única variável sem reconhecer essa troca.
- [ ] Se há saída interna Wine, correlacionar NTSTATUS/SEH e chamador/alvo de término. Se há sinal externo, identificar emissor e relação com cgroup/launcher. Presença de um reaper na árvore não basta.
- [ ] Parar ao primeiro resultado conclusivo para produzir uma correção mínima com RED/GREEN. Não aumentar delay, trocar Proton ou somar variáveis a um ensaio falho.

## Tarefa 5 — aplicar a correção causal e validar o objetivo inteiro

**Arquivos:** somente os que produzem a primeira diferença causal nas tarefas anteriores; depois testes correspondentes, documentação de validação e handoff.

- [ ] Registrar hipótese confirmada com previsão, trace e comparação. Escrever regressão na fronteira real antes do patch; se não houver seam automatizável, conservar o reproducer físico e registrar essa limitação.
- [ ] Corrigir uma variável; repetir o caso que falhava com a mesma receita. Um processo artificial estável não substitui FLiNG + jogo.
- [ ] Rodar `python -m unittest discover -s tests_backend -p 'test_*.py'`, `python -m unittest discover -s tests_packaging -p 'test_*.py'`, `pnpm run check` e `python -m compileall trainer_relay tools/diagnostics` para o candidato final. Resolver falhas relevantes antes de empacotar.
- [ ] Empacotar uma única versão candidata após o diagnóstico, verificar hash e rollback, instalar pelo fluxo oficial e conferir a versão realmente carregada.
- [ ] Validar em ordem: duas identidades estáveis por 60 s; janela no seletor Steam; alternância jogo/trainer; clique físico no controle certo; toggle ON/OFF; Infinite Stamina com efeito e reversão; regressão GOG e persistência do atalho. Repetir uma nova sessão para evitar PASS ocasional.
- [ ] Se estabilidade passar e coordenadas falharem, abrir investigação de input separada: correlacionar superfície/XID, foco, escala e posição real de um clique. Conferir se a versão instalada contém o patch Gamescope `33b4eff0fb577608b6f71c6adc0f615782aa48ef` e se há input absoluto com textura previamente ampliada. Somente com essa condição medida considerar escala 1:1 ou build candidata isolada; não atualizar SteamOS globalmente. `WM_HINTS.Input`, contador Gamescope e hotkey sintética não provam clique nativo.
- [ ] Atualizar relatório/handoff, publicar commits explícitos e informar o que passou. Não usar “corrigido” com qualquer gate físico pendente.

## Encerramento desta etapa de planejamento

Pesquisa e dois RED locais concluídos; 42 testes existentes passaram. Nenhum código de produto foi alterado e nenhuma etapa física acima foi executada. Próximo trabalho concreto: tarefa 1, seguida do contrato de ambientes e manifesto da sessão. A causa inicial do encerramento segue desconhecida.
