# Trainer Relay host-session D-Bus correction plan

Date: 2026-08-30

1. Replay the `.17` diagnostic export and quantify the failing boundary.
2. Compare Decky sandbox identity, UMU 1.4.4 launch-client behavior, Steam
   Runtime launcher-service documentation, and UniFiDeck headless-session
   patterns against primary sources.
3. Add red tests proving the game container D-Bus is rejected, the target Deck
   user session is selected, failure metadata remains bounded, and the same
   failed session is not probed every watcher tick.
4. Resolve and verify a host-session candidate before forwarding only its
   D-Bus/XDG pair to UMU; preserve `PROTON_VERB=runinprefix` as the final
   environment assignment.
5. Run backend, frontend, typecheck, lint, build, packaging/import, determinism,
   and independent review gates.
6. Publish `v0.1.0-experimental.18`, verify the public asset, and create a
   versioned installation kit.
7. Reinstall on the Steam Deck and require physical GOG and Epic evidence
   before any stable promotion.
