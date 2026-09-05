# Live CEF and known-working GOG baseline

## State

- User confirms experimental.19 opened the trainer for GOG. This is user-observed runtime evidence, not a new replay by the agent.
- User confirms experimental.22 still shows only Mortal Shell in Steam's window switcher. Do not call .22 a verified fix.
- Scope remains trainer launch/window visibility. Cancelled radial-menu work stays cancelled.

## Checks performed

- Read-only elevated TCP checks: 192.168.1.247:8081 reachable; 22 and 18081 unavailable.
- GET :8081/json/list succeeded. SharedJSContext target F449D295DB537C9D2C95E25571665BC3, route /routes/apprunning. Rediscover target IDs before resuming.
- Read-only CEF Runtime.evaluate: FocusedAppWindowStore reports app ID 2476768691, window ID 39845891. AppDetails has no window-list field. This proves focus, not trainer visibility.
- Inspected supplied kit without extraction or execution: C:/Users/slvma/Downloads/TrainerRelay-v0.1.0-experimental.19-kit.zip contains TrainerRelay-v0.1.0-experimental.19.zip (307848 bytes), docs and checksums.
- Compared nested py_modules/trainer_relay/environment.py against current source: only added lines are the .22 UMU_STEAM_GAME_ID restoration block. No other environment-module changes found. Other modules still require full comparison.
- Local ../Unifideck/unifideck/bin/umu/umu/umu_run.py is only 7 bytes; do NOT treat it as authoritative installed UMU implementation.

## Primary-source research

Source: https://raw.githubusercontent.com/Open-Wine-Components/umu-launcher/1.4.4/umu/umu_run.py

- run_command gates run_in_steammode on Gamescope, STEAM_MULTIPLE_XWAYLANDS=1 and Flatpak (lines 653-660, 685-686).
- run_in_steammode starts monitor_windows only with a baselayer sequence and waitforexitandrun (lines 613-630).
- Container reentry sets runinprefix (lines 349-383).
- Therefore restored incoming identity alone does not guarantee execution of UMU's window-property monitor. This is source-level evidence, not proof of the device's actual branch or the root cause.
- Installed UMU source/version must still be matched. GOG and Epic tests also differ in game/trainer binaries, so store causality is not established.

## Pending / resume

1. Obtain actual Steam-recognized window list and correlate trainer X11 PID/window with game app ID, window type, transient owner and skip-taskbar state. Current probe captures only eight windows and lacks these fields.
2. Compare remaining .19 modules against current code without installing or overwriting the known-working package.
3. Reproduce the actual visibility failure before another behavior change. Do not equate process-alive or WM_STATE Normal with visibility in Steam.
4. Use narrow RED/GREEN tests for any demonstrated correction; physical Deck validation remains required.

## Delivery status

- No plugin behavior, device settings, focus or processes changed during these checks.
- No automated tests run: read-only investigation and this note only.
- Git branch feat/trainer-relay. Existing untracked .codex-remote-attachments/ preserved.
- Commit/push of this note pending; no new ZIP produced.
