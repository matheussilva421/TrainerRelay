# Nested UMU Steam shortcut identity

User reports GOG trainer window switching works, Epic Mortal Shell only lists
the game. Device .windows.2 evidence proves trainer window exists on DISPLAY=:1,
but not visible/selectable through Steam. No captured identity environment values
prove the specific on-device cause yet.

Primary source inspected:
https://raw.githubusercontent.com/Open-Wine-Components/umu-launcher/main/umu/umu_run.py
set_env captures incoming SteamGameId into UMU_STEAM_GAME_ID then replaces
SteamGameId with UMU's SteamAppId, commonly zero. get_steam_appid uses media/cache
paths before falling back to UMU_STEAM_GAME_ID shifted right 32 bits.
monitor_windows assigns Steam properties to windows it tracks. Consequently a
nested invocation can overwrite a retained shortcut identity with zero. Whether
the installed bundled UMU version and window-monitor branch produce this user's
symptom remains to be tested physically. Different media/cache metadata and
Legendary's detached process chain can explain store differences, but are not
measured GOG/Epic differential proof.

Implemented .22: sanitized environment restores SteamGameId from a retained
UMU_STEAM_GAME_ID only for a valid uint64 non-Steam shortcut encoding (high bit
of upper 32 set; lower 32 equals 0x02000000), and only if current ID is absent,
zero or identical. Invalid/ambiguous values do not override a nonzero identity.
No change to prefix/container resolution, game environment or global focus.

UI: trainer-selection message no longer falsely asserts UMU preparation missing;
successful enable/disable clears the stale message. Preparation button remains
derived from migration plan: absent when launch options are already prepared.

Tests: observed RED with SteamGameId=0 despite original retained ID; GREEN after
fix. Added invalid-ID and conflicting-ID cases. Full backend 267/267, frontend
217/217, packaging 7/7; TypeScript production/tests, build, compileall passed.
Biome formatting correction applied; diff check clean. UI tested with existing
suite only; no claim of new hook regression coverage or physical validation.

Files: environment.py and test_environment.py; useRelayPageController.tsx;
main.py, package.json and package assertions. ZIP .22 SHA256:
83FF43CE6F935371847E54C50061BFB73304732E3D05BDC745431ABAA9A494C1.
Git commit/push target feat/trainer-relay. No device installation performed.

Next: install .22, restart plugin/Steam, start a fresh Epic session and inspect
STEAM window list. Export persistent TXT. If absent, obtain bounded original
Steam IDs and installed UMU window monitor behavior before applying window
properties. Do not present this candidate correction as physically verified.
