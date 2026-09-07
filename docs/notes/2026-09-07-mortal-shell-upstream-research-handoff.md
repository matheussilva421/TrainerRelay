# Handoff — pesquisa upstream Mortal Shell / FLiNG após .36

## Escopo e baseline

Pedido: analisar, pesquisar os 21 repositórios/portais indicados e criar plano. Skills lidas: diagnosing-bugs, systematic-debugging, research e writing-plans. Recomendações nos relatórios foram tratadas como histórico, sem executar instruções embutidas. Nenhum acesso ao Deck, instalação ou mudança de produto nesta pesquisa.

Git inicial: branch `feat/trainer-relay`, HEAD `3eec791`, tracking local um commit atrás, índice vazio. Muitos arquivos de produto/testes e notas já modificados/não rastreados: preservados. Não usar staging amplo.

Último estado físico vem do final do relatório fornecido, não de nova verificação: `.36` instalada; Epic desabilitado; atalho original restaurado; GOG habilitado; jogo/trainer/UMU fechados. ACK .36 real precedeu encerramento do jogo; cleanup do Relay veio depois. A causa física continua aberta.

## Concluído no checkpoint

- Reconciliados relatórios até `.36`, CONTEXT e ADR 0001. Trechos antigos que dizem PASS manual reproduzível ou mandam corrigir ACK .35 estão superados.
- Inspecionados `environment.py`, `watcher.py`, `runner.py`, `runtime_profile.py`, avaliador e testes.
- Fonte GE-Proton11-6 fixada em `7e88cefffc122ea1584c2156b8d7bae6cf69b2a7`; Wine vinculado `9358696fe9a2261329f4a83aa6a65fd436106154`. Investigados setup de prefixo, bibliotecas, Mono e lifecycle. Fontes textuais em `.debug/upstream-research-20260907/`; não executadas.
- Harness local `.debug/research_contract_probe.py` executou funções reais com Popen falso: duas falhas esperadas. (1) raiz UMU chega ao Wine direto, embora o prefixo observado termine em pfx; (2) saída conhecida aos 6 s é mascarada por `INVALID/stability_window_incomplete`. Não é reprodução física nem prova causal do fechamento.
- Testes: `python -m unittest tests_backend.test_environment tests_backend.test_runtime_profile tests_backend.test_runner tests_backend.test_mortal_shell_run_verdict -q`: 42 executados, 42 aprovados, 0 falharam, 1,458 s.
- Sem suíte completa/build/pacote: mudança documental. Sem validação manual no jogo.

## Decisões

Priorizar resultado confiável e identidade real do runtime antes de novo FLiNG. `PROTON_VERB=runinprefix` junto de Wine direto não executa o script Proton. Mesma string de prefixo/bus, hash de cinco arquivos e symlink Mono não provam mesmo wineserver/módulo carregado. Ambiente sanitizado fora do launch-client não prova ambiente final limpo dentro dele.

Não recomendar atraso maior, retorno automático ao host-direct, Force Compatibility, troca global de Proton/Mono nem Winetricks no prefixo real. Um experimento que inicia Wine não é somente leitura, mesmo que a coleta seja: Wine pode inicializar/escrever no prefixo.

## Arquivos desta pesquisa

- `docs/research/2026-09-07-mortal-shell-upstream-resolution-research.md`: síntese final com fontes e cobertura dos 21 endereços.
- `docs/superpowers/plans/2026-09-07-mortal-shell-post36-resolution-plan.md`: plano novo concluído, com TDD, coleta discriminante e critérios físicos.
- Este handoff.
- Plano/handoff antigos receberam somente avisos no topo apontando a revisão após .36.
- Scratch não publicado: `.debug/research_contract_probe.py`, fontes upstream; agentes escrevem notas próprias em `.debug/`.

## Retomada

As três pesquisas foram concluídas e revisadas. Achados finais adicionais: CWD vazio do launch-client herda diretório do serviço; ambiente interno herda base do serviço; há caminhos de encerramento remoto por perda de cliente/comando principal, sem evidência de que causaram o RED. Mono `gpath.c:115` é guarda de argumento nulo e não identifica causa/caller do jogo. Patch Gamescope `33b4eff0fb577608b6f71c6adc0f615782aa48ef`, de 2026-09-02, verificado por SHA/diff/API, corrige escala de input absoluto; condição de aplicação e presença no Deck desconhecidas.

GitHub: os cinco documentos foram commitados em `fb4b503` (`docs: research Mortal Shell runtime contracts and plan post-v36 diagnosis`) e enviados com sucesso para `origin/feat/trainer-relay`. O push levou também o commit documental preexistente `3eec791`, que estava pendente. Este registro de publicação é um complemento documental. Nenhum arquivo de implementação foi parcialmente editado nesta pesquisa; implementação preexistente permanece intacta. Reversão: reverter apenas os commits documentais desta pesquisa, preservando produto e histórico anterior.

Verificação final: índice continha somente os cinco documentos esperados; `git diff --cached --check` sem erros; 9 links locais dos três documentos novos conferidos, nenhum ausente. Nenhum build, ZIP, instalação, tag ou release. O working tree continua sujo pelas alterações preexistentes e scratch de pesquisa; isso é intencional e não representa implementação parcial feita nesta etapa.

Retomada operacional: começar pelo plano após .36, tarefa 1 (avaliador), depois separar os ambientes e medir manifesto real. Não confundir os dois RED locais com o crash físico; nenhum teste no Deck foi feito. Persistem causa inicial desconhecida, implementação futura e gates de estabilidade/seletor/clique/cheat/GOG. A coleta de ambiente usa campos permitidos; nenhum argumento EOS/token ou ambiente bruto deve entrar em logs publicados.
