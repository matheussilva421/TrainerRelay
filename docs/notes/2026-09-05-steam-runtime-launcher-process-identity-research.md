# Steam Runtime launcher process identity research

## Question

Can TrainerRelay identify the X11 window created by a trainer launched through UMU 1.4.4 container re-entry by comparing its PID's process group with the outer `umu-run` process group?

## Primary-source findings

The answer is no.

- UMU 1.4.4 builds the re-entry command as `steam-runtime-launch-client --bus-name=... -- <compatibility-tool command> <EXE>`. Its `run_command` starts the outer command in a new session, but that only owns the local `umu-run`/launch-client side of the boundary. Source: [UMU `build_command`](https://github.com/Open-Wine-Components/umu-launcher/blob/cf3d1b107147480c447ffbfb3f789dc74335074c/umu/umu_run.py#L359-L415) and [UMU `run_command`](https://github.com/Open-Wine-Components/umu-launcher/blob/cf3d1b107147480c447ffbfb3f789dc74335074c/umu/umu_run.py#L735-L744).
- The launch client is a client/server boundary analogous to `ssh`: the command is created by `steam-runtime-launcher-service`, not as a normal descendant of the client. Source: [launch-client manual](https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/06a2477429fe271c5b254399caffdab8b7737e99/bin/launch-client.md).
- Before the service spawns the command, its child setup calls `setsid()` and `setpgid(0, 0)` unless configured to retain the TTY session. The resulting trainer therefore has a new session/process group. Source: [launcher-service child setup](https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/06a2477429fe271c5b254399caffdab8b7737e99/bin/launcher-service.c#L421-L448).
- The D-Bus `Launch()` result is a PID in the service/container namespace and is not guaranteed to be meaningful in the caller's namespace. Source: [Launcher1 interface](https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/06a2477429fe271c5b254399caffdab8b7737e99/steam-runtime-tools/com.steampowered.PressureVessel.Launcher1.xml).

This explains why experimental.23's PGID test was locally green but would normally produce `no_owned_windows` on the physical re-entry path. Experimental.23 is superseded and must not be installed.

## Environment-marker hypothesis

A random variable added only to the outer `umu-run` environment is not a valid ownership marker. By default, launch-client commands inherit the launcher-service environment, not the client's environment. Passing a client value requires an explicit `--env` or `--pass-env` option. UMU 1.4.4 does not add such an option for arbitrary TrainerRelay variables in its re-entry command. Source: [launch-client environment semantics](https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/06a2477429fe271c5b254399caffdab8b7737e99/bin/launch-client.md#environment-options) and the UMU command construction linked above.

Therefore no unverified marker injection was added.

## Selected bounded correction

Experimental.24 validates each X11 `_NET_WM_PID` directly against `/proc`:

1. the process command line must resolve to the exact configured trainer executable;
2. `WINEPREFIX` must equal the selected compatdata anchor or its `/pfx` child;
3. `/proc/<pid>/stat` start time must remain stable across the read;
4. the same PID/start-time identity is revalidated immediately before and after the `STEAM_GAME` write;
5. if windows map to more than one matching process identity, the operation returns `ambiguous_owned_windows` before any write.

This is a bounded trusted-session ownership check, not a hostile-X11 security boundary. A malicious peer on the same X display can forge or alter X11 properties. Physical validation must run with only the intended game/trainer processes in scope.

## Evidence boundary

- Measured on the prior Deck capture: trainer X11 window `0x3600001` exposed PID `31304`; the game window `0x2600003` exposed PID `31186`.
- Demonstrated from upstream source: service-launched processes do not retain the outer client PGID, and arbitrary client environment is not automatically forwarded.
- Demonstrated locally by automated tests: exact executable/prefix/PID identity can distinguish the captured trainer/game topology and fails closed on ambiguity or PID reuse.
- Still unknown: whether experimental.24 makes the trainer appear and remain selectable in the physical Steam window switcher. Only a fresh Deck run can establish that.
