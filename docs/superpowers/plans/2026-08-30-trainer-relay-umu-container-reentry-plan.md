# Trainer Relay UMU container re-entry implementation plan

Date: 2026-08-30

1. Preserve the `.16` physical evidence and refute the trainer-location
   hypothesis in the handoff.
2. Add red TypeScript tests for plain identities, duplicate/wrong
   `UMU_CONTAINER_NSENTER`, legacy migration composition, view-model gating,
   and user-facing preparation controls.
3. Add red Python tests for rejecting an unprepared game process and for
   rebuilding the sidecar environment with re-entry enabled and
   `PROTON_VERB` last.
4. Extend the source-preserving migration plan so a selected trainer requires
   exactly one verified re-entry assignment before enablement.
5. Require the inherited flag during process discovery and force it on the
   sidecar while removing stale launcher-service state.
6. Capture bounded UMU stdout/stderr continuously, sanitize retained tails,
   record process-group/descendant metadata, and use INFO logging to avoid a
   complete environment dump.
7. Run backend, frontend, typecheck, lint, compile, build, package-layout,
   deterministic-ZIP, and installed-import gates.
8. Review the complete diff, update the research, ADR, context, user guide,
   validation checklist, version, and handoff.
9. Commit and push the feature and release commits, tag
   `v0.1.0-experimental.17`, verify CI and the public ZIP, then create a local
   installation kit.
10. On the Steam Deck, reinstall `.17`, select the trainer, confirm preparation,
    restart the GOG game, and export diagnostics. Do not promote stable until
    GOG and Epic both pass.
