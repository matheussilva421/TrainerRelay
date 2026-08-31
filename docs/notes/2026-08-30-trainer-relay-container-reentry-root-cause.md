# Trainer Relay — causa raiz do `container_reentry_probe_failed` e plano definitivo

Branch: `codex/trainer-relay-third-model` · Worktree: `.worktrees/trainer-relay-third`
Base analisada: `8e6b6fd` (`fix: resolve host D-Bus session bus for container re-entry preflight`)

Documento **somente de análise**. Nenhum arquivo de código foi criado ou alterado
para produzir este relatório.

---

## 1. Escopo e método

Aplicado o ciclo de depuração sistemática (causa raiz antes de qualquer correção),
com verificação em **fonte primária** — não em memória nem em inferência sobre o
comportamento do runtime. Foram lidos diretamente:

- `umu-launcher/umu/umu_run.py` e `umu/umu_runtime.py` (implementação de referência
  do re-entry);
- `steam-runtime-tools/bin/launch-client.c` e `bin/launch-client.md` (semântica exata
  de `--list`, códigos de saída);
- `steam-runtime-tools/pressure-vessel/flatpak-run.c`, `wrap.c`, `wrap-setup.c`
  (como o container trata D-Bus, `XDG_RUNTIME_DIR`, `PATH`);
- `decky-loader/backend/decky_loader/plugin/sandboxed_plugin.py` (ambiente real do
  processo de backend do plugin).

---

## 2. Sintoma físico (`.17`)

Do export `TrainerRelay-diagnostics-20260830-233641.txt`:

- 462 observações aceitas/revalidadas do processo real do BioShock 2 (GOG,
  GE-Proton 11-6, PID `79033`), **com a flag de re-entry herdada presente**;
- 462 rejeições `container_reentry_probe_failed`;
- zero `trainer_spawned`, zero `trainer_running`;
- `steam-runtime-launch-client --list` retornando **não-zero em ~10 ms**;
- ~7,5 MiB de diagnóstico em ~8 minutos (um preflight por tick).

Fato importante já provado pela própria evidência: como o erro foi
`probe_failed` e **não** `container_reentry_unsupported`, todos os gates
anteriores passaram no aparelho real. Ou seja, no Deck físico o plugin **já
resolvia corretamente**: `WINEPREFIX`, `PROTONPATH`, a variante do runtime lida
do `toolmanifest.vdf`, a raiz do UMU e o caminho do binário
`steam-runtime-launch-client` (que existia e era executável). O único ponto que
falhava era a execução do `--list`.

---

## 3. Cadeia causal — provada

### 3.1 `--list` só retorna não-zero se o barramento de sessão não for alcançado

`bin/launch-client.c`, função `list_servers()`:

- chama `g_bus_get_sync(G_BUS_TYPE_SESSION, ...)`; se falhar, prefixa o erro com
  "Can't find session bus" e retorna `LAUNCH_EX_FAILED`;
- em seguida chama `ListNames` e `ListActivatableNames`; se qualquer uma falhar,
  retorna `LAUNCH_EX_FAILED`;
- caso contrário imprime uma linha `--bus-name=<nome>` por serviço encontrado e
  **retorna 0 — inclusive quando a lista está vazia**.

Consequência direta e decisiva:

> `--list` com código de saída não-zero significa **"não consegui falar com o
> barramento de sessão"**. Nunca significa "nenhum serviço encontrado".

`bin/launch-client.md` (EXIT STATUS) confirma: `125` = "Invalid arguments were
given, or steam-runtime-launch-client failed to start".

### 3.2 Dentro do pressure-vessel, `DBUS_SESSION_BUS_ADDRESS` aponta para um caminho que não existe no host

`pressure-vessel/flatpak-run.c`, `flatpak_run_add_session_dbus_args()`:

- `sandbox_socket_path  = "/run/pressure-vessel/bus"`
- `sandbox_dbus_address = "unix:path=/run/pressure-vessel/bus"`
- faz `--ro-bind <socket real da sessão do host> /run/pressure-vessel/bus`
- faz `flatpak_bwrap_set_env(app_bwrap, "DBUS_SESSION_BUS_ADDRESS", sandbox_dbus_address, TRUE)`

`pressure-vessel/wrap-setup.c` chama essa função no caminho normal de
compartilhamento. Portanto **todo processo dentro do container do jogo carrega
`DBUS_SESSION_BUS_ADDRESS=unix:path=/run/pressure-vessel/bus`**, e esse caminho
**não existe no sistema de arquivos do host**.

### 3.3 O `.17` copiava exatamente essa variável para o preflight

`DBUS_SESSION_BUS_ADDRESS` está em `EXACT_KEYS` de
[`trainer_relay/environment.py`](trainer_relay/environment.py). O ambiente
sanitizado é copiado de um descendente Windows **de dentro** do pressure-vessel.
O `.17` executava o `--list` no host com esse ambiente.

**Cadeia fechada:** endereço aponta para `/run/pressure-vessel/bus` → o caminho
não existe no host → `g_bus_get_sync` falha imediatamente → `LAUNCH_EX_FAILED`
→ retorno não-zero em ~10 ms → `container_reentry_probe_failed`. Os ~10 ms
observados são exatamente o custo de um `connect()` que falha em caminho
inexistente, sem I/O de rede nem timeout.

**A causa raiz do `.17` está confirmada. Não é hipótese.**

### 3.4 O serviço realmente vive no barramento do host

O mesmo `--ro-bind` acima prova que `/run/pressure-vessel/bus` é o **mesmo
socket** do barramento de sessão do host, apenas remontado em outro caminho. Não
há um segundo daemon D-Bus dentro do container. Logo o nome
`com.steampowered.App<md5>` registrado pelo `steam-runtime-launcher-service`
**é visível a partir do host**. Os exemplos do manual do
`steam-runtime-launch-client` mostram exatamente isso: o usuário roda `--list`
de um shell comum do host e vê `--bus-name=com.steampowered.App312990`.

Isso valida a direção da correção `8e6b6fd`.

---

## 4. Avaliação da correção já commitada (`8e6b6fd`)

A correção resolve candidatos de barramento **host** em
[`trainer_relay/container_reentry.py`](trainer_relay/container_reentry.py),
nesta ordem:

1. `DBUS_SESSION_BUS_ADDRESS` do ambiente do próprio plugin — `host_env`
2. `unix:path=$XDG_RUNTIME_DIR/bus` — `xdg_runtime_dir`
3. `unix:path=/run/user/<os.getuid()>/bus` — `uid_default`

**Está correta e ataca a causa raiz certa.** Porém há um fato que precisa ficar
explícito, porque muda o risco:

> No Steam Deck real, os candidatos 1 e 2 **não existem**. A correção depende
> inteiramente do candidato 3.

Prova, em `decky-loader/backend/decky_loader/plugin/sandboxed_plugin.py`
(`initialize`): o backend do plugin é bifurcado do serviço do Decky Loader (que
roda como root via systemd de **sistema**) e então executa `setgid`/`setuid` para
`HOST_USER`. Logo em seguida o Decky define apenas `HOME`, `USER` e as variáveis
`DECKY_*`. **Ele nunca define `XDG_RUNTIME_DIR` nem `DBUS_SESSION_BUS_ADDRESS`**,
e um serviço systemd de sistema não os herda.

Como `plugin.json` traz `"flags": []`, o `setuid` vai para o usuário do host
(`deck`, uid 1000) e não para root. Portanto:

- candidato 1: ausente;
- candidato 2: ausente;
- candidato 3: `unix:path=/run/user/1000/bus` — **existe, e o uid real 1000
  corresponde ao dono do socket**, então a conexão é permitida.

Ou seja: a correção deve funcionar, mas por uma única via. Isso é frágil e,
principalmente, **mal instrumentado**: se o candidato 3 falhar, a evidência
atual (`returncode` + `detail` truncado) não distingue "socket não existe" de
"socket existe mas recusou a conexão".

---

## 5. O que ainda pode quebrar depois dessa correção — riscos ranqueados

### R1 — ALTO · `HOME` do container decide qual raiz UMU o sidecar usa

`build_sanitized_environment` mantém `HOME` copiado do processo do jogo. O
sidecar `umu-run` roda **no host** com esse `HOME`.

O problema é a **assimetria**: o preflight do plugin resolve a raiz do UMU a
partir de `self._home` (o `HOME` do plugin), enquanto o `umu-run` do sidecar
resolve `UMU_LOCAL` a partir do `XDG_DATA_HOME`/`HOME` que ele recebeu. Se o
pressure-vessel tiver usado home privado — `wrap.c` monta
`~/.var/app/com.steampowered.App<id>` quando o home não é compartilhado — o
plugin valida um `steam-runtime-launch-client` e o `umu-run` procura outro.

Resultado possível: preflight **verde** e, logo depois, o `umu-run` do sidecar
não encontra o bus e **abre um container novo** — que é exatamente o modo de
falha do `.16` (trainer sobe e morre). Preflight verde não garante re-entry.

### R2 — ALTO · Preflight e sidecar podem discordar

O preflight prova uma coisa; quem realmente decide o re-entry é o `build_command`
do `umu-run` do sidecar (`umu_run.py`, linhas ~380-408), que refaz o `--list` por
conta própria. Se o ambiente do sidecar divergir do ambiente do preflight em
**qualquer** variável que afete a resolução do bus (`DBUS_SESSION_BUS_ADDRESS`,
`HOME`, `XDG_DATA_HOME`, `UMU_FOLDERS_PATH`, `WINEPREFIX`), o umu **falha em
silêncio para um container novo** — ele não aborta.

Esse é o ponto mais perigoso do sistema inteiro: **a falha do umu é aberta, não
fechada.** O plugin é fail-closed; o umu não é.

### R3 — MÉDIO · Bus name recalculado em vez de lido

O plugin recalcula `md5(str(Path(WINEPREFIX).expanduser().resolve(strict=False)))`.
O umu calcula o mesmo (`umu_run.py` linhas 213 e 302), então **hoje bate**.
Mas há duas fontes de divergência silenciosa:

- o umu calcula no **host** antes de entrar no container; o plugin calcula
  resolvendo, no host, uma string vinda de **dentro** do container;
- `resolve()` segue symlinks; prefixo em cartão SD ou caminho com link pode
  divergir.

O ambiente do jogo **já contém `STEAM_COMPAT_APP_ID`** (o umu escreve em
`os.environ`, `umu_run.py` linha 305, e o pressure-vessel não o remove — não
consta da tabela `default_exports` de variáveis limpas em `flatpak-run.c`). Ler
o valor pronto elimina a classe inteira de divergência.

### R4 — MÉDIO · Não existe sinal direto de "o serviço nem foi publicado"

O `steam-runtime-launcher-service` é **opt-in**. O umu só define
`STEAM_COMPAT_LAUNCHER_SERVICE` quando `UMU_CONTAINER_NSENTER == "1"`
(`umu_run.py` linhas 1034-1035); o manual do Valve documenta o mesmo padrão
(`STEAM_COMPAT_LAUNCHER_SERVICE=proton %command%`). Sem isso, **nenhum**
`com.steampowered.App*` existe.

O plugin já rejeita jogo sem `UMU_CONTAINER_NSENTER=1`, o que é um bom *proxy*.
Mas o sinal direto — `STEAM_COMPAT_LAUNCHER_SERVICE` presente no ambiente
capturado — não é checado. Sem ele, o cenário "usuário abriu o jogo antes de
preparar o atalho" chega ao usuário como `container_reentry_bus_missing`, um
código que não diz o que fazer.

### R5 — BAIXO/MÉDIO · `PATH` do container no sidecar do host

`OwnedTrainerRunner.spawn` passa `env=spawn_environment` explicitamente, sem
herdar o ambiente do host. O `PATH` copiado é o do container (o pressure-vessel
força um `PATH` próprio — ver `default_exports` em `flatpak-run.c`). O `umu-run`
é invocado por caminho absoluto, então não quebra de imediato, mas qualquer
subprocesso do umu que dependa de `PATH` do host fica exposto.

### R6 — BAIXO · `XDG_RUNTIME_DIR` — risco descartado por evidência

Confirmado em `flatpak-run.c`: "We always use /run/user/UID, even if the user's
XDG_RUNTIME_DIR outside the sandbox is somewhere else". Dentro do container o
valor é `/run/user/1000`, **idêntico** ao do host no Deck. Não é fonte de erro.

### R7 — BAIXO · Latch e corrida de registro

O latch por `SessionIdentity` está correto e elimina o loop de 462 tentativas.
O `steam-runtime-launcher-service` sobe junto com o container, antes dos
processos Wine que o plugin usa para aceitar a sessão, então não há corrida
real. Os 5 retries de 1 s já cobrem folga.

---

## 6. Plano definitivo — o que fazer para funcionar de uma vez por todas

Ordenado por **razão de valor sobre risco**. Cada item é independente e
testável isoladamente por TDD.

### P1 — Eliminar a assimetria de ambiente entre preflight e sidecar (resolve R1 + R2)

O princípio: **o preflight e o `umu-run` do sidecar precisam responder à mesma
pergunta com os mesmos dados.**

- Executar o preflight com o **ambiente do host do plugin**, não com o ambiente
  sanitizado do jogo. O `--list` não precisa de nada do jogo: `list_servers()`
  usa apenas o barramento de sessão. É exatamente o que o umu faz — ele chama
  `Popen([exe_path, "--list"])` **sem argumento `env`**, herdando o próprio
  ambiente.
- No ambiente do **sidecar**, substituir por valores do host as três variáveis
  que decidem a resolução do runtime e do bus: `HOME`, `XDG_DATA_HOME` (quando
  presente) e `PATH`. Manter `WINEPREFIX`/`STEAM_COMPAT_DATA_PATH` ancorados na
  raiz de compatdata já validada, como hoje.
- Manter a injeção do `DBUS_SESSION_BUS_ADDRESS` resolvido (já feita em
  `8e6b6fd`) — ela é o que faz o probe interno do umu concordar com o preflight.

Seams de teste: dado um ambiente de jogo com `HOME` privado
(`~/.var/app/com.steampowered.App<id>`), o ambiente do sidecar deve conter o
`HOME` do host; e o preflight não deve consumir nenhuma variável do jogo além do
prefixo/Proton usados para localizar o binário.

### P2 — Ler `STEAM_COMPAT_APP_ID` em vez de recalcular o MD5 (resolve R3)

Usar o valor presente no ambiente capturado do jogo e montar
`com.steampowered.App<valor>`. Manter o cálculo MD5 apenas como fallback quando
a variável estiver ausente, e **registrar qual caminho foi usado** no evento de
diagnóstico. Se ambos existirem e divergirem, isso é um sinal de erro de
primeira ordem e deve falhar fechado com código próprio.

### P3 — Classificar "serviço não publicado" com código próprio e acionável (resolve R4)

Antes de qualquer D-Bus, checar `STEAM_COMPAT_LAUNCHER_SERVICE` no ambiente
capturado do jogo. Ausente ⇒ re-entry é **estruturalmente impossível** nesta
sessão; emitir um código distinto (por exemplo `container_reentry_service_absent`)
cuja mensagem instrui: preparar o atalho e **reiniciar o jogo**. Isso troca uma
falha opaca por uma instrução que o usuário consegue executar.

### P4 — Instrumentar a resolução do barramento (fecha a lacuna do candidato único)

Para cada candidato, registrar de forma limitada: origem (`host_env` /
`xdg_runtime_dir` / `uid_default`), se o caminho **existe** e é socket, o `uid`
efetivo usado, e o `returncode`. Hoje, se o candidato 3 falhar, a evidência não
distingue "socket ausente" de "conexão recusada". Adicionar um quarto candidato
derivado do `DECKY_USER_HOME`/`DECKY_USER` também é barato e cobre um Deck com
uid diferente de 1000.

### P5 — Encerrar a ambiguidade de fail-open do umu (resolve o resíduo de R2)

Mesmo com P1, o `umu-run` do sidecar pode decidir sozinho abrir um container
novo. Como o plugin já drena e guarda um tail sanitizado do stdout/stderr do umu
com `UMU_LOG=info`, e o umu emite as linhas
`Re-entering container through bus '<nome>'` em sucesso e
`Failed to find bus name <nome> (retry N)` em falha (`umu_run.py`, linhas
405 e 407), o plugin pode **confirmar o re-entry a partir da saída do próprio
umu** em vez de assumir. Sem essa confirmação, tratar como falha e não declarar
`trainer_running`.

Esta é a diferença entre "o preflight passou" e "o trainer está de fato dentro
do container do jogo" — e é o que evita repetir o falso positivo do `.16`.

### P6 — Sem alterações necessárias

Não mexer em: derivação da variante do runtime (`_RUNTIME_VARIANTS` bate
exatamente com `RUNTIME_VERSIONS` do umu — `1391110`→`steamrt2`,
`1628350`→`steamrt3`, `4183110`→`steamrt4`, `4185400`→`steamrt4-arm64`, e
`UmuRuntime.path` é `UMU_LOCAL/<variant>`, idêntico ao que o plugin monta);
precedência `UMU_FOLDERS_PATH` → `XDG_DATA_HOME`; comparação exata da linha
`--bus-name=`; latch de preflight; fronteira fail-closed. Tudo isso já está
alinhado com a implementação de referência e comprovado pela evidência física.

---

## 7. Roteiro de validação física (obrigatório antes de qualquer alegação de correção)

1. Gerar build a partir desta branch, com versão que não colida com o trabalho
   `.18` da segunda worktree. Instalar no Deck com Diagnostics ligado.
2. Preparar o atalho GOG (BioShock 2) e **reiniciar o jogo** — sessão iniciada
   antes da preparação nunca terá o serviço publicado.
3. Antes de abrir o overlay, no Desktop Mode, executar como usuário `deck` o
   `--list` do runtime correspondente e confirmar que aparece
   `--bus-name=com.steampowered.App<id>`. Se **não** aparecer, o problema está na
   publicação do serviço (P3), não no barramento.
4. Exportar o TXT e verificar a sequência esperada:
   `container_reentry_verified` → `trainer_spawned` → `trainer_running`,
   com `dbus_source` presente no evento verificado.
5. Confirmar que `dbus_source` é `uid_default` — se for, a leitura da seção 4
   está certa e os candidatos 1/2 realmente não existem sob o Decky.
6. Confirmar no tail do UMU a linha `Re-entering container through bus`. **Sem
   ela, o trainer subiu em container novo** e o resultado é falso positivo,
   mesmo com o trainer aparentemente rodando.
7. Repetir com um título Epic. Promoção a estável permanece proibida até GOG e
   Epic passarem fisicamente.

---

## 8. Matriz de diagnóstico

| Código | Significado provado | Ação |
|---|---|---|
| `container_reentry_unsupported` | Prefixo/Proton/variante/binário não resolvidos no host | Verificar PROTONPATH e a instalação do runtime UMU |
| `container_reentry_probe_failed` + `returncode` não-zero | `--list` não alcançou barramento de sessão algum | Aplicar P4; conferir `/run/user/<uid>/bus` e o uid efetivo |
| `container_reentry_probe_failed` + `no_host_session_bus` | Nenhum candidato pôde ser construído | Decky sem `XDG_RUNTIME_DIR` e `getuid` indisponível; aplicar P4 |
| `container_reentry_bus_missing` | Barramento alcançado, `--list` retornou 0, mas sem o bus do prefixo | Serviço não publicado (P3) ou bus name divergente (P2) |
| Preflight verde + trainer que sobe e morre | Sidecar abriu container novo | R1/R2 — aplicar P1 e confirmar com P5 |

---

## 9. Conclusão

A correção `8e6b6fd` ataca a causa raiz **correta e comprovada** do `.17`. Ela
não é suficiente para "funcionar de uma vez por todas" por três motivos
concretos: depende de um único candidato de barramento sem instrumentação que o
distinga em caso de falha (P4); mantém uma assimetria de `HOME`/`PATH` entre
preflight e sidecar que pode produzir preflight verde com re-entry falso (P1);
e não confirma, a partir da saída do próprio umu, que o re-entry realmente
ocorreu (P5).

Com P1 a P5 aplicados, todo modo de falha conhecido passa a ter um código
distinto e uma ação correspondente, e o sistema deixa de depender de um caminho
não observado.

---

## 10. Fontes primárias

- [umu-launcher — `umu/umu_run.py`](https://github.com/Open-Wine-Components/umu-launcher/blob/main/umu/umu_run.py) — `set_env` (`STEAM_COMPAT_APP_ID`), `build_command` (probe de re-entry), `STEAM_COMPAT_LAUNCHER_SERVICE`
- [umu-launcher — `umu/umu_runtime.py`](https://github.com/Open-Wine-Components/umu-launcher/blob/main/umu/umu_runtime.py) — `RUNTIME_VERSIONS`, `UmuRuntime.path`, `CompatLayer.launch_client`/`launcher_service`
- [umu-launcher — `umu/umu_consts.py`](https://github.com/Open-Wine-Components/umu-launcher/blob/main/umu/umu_consts.py) — `UMU_LOCAL`, precedência `UMU_FOLDERS_PATH`/`XDG_DATA_HOME`
- [Open Wine Components](https://github.com/Open-Wine-Components)
- steam-runtime-tools — `bin/launch-client.c` (`list_servers`), `bin/launch-client.md` (SYNOPSIS, `--list`, EXIT STATUS, EXAMPLES)
- steam-runtime-tools — `pressure-vessel/flatpak-run.c` (`flatpak_run_add_session_dbus_args`, `default_exports`), `pressure-vessel/wrap.c`, `pressure-vessel/wrap-setup.c`
- [Valve Software](https://github.com/ValveSoftware) · [Proton](https://github.com/ValveSoftware/Proton) · [GE-Proton](https://github.com/GloriousEggroll/proton-ge-custom)
- [decky-loader — `sandboxed_plugin.py`](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/plugin/sandboxed_plugin.py) — `setuid(HOST_USER)`, variáveis exportadas ao backend
- [UniFiDeck](https://github.com/mubaraknumann/unifideck)
