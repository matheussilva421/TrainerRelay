# Trainer Relay — terceira worktree

## Estado

- Terceira worktree criada para investigar, de forma isolada, a mesma falha
  física do `experimental.17`: `container_reentry_probe_failed` com zero
  `trainer_spawned` e zero `trainer_running`.
- Caminho: `C:\Users\slvma\Downloads\Github\Mods\.worktrees\trainer-relay-third`.
- Branch: `codex/trainer-relay-third-model`.
- Base: `8a58fb8` (`docs: hand off third trainer relay worktree`).
- `origin` = `https://github.com/matheussilva421/TrainerRelay.git`.
- Isolamento preservado: `Mods/main`, `trainer-relay-source`, `trainer-relay` e
  `trainer-relay-second` não foram alterados. Nenhum `reset`, `checkout`
  destrutivo ou `clean` foi executado.

## Diagnóstico (evidência capturada, sem novo hardware)

O export físico `TrainerRelay-diagnostics-20260830-233641.txt` do `.17` mostrou
462 rejeições `container_reentry_probe_failed`, nenhuma `trainer_spawned`. O
`steam-runtime-launch-client --list` retornava não-zero em ~10 ms.

Causa raiz confirmada por leitura de código: o `ContainerReentryProbe` executava
o preflight com o ambiente sanitizado **copiado de um descendente Windows dentro
do pressure-vessel**. Esse ambiente carrega `DBUS_SESSION_BUS_ADDRESS` apontando
para o barramento D-Bus interno do container do jogo, que o plugin (executado
pelo Decky como usuário host `deck`) não alcança. O serviço launcher que o
`UMU_CONTAINER_NSENTER=1` expõe fica registrado no barramento de sessão **do
host** (`/run/user/<uid>/bus`), não no barramento interno. Logo o `--list`
falhava sempre, e o watcher repetia o mesmo preflight a cada segundo (~7,5 MiB
de diagnósticos em ~8 min).

## Correção implementada (TDD, backend apenas)

Arquivos alterados:

- `trainer_relay/container_reentry.py`
  - Resolve candidatos de barramento **host** independentes das variáveis de
    runtime do jogo, na ordem: `DBUS_SESSION_BUS_ADDRESS` do ambiente do plugin
    (`host_env`), `unix:path=$XDG_RUNTIME_DIR/bus` (`xdg_runtime_dir`) e
    `unix:path=/run/user/<uid>/bus` (`uid_default`).
  - Remove as variáveis D-Bus do jogo (`DBUS_SESSION_BUS_ADDRESS`,
    `DBUS_STARTER_ADDRESS`, `DBUS_STARTER_BUS_TYPE`) antes de sondar e injeta o
    endereço host candidato em cada tentativa.
  - Aceita apenas o candidato cujo `--list` contém o bus MD5 exato do prefixo.
  - `ContainerReentryResolution` agora carrega `dbus_address` e `dbus_source`.
  - Fail-closed com evidência limitada: `ContainerReentryError.evidence` guarda
    `returncode` e um `detail` truncado (≤160) com segredos redigidos
    (`token`/`password`/`secret`/`cookie`/`authorization`/`credential`/`api_key`
    /`access_key`/`private_key`). Sem barramento host → `probe_failed`
    (`no_host_session_bus`); barramentos alcançáveis mas sem o bus →
    `bus_missing`.
- `trainer_relay/watcher.py`
  - Injeta o `dbus_address` resolvido em `safe_environment` antes do
    `runner.spawn`, para que o sidecar re-entre no mesmo serviço launcher.
  - Registra `dbus_source` e a evidência limitada (`probe_returncode`,
    `probe_detail`) nos eventos de diagnóstico.
  - **Latch de preflight**: uma falha `container_reentry_*` é presa ao
    `SessionIdentity` (PID/start-time) atual (`_RelayState.reentry_latch`). O
    watcher não repete o probe a cada tick; só reexecuta em nova sessão ou em
    retry manual. A fronteira fail-closed e o isolamento do jogo permanecem.

## Testes

- `python -m unittest discover -s tests_backend -p "test_*.py"`
  - Antes: 124/124. Depois: **131/131 aprovados, 0 falhas** (7 novos testes).
- `python -m compileall -q main.py trainer_relay tests_backend`: OK.
- Seams cobertos (RED→GREEN observado):
  1. o probe usa o barramento host, nunca o `DBUS_SESSION_BUS_ADDRESS` do jogo;
  2. dado um candidato host inalcançável e outro válido, seleciona o válido;
  3. zero barramentos válidos → fail-closed com evidência sanitizada;
  4. segredos são redigidos da evidência;
  5. o contexto D-Bus resolvido chega ao ambiente do runner;
  6. uma sessão inválida inalterada executa **um** preflight, não um por tick;
  7. retry manual e nova sessão rearmam o latch.
- Frontend não foi tocado (mudança 100% backend); gates de frontend/pnpm não
  executados neste bloco.

## GitHub

- Commit na branch `codex/trainer-relay-third-model`; push e Draft PR abertos.
- Nenhuma tag/release/kit criada: correção é candidata e **não** foi validada
  fisicamente.

## Pendências / próximos passos (obrigatório antes de qualquer alegação de fix)

1. Gerar um novo build/pacote a partir desta branch (bump de versão a combinar
   para não colidir com o trabalho `.18` da segunda worktree) e instalar no
   Steam Deck físico com Diagnostics habilitado.
2. Abrir o atalho GOG BioShock 2, exportar o TXT e confirmar a sequência
   `container_reentry_verified` → `trainer_spawned` → `trainer_running`, com
   `dbus_source` presente no evento verificado.
3. Se o preflight ainda falhar, enviar o código `container_reentry_*` limitado,
   `probe_returncode`/`probe_detail` e o TXT; nenhum trainer deve ter iniciado e
   o jogo deve permanecer isolado.
4. Repetir com um título Epic. Promoção a estável continua proibida até GOG e
   Epic passarem fisicamente.

## Como reverter

`git checkout main -- trainer_relay/container_reentry.py trainer_relay/watcher.py`
e remover os testes adicionados; ou descartar a branch
`codex/trainer-relay-third-model`. As outras worktrees não são afetadas.
