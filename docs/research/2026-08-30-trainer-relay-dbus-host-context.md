# Trainer Relay: Decky host identity and UMU launcher-service D-Bus context

Date: 2026-08-30
Scope: primary-source research only; UniFiDeck `staging` is pinned here to
commit `cb2eeaacff4a8acd3bdd6664851e41227e5e9243`.

## Short answer

With `plugin.json` `flags: []`, a Python Decky backend runs as the Decky
**host user** (normally `deck`, usually UID 1000), in a host process
namespace. It is not a root plugin and it is not automatically inside the
game's Proton/pressure-vessel container. The loader service starts as root,
but Decky's `SandboxedPlugin.initialize()` calls `setgid(HOST_USER)` and
`setuid(HOST_USER)` whenever `root` is absent from `flags`.

UMU 1.4.4's `steam-runtime-launch-client --list` must therefore run with the
**active Deck/Steam host user's session-bus context**: a
`DBUS_SESSION_BUS_ADDRESS` and `XDG_RUNTIME_DIR` pair belonging to the same
host user/session, not an untrusted environment copied from a Wine descendant.
The listing is successful only when it returns the exact same-prefix service
`--bus-name=com.steampowered.App<md5(canonical UMU WINEPREFIX)>`.

## Source comparison

### Decky Loader: identity is host-user, not game-container

- The official release unit has `User=root` and sets `UNPRIVILEGED_PATH` to
  the Decky homebrew folder: [plugin_loader-release.service](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/dist/plugin_loader-release.service#L3-L13).
- `SandboxedPlugin.initialize()` selects `HOST_USER` unless `"root" in
  self.flags`, then calls `setgid()`/`setuid()` before importing `main.py`.
  It also sets `HOME` and `USER` to that selected identity and sets the
  `DECKY_*` variables; it does not create a Proton or pressure-vessel
  namespace: [sandboxed_plugin.py](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/plugin/sandboxed_plugin.py#L51-L84).
- On Linux, `HOST_USER` is the configured/unprivileged Decky user; the source
  resolves it from `UNPRIVILEGED_USER` or the owner of the unprivileged path,
  with `deck` as the final fallback. `setuid(HOST_USER)` uses that user's UID:
  [localplatformlinux.py](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/localplatform/localplatformlinux.py#L33-L47), [setuid/get_unprivileged_user](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/localplatform/localplatformlinux.py#L124-L141) and [user resolution](https://github.com/SteamDeckHomebrew/decky-loader/blob/main/backend/decky_loader/localplatform/localplatformlinux.py#L260-L276).
- The official plugin stub states the same contract: `HOME`/`USER` are
  `/root`/`root` only when the `root` flag is present; otherwise they are the
  user whose home contains Decky, normally `/home/deck`/`deck`:
  [decky.pyi](https://github.com/SteamDeckHomebrew/decky-plugin-template/blob/main/decky.pyi#L22-L55).

Consequences: `flags: []` establishes the backend's host-user identity, but
does not guarantee that its inherited `DBUS_SESSION_BUS_ADDRESS`,
`XDG_RUNTIME_DIR`, `HOME`, or `PATH` describe the running game. Decky changes
some variables after the UID drop; it does not make the service's inherited
D-Bus variables authoritative.

### UMU 1.4.4: the `--list` lookup uses the current UMU process environment

UMU 1.4.4 makes the prefix/service relationship explicit:

1. `set_env()` canonicalizes `WINEPREFIX`, sets
   `STEAM_COMPAT_DATA_PATH` to that same UMU prefix root, and derives
   `STEAM_COMPAT_APP_ID` as the MD5 of the canonical prefix path. It carries
   `UMU_CONTAINER_NSENTER`: [umu_run.py](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_run.py#L192-L301).
2. Before building the command, UMU writes its derived environment into
   `os.environ`. Therefore the `Popen([launch_client, "--list"], ...)` call in
   `build_command()` has no explicit `env=` and inherits that process
   environment: [umu_run.py](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_run.py#L758-L804).
3. With `UMU_CONTAINER_NSENTER=1`, it runs the resolved launch client with
   `--list`, searches stdout for
   `--bus-name=com.steampowered.App<STEAM_COMPAT_APP_ID>`, and only then
   prepends `--bus-name=... --` and changes `PROTON_VERB` to `runinprefix`:
   [umu_run.py](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_run.py#L331-L383).
4. The final environment assignment sets
   `STEAM_COMPAT_LAUNCHER_SERVICE` from the selected Proton layer before the
   command is built: [umu_run.py](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_run.py#L935-L966).
5. UMU's data/runtime location precedence is `UMU_FOLDERS_PATH`, then
   `XDG_DATA_HOME`, then `$HOME/.local/share`; this must be used when finding
   the matching runtime's `steam-runtime-launch-client`:
   [umu_consts.py](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_consts.py#L54-L94).

The important negative behavior is that UMU's five one-second `--list`
attempts are not a fail-closed contract. If the exact bus is not found,
`nsenter` remains empty and UMU returns the ordinary unwrapped Proton command
instead of the same-container command ([build_command](https://github.com/Open-Wine-Components/umu-launcher/blob/1.4.4/umu/umu_run.py#L349-L383)). A caller that requires same-prefix behavior must preflight and fail closed itself.

### Valve Proton and Steam Runtime: separate container boundary, explicit prefix

Valve's Steam Runtime documentation says that Proton uses the Steam container
runtime; this is a distinct runtime layer from the host Linux process:
[Steam Runtime README](https://github.com/ValveSoftware/steam-runtime/blob/master/README.md#L175-L189).

The Proton source shows why the Windows descendant's environment is not the
UMU input contract: Proton's `init_session()` sets its Wine prefix from
`g_compatdata.prefix_dir`, and the `runinprefix` verb invokes Wine directly
with the already-initialized session environment:
[Proton `init_session`](https://github.com/ValveSoftware/Proton/blob/experimental_11.0/proton#L1558-L1560) and [Proton command dispatch](https://github.com/ValveSoftware/Proton/blob/experimental_11.0/proton#L1946-L1978).
The same source also passes its session environment to subprocesses through
`run_proc()` ([Proton `run_proc`](https://github.com/ValveSoftware/Proton/blob/experimental_11.0/proton#L1902-L1905)). This supports using the selected compatdata/prefix contract, not replaying a post-container child environment.

### UniFiDeck `staging`: inherited launch environment, then UMU/Proton transforms

The pinned UniFiDeck staging source builds the UMU environment from
`dict(os.environ)`, then explicitly sets `PROTONPATH`,
`STEAM_COMPAT_DATA_PATH`, and `WINEPREFIX`; it removes
`STEAM_COMPAT_CLIENT_INSTALL_PATH` and sets the initial
`PROTON_VERB=waitforexitandrun`:
[staging `core.py`](https://github.com/mubaraknumann/unifideck/blob/cb2eeaacff4a8acd3bdd6664851e41227e5e9243/py_modules/unifideck/launcher/proton/infrastructure/core.py#L315-L391).

Its headless/subprocess path passes the planned environment explicitly to
`umu-run` with `env=env` and starts a new session/process group:
[staging `umu_runtime.py`](https://github.com/mubaraknumann/unifideck/blob/cb2eeaacff4a8acd3bdd6664851e41227e5e9243/py_modules/unifideck/launcher/proton/infrastructure/umu_runtime.py#L490-L522).
The staging launch-options contract likewise describes environment variables
as inherited by the launcher and then passed to Proton/UMU:
[staging launch options](https://github.com/mubaraknumann/unifideck/blob/cb2eeaacff4a8acd3bdd6664851e41227e5e9243/docs/launch-options.md#L20-L55).

This pattern proves environment propagation, not D-Bus ownership. It contains
no authority that a game descendant's D-Bus address is the host user's
session bus, and no generic same-prefix service discovery. Trainer Relay must
add that boundary explicitly.

## Explicit assessment of the proposed choices

| Choice | Assessment | Required interpretation |
| --- | --- | --- |
| Use the game descendant's `DBUS_SESSION_BUS_ADDRESS` | **Reject as authority.** | The descendant is post-UMU/pressure-vessel and may name an in-container/private endpoint. Do not copy its D-Bus/XDG pair wholesale. At most, treat it as diagnostic input; it still cannot replace a host-session probe that returns the exact prefix bus. |
| Use `os.getuid()` | **Use only as an identity anchor.** | For this non-root Decky backend it should identify the host user after Decky's UID drop. It is not proof of an active Steam user bus or of the same-prefix service. Cross-check it against Decky's configured host user/home; never turn UID 0 into a desktop target merely because the loader service started as root. |
| Derive `/run/user/<target uid>/bus` | **Guarded fallback.** | Derive it only after resolving a non-root target host UID and confirming the corresponding runtime directory/socket is usable. Pair it with `XDG_RUNTIME_DIR=/run/user/<target uid>`. The path is a candidate, not proof: `--list` must succeed and expose the exact `com.steampowered.App<md5(prefix)>` line. |
| Forward only a verified D-Bus/XDG pair | **Required design.** | Probe with the host user's verified `DBUS_SESSION_BUS_ADDRESS` plus matching `XDG_RUNTIME_DIR`; forward only that pair into the UMU launch context, while retaining the separately validated UMU/Proton/prefix inputs. Do not forward the descendant's pair or arbitrary container environment. |
| Latch failed preflight | **Required fail-closed policy.** | If all bounded candidates/retries fail, record the failure against the stable accepted game session (PID plus start time), suppress watcher-tick reprobes, and clear the latch only after explicit Retry or a new game session. This compensates for UMU's fallback to an ordinary independent launch when `--list` finds no exact bus. |

## Recommended preflight contract

1. Resolve the target host UID from Decky's host-user identity. For
   `flags: []`, `os.getuid()` is a useful check; it must not be used alone
   when the process is root or when another user/session is possible.
2. Build host-session candidates in this order: a host-provided
   D-Bus/XDG pair only if both values are consistent with the target UID, then
   the guarded pair
   `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/<target uid>/bus` and
   `XDG_RUNTIME_DIR=/run/user/<target uid>`.
3. Resolve the launch client using UMU 1.4.4's runtime precedence and run
   `[steam-runtime-launch-client, "--list"]` with `shell=False` under each
   candidate pair. Require a successful exit and the exact prefix bus line.
4. Only after that verification, pass the verified pair to the sidecar's
   UMU invocation, retain the same canonical UMU prefix root, enable
   `UMU_CONTAINER_NSENTER=1`, and let the exact UMU path select
   `PROTON_VERB=runinprefix`.
5. On failure, do not silently launch an unrelated container/prefix. Latch
   the bounded failure to the accepted session and expose Retry as the
   deliberate re-probe path.

No code or files other than this research note were changed.
