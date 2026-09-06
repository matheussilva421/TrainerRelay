# Current session: reentry preparation absent

Direct authenticated read-only SSH investigation, experimental.22 still installed.

- Current game PID24119 Dungeonhaven.ex/start64943 rejected with container_reentry_missing. Current process environ allowlist confirms UMU_CONTAINER_NSENTER absent, DISPLAY=:1, SteamGameId/SteamAppId=0.
- Steam shortcuts.vdf read-only parsed row app2476768691 Mortal Shell: Exe points to Unifideck launcher; LaunchOptions exactly epic:0055e45ce7654c55aade646467349e83. Preparation absent on disk too. No assertion yet about who removed it or when.
- Config remains enabled with expected Mortal Shell trainer path. No trainer/umu launch events after plugin_loaded at 10:37:35 UTC. Prior successful launch events belong to earlier boot/session, not current one.
- PID24251/window0x3400003 identified by diagnostics as EOSOverlayRenderer-Win64-Shipping.exe, CrBrowserMain. It is unmapped, not evidence of a trainer window.
- Therefore current failure is launch blocked by missing preparation, distinct from earlier observed trainer visibility failure. Do not deploy .24 as a proven cure or mutate the overlay.
- No code changes, deployment, process termination, window writes or automated tests. Existing pending test and attachments untouched.
- Next human checkpoint: user save and close game normally. Then reprepare exact shortcut through existing verified Steam API flow, preserving options; verify readback and launch fresh session. Capture actual trainer/window before further correction. Investigate persistence separately if preparation disappears again.
- Research agent01a0765b-0b06-7260-9ed1-6462ea2f42b2 assigned bounded lifecycle analysis, notified current evidence; output docs/notes/2026-09-06-running-lifecycle-research.md pending. Do not duplicate work.
- Temporary SSH key/service remain enabled by user authorization, cleanup required at completion; see temporary-ssh-key handoff. No credentials collected.
- Git: documentation-only commit/push follows. Objective remains incomplete.
