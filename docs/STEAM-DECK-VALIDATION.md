# Steam Deck validation — Trainer Relay v0.1.0-experimental.2

This checklist is intentionally manual. The release must not be promoted to stable until one real Epic title and one real GOG title pass the checks below on a physical Steam Deck.

## Preparation

- [ ] Record the SteamOS version, Decky Loader version, UniFiDeck version, and Trainer Relay version.
- [ ] Keep the original CheatDeck installed for direct Steam launches.
- [ ] Choose one supported Epic shortcut and one supported GOG shortcut created by UniFiDeck.
- [ ] Use a trusted Windows `.exe` trainer for each title. Do not use `.bat` files or trainer arguments.
- [ ] Capture screenshots of the Trainer Relay configuration and status, but do not capture credentials or complete launch options.

## Evidence commands

Run these from a Konsole session while the relevant shortcut is active. Replace `<PID>` only after reading it from the first command. These commands expose bounded anchors rather than dumping a process environment.

```bash
pgrep -af 'unifideck-launcher'
readlink -f /proc/<PID>/exe
stat -c '%d:%i:%Y:%n' /proc/<PID>
tr '\0' '\n' < /proc/<PID>/environ | grep -E '^(STEAM_COMPAT_DATA_PATH|WINEPREFIX|SteamAppId|SteamGameId)='
```

Expected evidence:

- the launcher command contains exactly one literal `epic:<game_id>` or `gog:<game_id>` token;
- `/proc/<PID>/exe` resolves to the expected Windows executable path;
- the process identity remains stable while the trainer starts;
- the selected prefix is the configured default or absolute override;
- no complete environment or secret-bearing launch option is copied into the report.

Do not use `printenv`, `env`, or an unrestricted `/proc/<PID>/environ` dump in a bug report.

## Epic title

- [ ] Configure the Epic identity and trainer path.
- [ ] Launch the game from the UniFiDeck shortcut.
- [ ] Confirm the game reaches its main menu before the trainer window appears.
- [ ] Confirm the Trainer Relay status progresses through `waiting_for_game` and `launching` to `running`.
- [ ] Confirm exactly one trainer instance is present.
- [ ] Confirm the trainer and game use the same prefix anchor.
- [ ] Confirm gameplay remains intact if the trainer is missing or exits early.
- [ ] Exit the game and confirm the Trainer Relay trainer exits within the configured shutdown window.
- [ ] Force Sync the shortcut and confirm the Trainer Relay configuration remains available.

## GOG title

- [ ] Repeat every Epic check for the GOG identity.
- [ ] Confirm the identity token is `gog:<game_id>`, not a guessed title or path.
- [ ] Confirm exactly one trainer instance is present and the game is never terminated by a trainer failure.

## Migration check

- [ ] On a disposable copy of one shortcut, add the legacy `PROTON_REMOTE_DEBUG_CMD` and `PRESSURE_VESSEL_FILESYSTEMS_RW` options.
- [ ] Confirm Trainer Relay displays the discovered trainer and asks for confirmation.
- [ ] Confirm `%command%`, the identity token, and unrelated launch options are preserved.
- [ ] Confirm only the two legacy variables are removed.
- [ ] Confirm AppDetails is re-read and the new configuration is enabled only after the expected text is present.
- [ ] Confirm reintroducing either legacy variable produces `invalid_config` and no trainer launch.

## Failure, retry, and ownership

- [ ] Make the trainer exit immediately and confirm one automatic retry occurs only while the same game session is active.
- [ ] Confirm a later retry requires the manual Retry action.
- [ ] Start a duplicate candidate and confirm the state becomes `ambiguous` without starting a trainer.
- [ ] Confirm stopping Trainer Relay does not stop the game, `wineserver`, global UMU, or another trainer.
- [ ] Review the plugin log for status/diagnostic codes only; confirm no environment dump, credential, cookie, or token is present.

## Results

| Check | Epic | GOG | Notes |
| --- | --- | --- | --- |
| Game starts before trainer | PENDING | PENDING | |
| Same prefix anchor | PENDING | PENDING | |
| One trainer instance | PENDING | PENDING | |
| Trainer exits with game | PENDING | PENDING | |
| Failure leaves game intact | PENDING | PENDING | |
| Force Sync preserves config | PENDING | PENDING | |
| Logs contain no sensitive dump | PENDING | PENDING | |

## Promotion gate

Keep the release experimental until every required row is `PASS` for both titles, with the SteamOS/Decky/UniFiDeck versions and concise evidence recorded in the handoff. A failed or unavailable physical-device check is a release blocker, not a reason to weaken the fail-closed behavior.
