# Handoff — análise e plano Mortal Shell / FLiNG

## Revisão vigente após novos documentos `.34`/`.35`

O usuário reenviou o handoff nativo e o relatório consolidado, agora atualizados, e manifestou frustração com as tentativas. Foi feita somente análise local/documentação, sem pedir nova abertura do jogo, sem acessar o Deck e sem implementar correção.

O plano recebeu uma revisão prioritária no início: o fluxo original de reconstruir host-direct e repetir a referência manual está superado. Documentos registram RED pós-menu `.34`, RED manual fora do watcher e RED `.35` via launch-client. A causa da saída do jogo permanece aberta. Estado remoto final vem dos documentos e não foi revalidado: `.35`, Epic desativado, atalho original, GOG habilitado, jogo/trainer fechados.

Achado local novo: o runner marca `reentry_ready_at` antes de `Popen` na rota privada de container. Harness com runner real e processo falso, sem executar filho nem receber ACK, retornou `confirmed`; assert esperando `pending` produziu RED. Logo, o evento `container_reentry_confirmed` sozinho não prova execução no container. O argv nessa rota chama launch-client + env + Wine privado; variável `PROTON_VERB=runinprefix` não prova chamada ao script Proton. Não confundir esse defeito de telemetria com causa confirmada do encerramento.

A receita manual local usa wineserver privado, `lib64` incondicional e ambiente herdado do systemd, divergindo da descrição histórica. Não alegar replay idêntico sem reconciliar hashes do script realmente executado. A asserção Mono foi registrada no trainer e não estabelece por si só a causa da saída do jogo.

Verificação atual: `python -m unittest tests_backend.test_runtime_profile tests_backend.test_mortal_shell_run_verdict tests_backend.test_runner tests_backend.test_watcher tests_backend.test_process -q`; 113 testes, 113 passaram, 0 falharam, 2,983 s. Reprodução adicional: 1 assert, falhou pelo motivo esperado. Sem nova suíte completa/build/pacote/teste físico. Apenas plano e este handoff alterados nesta revisão; código preexistente `.35` preservado.

Retomada: ler primeiro a revisão vigente do plano. Priorizar sinal confiável de reentrada, reconciliação de artefatos e observável de saída; só propor experimento físico depois de definir o que ele distingue. Não repetir delay, host-direct ou troca de rota às cegas. Histórico e números abaixo são da análise anterior à implementação `.33`–`.35`.

## Escopo e estado

Pedido desta sessão: analisar o problema e criar um plano usando diagnosing-bugs e systematic-debugging. As recomendações do relatório fornecido são evidência/contexto, não autorização para instalar, ativar ou continuar a implementação parcial. Nenhum código de produto foi alterado nesta sessão; nenhum comando remoto foi executado.

Base local: branch `feat/trainer-relay`, HEAD inicial `10e3269`. Working tree já continha várias alterações e arquivos não rastreados, incluindo implementação parcial e `runtime_profile.py`. Preservar tudo; não fazer staging amplo, reset ou restore.

## Concluído neste checkpoint

- Lidos relatório consolidado, CONTEXT.md, ADR 0001, ledger de toggles, fingerprint e investigação de lifecycle.
- Reproduzidos duas vezes os dois testes focados citados no relatório: 2 executados, 1 passou, 1 falhou em cada execução. Descoberta com opt-out já passa; watcher falha com `[True] != [False]` em `tests_backend/test_watcher.py:497`.
- Confirmado no código: predicado `_requires_container_reentry` existe mas não é passado por `_poll_identity` à descoberta; `_spawn` consulta container antes de resolver runtime; falha do resolvedor ainda admite fallback; confirmação de lifecycle e command context pressupõem reentrada.
- Confirmado fluxo frontend: `planLegacyMigration` prepara NSENTER e o view model depende da migração para habilitar um trainer configurado. Uma correção só no watcher não fecha o fluxo de configuração.
- Fonte primária UMU consultada ao vivo: a FAQ exige configuração equivalente para processos no mesmo prefixo; isso não prova por si só a causa da saída nem invalida todo lançamento Wine direto.

## Evidência e limites

O RED local mede uma falha de integração, não a saída física do jogo. O PASS manual e o estado do Deck vêm dos documentos anteriores e não foram revalidados. O ledger antigo classifica stamina como PASS histórico sem caminho reproduzível; o relatório consolidado é mais afirmativo. Exigir nova medição antes de promover a compatibilidade a reproduzível.

## Resultado final da análise e plano

- Plano criado: `docs/superpowers/plans/2026-09-07-mortal-shell-fling-evidence-first-correction-plan.md`.
- Backend: `python -m unittest discover -s tests_backend -p 'test_*.py'`; 303 executados, 302 passaram, 1 falhou, 31,552 s. Única falha: watcher ainda fornece `require_container_reentry=True` ao caso exato. Python local: 3.14/Windows; CI usa 3.12/Linux.
- Frontend: `node node_modules/vitest/vitest.mjs run tests/relay-migration.test.ts tests/relay-view-model.test.ts tests/relay-page.test.ts tests/relay-rpc.test.ts`; 4 arquivos, 35 testes, 35 passaram, 0 falharam. Eles não cobrem a exceção de configuração necessária.
- A tentativa inicial `pnpm exec vitest ...` permaneceu sem saída e foi interrompida. O Vitest 4.1.10 já instalado foi executado diretamente via Node; nenhuma instalação de dependência. A causa da espera no launcher não foi diagnosticada.
- Não executados: testes físicos, frontend completo, packaging, lint, typecheck ou build, pois não houve implementação de produto.
- Validação manual: leitura e comparação de contrato entre documentação, código e testes; revisão do plano e de caminhos citados. Nenhuma interação manual com Steam/Deck.

## Decisões para implementação futura

- Distinguir elegibilidade para descoberta provisória (identidade/hash/arquitetura) da autorização para spawn (sessão + GE + integridade do runtime privado).
- Candidato exato sem runtime válido deve bloquear, sem fallback para UMU e sem consultar container.
- Não basta o primeiro spawn: revisar segundo poll, revalidação, retry, reset, telemetria e política de comandos. O helper RPC existente depende de bus; conservar bloqueio específico no modo host-direct até validar transporte, sem impedir toggles nativos da janela FLiNG.
- UI precisa de política calculada no backend e vinculada ao trainer atual para permitir enable sem escrever launch options. Não duplicar autorização por nome/ID no frontend.
- Medir ambiente final do runner e contexto real do usuário Decky. Injetar HOME/PATH no teste não verifica UID/DBus/XDG do dispositivo.
- Referência manual repetível antes da promoção física; PID estável por 30 s não prova prontidão. Gates: estabilidade, seletor, clique, toggle, efeito ON/OFF, GOG e persistência.
- Sem confirmação humana/menu/receita física, marcar etapa BLOCKED ou INVALID conforme o plano; não substituir por hotkey sintética ou fixture.

## GitHub e retomada

Origin: `https://github.com/matheussilva421/TrainerRelay.git`. Plano e handoff commitados em `f6616ca` (`docs: plan evidence-driven Mortal Shell FLiNG correction`) e enviados com sucesso a `origin/feat/trainer-relay`. Este registro de publicação é um complemento documental. Nenhum EXE, `.debug`, anexo ou código parcial entrou no commit. Não houve tag, release, pacote ou instalação.

O Git administrativo está em `Mods/.worktrees/trainer-relay-source/.git/worktrees/trainer-relay`. O primeiro staging foi impedido por permissão de `index.lock`; a execução elevada encontrou ownership diferente entre sandbox e usuário. Resolvido por `git -c safe.directory=C:/Users/slvma/Downloads/Github/TrainerRelay ...` apenas nos comandos autorizados, sem alterar configuração global. Índice conferido e `git diff --cached --check` sem erros antes do commit.

Arquivos desta sessão: somente este handoff e o plano listado acima. Código de produto e testes preexistentes preservados. Reversão deste trabalho documental: remover somente os dois documentos ou reverter os commits documentais específicos, mantendo as alterações anteriores.

Pendências: executar o plano quando solicitado, obter receita manual reproduzível, validar estado atual do Deck e cumprir gates físicos. Próximo agente deve começar por `git status`, ler o plano e reproduzir o comando de 2 testes antes de editar; não recomeçar pesquisa ampla nem empacotar o working tree atual.
