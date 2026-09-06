# Deck access restored

- User confirms Deck powered on at 192.168.1.247 and TrainerRelay experimental.22 installed; no newer package installed.
- Read-only elevated GET http://192.168.1.247:8081/json/list succeeded. Six page targets returned, including SharedJSContext at https://steamloopback.host/routes/library/home. This proves CEF reachability, not plugin version or absence of a running game.
- No installation, settings change, game launch, or runtime evaluation performed. No automated tests executed.
- Prior device-access blocker is resolved. Epic trainer functionality remains unverified. Pending local test and remote attachments must remain untouched.
- Next: obtain fresh experimental.22 reproduction with Mortal Shell Epic and the configured trainer; correlate plugin diagnostics, trainer process/window and Steam-recognized windows. Do not install .24 automatically or call it validated.
- Git delivery: documentation-only checkpoint; commit/push pending at creation.
