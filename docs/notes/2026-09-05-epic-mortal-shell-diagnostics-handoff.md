# Epic Mortal Shell diagnostic analysis

Source: `G:/Meu Drive/Steam Deck/TrainerRelay-diagnostics-20260905-205012.txt`.
SHA-256: `2B59CD2C6770B1686A53C7C248617F5B81987D3BAFA437EA1594386EC854D9D3`.

The export reports plugin `0.1.0-experimental.19`, not the locally rebuilt .20.
It contains 1175 Epic identity events for Mortal Shell,
`epic:0055e45ce7654c55aade646467349e83`.

## Measured sequence (UTC)

- 20:49:23.216, event 15384: trainer spawned using bundled UMU,
  `runinprefix` and enabled container re-entry; owned group 22616.
- 20:49:26.823, event 15479: trainer running after 3578 ms.
- 20:49:54.280: accepted game PID 22564 (`Dungeonhaven.exe`) and observed
  shipping executable PID 22570 (`Dungeonhaven-Win64-Shipping.exe`) share the
  expected Epic prefix with `STORE=none`, GE-Proton11-6. The shipping process
  is rejected as the tracked session because games.map names Dungeonhaven.exe.
- 20:49:54.282: actual Windows trainer PID 22711 remains visible in that prefix.
  Its candidate rejection is expected: it is not the configured game executable.
- 20:49:55.444: accepted count drops to zero; neither game PID is present in
  this scan's candidate events, while the trainer still appears.
- 20:49:55.454: session ended.
- 20:49:55.646: SIGTERM sent to owned trainer group 22616, forced=false.

## Conclusion and limits

This capture provides real Epic trainer launch evidence. No launch failure or
premature trainer exit is evidenced. Both game processes disappear before the
plugin sends its trainer termination signal. The export cannot establish whether
the user closed the game or it crashed; a CrashReportClient process alone does
not prove a crash. It also cannot prove cheat activation or in-game effects.

Tracking the bootstrap instead of the shipping executable is a potential
lifecycle limitation, but this capture does not show the shipping process
surviving the tracked bootstrap. Do not implement a speculative matching change.

## Handoff

- Changed only this analysis document; no runtime/configuration changes.
- Verification: filtered complete source export, deduplicated Epic candidates,
  inspected launch/end timeline and SHA-256. No automated tests rerun for this
  documentation-only analysis.
- Git baseline: a28b09f, feat/trainer-relay; documentation committed/pushed
  separately. Local attachment directory remains untouched.
- Next: ask whether trainer UI opened, a cheat actually worked, and whether the
  game was closed manually. If all confirmed, record Mortal Shell Epic as the
  physically validated title on .19; do not generalize to all Epic titles or .20
  sidebar/helper controls. If a symptom remains, reproduce that specific symptom.
