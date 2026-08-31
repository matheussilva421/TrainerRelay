# Trainer Relay — segunda worktree

## Estado

- Criada para permitir trabalho paralelo de um segundo modelo de IA no mesmo
  problema físico do Trainer Relay.
- Caminho: `C:\Users\slvma\Downloads\Github\Mods\.worktrees\trainer-relay-second`.
- Branch: `codex/trainer-relay-second-model`.
- Base: `146b7c3` (`docs: record experimental 17 physical failure`).
- Fork/remotes: `origin` aponta para `matheussilva421/TrainerRelay`; `upstream`
  aponta para `SheffeyG/CheatDeck`.

## Isolamento

- A worktree principal `Mods`/`main` não foi alterada.
- A worktree existente `trainer-relay`, que contém alterações não commitadas da
  investigação da versão `.18`, não foi alterada.
- Esta worktree começa sem alterações de código da investigação concorrente.

## Problema reproduzido

O diagnóstico físico `.17` aceitou o BioShock 2 GOG, mas teve 462 falhas
`container_reentry_probe_failed`, sem `trainer_spawned` ou `trainer_running`.
O próximo trabalho deve investigar o contexto host-side do D-Bus usado pelo
`steam-runtime-launch-client --list`, registrar stderr/return code sanitizados,
e evitar repetir o mesmo preflight a cada segundo para a mesma sessão inválida.

## Validação inicial

- `python -m unittest discover -s tests_backend -p "test_*.py"`
- Resultado: 124 testes executados, 124 aprovados, 0 falhas.
- `pnpm --version` não respondeu no ambiente Windows e foi interrompido; não
  houve alteração de arquivos.

## Retomada

Trabalhar somente nesta worktree/branch. Antes de editar, revisar o diagnóstico
em `docs/notes/2026-08-29-trainer-relay-handoff.md`, criar testes vermelhos
para a resolução do D-Bus host e o latch de preflight, e preservar a fronteira
fail-closed: falhas do trainer nunca encerram o jogo.
