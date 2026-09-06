# Deck access restored

- User confirms Deck powered on at 192.168.1.247 and TrainerRelay experimental.22 installed; no newer package installed.
- Read-only elevated GET http://192.168.1.247:8081/json/list succeeded. Six page targets returned, including SharedJSContext at https://steamloopback.host/routes/library/home. This proves CEF reachability, not plugin version or absence of a running game.
- No installation, settings change, game launch, or runtime evaluation performed. No automated tests executed.
- Prior device-access blocker is resolved. Epic trainer functionality remains unverified. Pending local test and remote attachments must remain untouched.
- Next: obtain fresh experimental.22 reproduction with Mortal Shell Epic and the configured trainer; correlate plugin diagnostics, trainer process/window and Steam-recognized windows. Do not install .24 automatically or call it validated.
- Git delivery: documentation-only checkpoint; commit/push pending at creation.

## Fresh running-game capture

- After user reported ready, rediscovered SharedJSContext and issued one read-only CDP Runtime.evaluate.
- Route is `/routes/apprunning`. SteamUIStore.WindowStore.m_mapAppWindows reports app 2476768691 with windowids [39845891] (0x2600003), focusedWindowID 0; app 769 separately has [37748789].
- This demonstrates one Steam-recognized window for the target app at capture time. It does NOT establish whether the trainer process exists or whether an unassociated X11 window exists. No focus, window property, plugin, or process changed.
- Next distinguish trainer launch failure from missing window association using the installed .22 Relay status/diagnostics. Keep game running for that capture. No automated tests in this capture.
