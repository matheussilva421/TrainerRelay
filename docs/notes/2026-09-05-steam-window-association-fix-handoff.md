# TrainerRelay experimental.23 — Steam window association handoff

> **SUPERSEDED — DO NOT INSTALL experimental.23.** Primary-source review after this handoff showed that `steam-runtime-launcher-service` creates the launched trainer in a new session/process group, so the PGID ownership premise below is false for the re-entry path. Continue from `2026-09-05-steam-window-association-fix-v24-handoff.md`.

## Scope and boundary

This work addresses the reported Steam/Gamescope window-switcher failure for the Mortal Shell Epic session. The user-observed GOG experimental.19 success remains a baseline, not a controlled regression comparison. Experimental.23 is a code-level candidate correction and must not be described as a physical runtime fix until a fresh Deck session passes the gate below.

No plugin, process, game, Steam setting, or device file was changed during implementation. The existing untracked `.codex-remote-attachments/` directory was preserved and excluded from staging.

## Live RED captured

With Mortal Shell running on the Deck, read-only CEF/CDP inspection of `SteamUIStore.WindowStore.m_mapAppWindows` was repeated three times. AppID `2476768691` contained only window `39845891` (`0x2600003`), the game window. The known trainer X11 window was absent from Steam's app-window map.

This is the exact observable RED for the user's symptom. Process-alive, focus, or `WM_STATE=Normal` were not treated as proof of Steam visibility. The game could be closed after this capture.

## Root-cause evidence and decision

Primary-source research is recorded in `docs/notes/2026-09-05-live-cef-steam-umu-research.md`.

- UMU 1.4.4 writes `STEAM_GAME` only for windows whose `_NET_WM_PID` belongs to the process tree it monitors.
- UMU container re-entry changes `PROTON_VERB` to `runinprefix`.
- The UMU Steam-mode window monitor is gated on `PROTON_VERB == waitforexitandrun`, in addition to Gamescope/Flatpak/multiple-Xwayland/baselayer gates.
- Gamescope reads non-zero `STEAM_GAME` as an authoritative AppID and publishes focusable window triplets.

Therefore restoring the incoming Steam identity in experimental.22 was necessary but insufficient: the re-entered sidecar invocation does not start the monitor that would compensate for a detached trainer window. The minimal candidate correction applies the validated shortcut AppID directly, but only to a window whose PID is still in the exact process group created and owned by TrainerRelay.

## Implemented

- `trainer_relay/window_probe.py`
  - validates the unsigned 64-bit non-Steam shortcut identity before enumeration;
  - enumerates at most 64 X11 windows with shell-free commands and per-command timeouts;
  - accepts only windows whose `_NET_WM_PID` belongs to the exact owned process group;
  - re-reads PID/group before the write and verifies PID/group/`STEAM_GAME` afterward;
  - skips an already-correct association and fails closed on query, ownership, timeout, or verification errors;
  - returns bounded counters/status without titles, paths, PIDs, AppIDs, or window IDs.
- `trainer_relay/watcher.py`
  - attempts association at 5, 10, and 15 seconds after confirmed UMU re-entry;
  - stops after verified success, a terminal invalid-input condition, or three attempts;
  - preserves the existing opt-in read-only window snapshot.
- `trainer_relay/diagnostics.py`
  - allowlists only the bounded association status/counters.
- `main.py`, `package.json`, and packaging expectations
  - version advanced to `0.1.0-experimental.23`.
- `docs/STEAM-DECK-VALIDATION.md`
  - adds the physical Steam window-switcher gate and the fail-closed `no_owned_windows` branch.

## TDD evidence

Focused RED/GREEN cycles were captured for:

- missing association implementation;
- foreign process-group exclusion;
- invalid shortcut identity rejection;
- no rewrite when already associated;
- bounded association deadline;
- watcher retry-until-verified behavior;
- diagnostic event allowlist;
- package version synchronization.

## Automated validation

- `python -m unittest discover -s tests_backend -p 'test_*.py'`
  - 280 executed, 280 passed, 0 failed after review-driven additions.
- `python -m unittest discover -s tests_packaging -p 'test_*.py'`
  - 7 executed, 7 passed, 0 failed.
- `node_modules/.bin/vitest.cmd run`
  - 30 files passed; 217 tests passed, 0 failed.
- local TypeScript compiler for the application and test configs
  - exit 0.
- local Biome check over `src`, `tests`, and `vitest.config.ts`
  - 75 files checked, no fixes or errors.
- local Rollup build
  - `dist` created successfully; exit 0.
- `git diff --check`
  - no whitespace errors; only Windows LF-to-CRLF notices.

The normal `pnpm` wrapper did not execute because it could not verify/download the pinned `pnpm@11.5.0` release from the registry. No registry bypass was enabled. The equivalent project-local binaries already present in `node_modules/.bin` were used successfully and required no download.

## Artifact

- New package: `artifacts/TrainerRelay-v0.1.0-experimental.23.zip`
- Size: 769,751 bytes
- SHA-256: `DB347558E40439DB8964998D83A35C8A90EC5A89B13C81B4AE210ECAFB1BD923`
- ZIP entries: 34
- Embedded `package.json` and `main.py` both report `0.1.0-experimental.23`.
- The pre-existing root `TrainerRelay.zip` was not overwritten.

## Physical validation gate — still pending

1. Install experimental.23 and start a fresh Epic/Mortal Shell session; do not reuse the experimental.22 process.
2. Wait at least 15 seconds after `container_reentry_confirmed`.
3. Inspect the bounded `window_association` diagnostic:
   - `associated` or `already_associated`: proceed to Steam selector verification;
   - an early `no_owned_windows`: allow the bounded retries to continue;
   - final `no_owned_windows`: no matching owned window was found and no window was changed; preserve evidence and stop;
   - any failure/partial/deadline result: preserve counts/status and stop.
4. Re-read Steam's app-window map. Both game and trainer must appear under shortcut AppID `2476768691`.
5. Open Steam's window switcher and actually select the trainer. Visibility and switching are required; focus alone is insufficient.
6. Confirm gameplay still works and game exit stops only the owned trainer group.
7. Repeat the known GOG baseline under experimental.23 to detect regression.

## Git status and continuation

- Branch: `feat/trainer-relay`.
- Primary-source research note was committed and pushed as `1045da5 docs: add Steam UMU window research`.
- Experimental.23 implementation, tests, validation checklist, and handoff were committed as `b73f80a fix: associate owned trainer windows with Steam` and pushed to `origin/feat/trainer-relay`.
- Do not stage `.codex-remote-attachments/` or any ZIP artifact.

Resume by reading this handoff and the research note, resolving any open review findings, rerunning affected gates, then committing the exact intended file list. Physical validation remains a separate, explicit user/device checkpoint.

## Review resolution and residual X11 boundary

The independent review initially found no critical issues, two important issues, and several minor issues. The timing finding was reproduced RED and corrected by storing `reentry_confirmed_at`; delays now start at the observed confirmation instant. Additional review-driven tests enforce diagnostic status/count bounds, normalize malformed/non-mapping/internally inconsistent associator output, record a missing Steam identity once as a terminal result, and include enumeration and each production X11 command in the two-second budget. The same reviewer performed two follow-up passes; the final result was zero Critical, Important, or Minor findings and `Ready: yes` for the code-level candidate.

The request for an atomic authoritative X11 validate-and-write operation was not implemented because this X11 path is cooperative: `_NET_WM_PID` is client-supplied, XIDs can theoretically be reused, and `xprop` has no compare-and-set transaction. This implementation follows UMU's own `_NET_WM_PID` model and narrows it with exact process-group checks immediately before and after the write. It is fail-closed for ordinary ownership mismatch/race evidence, but it is not a security boundary against a malicious peer X11 client; such a client can already modify peer properties on the shared display. Physical validation must be performed only with the trusted trainer/game processes in scope.
