# Task 3 report — fail-closed Steam Input probe adapter

Date: 2026-09-02
Branch: `feat/trainer-relay`
Base: `ee5be57`

## Result

Implemented the strict frontend registry boundary, typed radial-layout RPC
client, runtime-shape fingerprint, and read-only Steam Input adapter. The
adapter recognizes only a bounded synthetic Neptune summary, reports
`readonly`, and keeps `createSeparateLayout` at
`unsupported_runtime` until a later physically validated writable profile.

## TDD evidence

- RED: `node_modules\\.bin\\vitest.cmd run tests/steam-input-decoder.test.ts tests/radial-layout-rpc.test.ts tests/steam-input-adapter.test.ts`
  - 3 test suites failed during import;
  - 0 tests executed;
  - missing modules were exactly `decoder`, `radialLayoutRpc`, and `adapter`.
- Initial GREEN: 23 tests passed across the 3 focused suites.
- Final focused GREEN: 24 tests passed across the 3 focused suites.
- One test-only TypeScript issue occurred after adding fingerprint-payload
  assertions: the digest mock had an inferred zero-argument tuple. Typing its
  input as `Uint8Array` resolved it; no production behavior changed.

## Files

Created:

- `src/domain/steamInput/decoder.ts`
- `src/infra/radialLayoutRpc.ts`
- `src/infra/steamInput/runtimeFingerprint.ts`
- `src/infra/steamInput/adapter.ts`
- `tests/steam-input-decoder.test.ts`
- `tests/radial-layout-rpc.test.ts`
- `tests/steam-input-adapter.test.ts`

Modified:

- `src/domain/steamInput/types.ts`
- `docs/notes/2026-08-29-trainer-relay-handoff.md`

The required report is this file. `.codex-remote-attachments/` remained
unmodified and was not staged.

## Safety call ledger

- Probe and selected-layout inspection: calls only
  `SteamClient.Input.GetConfigForAppAndController(appId, 0)`.
- Explicit fallback: calls only
  `SteamClient.App.ShowControllerConfigurator(appId)` after positive safe
  integer AppID validation.
- Separate-layout creation: zero Steam calls; returns
  `unsupported_runtime` / `steam_input_runtime_not_validated`.
- Never invoked: `ExportCurrentControllerConfiguration`,
  `StartEditingControllerConfigurationForAppIDAndControllerIndex`, all
  `SetEditingControllerConfiguration*` methods,
  `SaveEditingControllerConfiguration`, `SetSelectedConfigForApp`, and
  `RegisterForControllerConfigInfoMessages`.
- Private Steam returns remain `unknown` at the API seam. Only bounded source
  ID/name summaries leave the adapter. Runtime fingerprints contain schema,
  method-presence booleans, primitive response key/type shape, and controller
  classification; they contain no private response values.
- Decoder/RPC inputs reject extra keys, unsafe IDs/names, unsafe AppIDs,
  malformed hashes/timestamps, duplicate records, equal source/generated IDs,
  unknown capability statuses, and arbitrary diagnostic text.
- `src/infra/steamInput/adapter.ts` contains no `any`.

## Validation

Commands and results:

- `node_modules\\.bin\\vitest.cmd run tests/steam-input-decoder.test.ts tests/radial-layout-rpc.test.ts tests/steam-input-adapter.test.ts` — 3 suites, 24 passed, 0 failed.
- `node_modules\\.bin\\tsc.cmd --noEmit` — passed.
- `node_modules\\.bin\\tsc.cmd --noEmit -p tsconfig.test.json` — passed.
- `node_modules\\.bin\\vitest.cmd run` — 34 suites, 254 passed, 0 failed.
- `node_modules\\.bin\\biome.cmd check src tests vitest.config.ts` — 85 files checked, no fixes/errors.
- `node_modules\\.bin\\rollup.cmd -c` — frontend build passed.
- `git diff --check` — passed; Git emitted only the existing LF/CRLF conversion warning for `types.ts`.

## Commit and GitHub

- Commit subject: `feat: add fail-closed Steam Input probe adapter`
- Commit SHA: recorded in the final session response after commit creation.
- Push target: `origin/feat/trainer-relay`.
- No release, tag, physical Steam Deck validation, or writable runtime profile
  was performed.

## Self-review and continuation

The implementation is limited to Task 3. The next safe task is the read-only
probe UI/export work. Physical capture must happen before any writable profile
is introduced. On resume, verify `git status --short --branch`, keep the
attachment directory untracked, and do not add private Steam payloads or
selection/edit calls.

## Fix round 1 — strict public boundaries

Base implementation: `4a09aad`

### Reviewer requirements addressed

- Capability diagnostics now use a finite allowlist. A syntactically valid but
  unapproved lowercase token is rejected as `invalid_steam_input_capability`.
- RPC transport calls are isolated from decoding. Every thrown/rejected
  transport value, including a forged `RadialLayoutRpcError`, becomes the
  bounded public code `radial_layout_rpc_failed`.
- The exported `radialLayoutRpc.getRegistry()` and `.record()` tests exercise
  the exact Decky callable registrations `get_radial_layout_registry` and
  `record_generated_radial_layout`.
- `SteamInputMethodShape.responsePrimitiveTypes` is mandatory. Fingerprint
  validation requires one allowed primitive type for every unique response key
  and canonical JSON always emits the complete sorted key/type map.
- Primitive response keys with invalid characters, more than 128 characters,
  or a response with more than 64 primitive keys fail closed instead of being
  omitted from the fingerprint.
- The privacy regression includes bounded `account_id`/`access_token`
  structural keys and private identifier/token values. Only key names and the
  literal type `string` reach the digest input; neither private value does.
- The registry freshness test now proves independent document, array, and
  record references plus two-way mutation isolation.

### TDD evidence

- RED command:
  `node_modules\\.bin\\vitest.cmd run tests/steam-input-decoder.test.ts tests/radial-layout-rpc.test.ts tests/steam-input-adapter.test.ts`
- RED result: 3 suites failed; 31 tests executed, 25 passed and 6 failed.
  Failures matched the requested gaps: diagnostic allowlist, exported/internal
  RPC sanitization, two invalid primitive-key cases, and missing primitive type.
- GREEN result for the same command: 3 suites passed; 31/31 tests passed.

### Final validation

- Focused Vitest: 3 suites, 31 passed, 0 failed.
- Full frontend Vitest: 34 suites, 261 passed, 0 failed.
- Production TypeScript: `node_modules\\.bin\\tsc.cmd --noEmit` passed.
- Test TypeScript: `node_modules\\.bin\\tsc.cmd --noEmit -p tsconfig.test.json` passed.
- Biome: 85 files checked, no fixes/errors.
- Rollup: frontend build passed.
- `git diff --check`: passed; only Git LF/CRLF conversion notices were emitted.

### Safety ruling retained

Method presence remains read-only shape evidence only. No writable profile or
authorization was added. `createSeparateLayout` remains unconditional
`unsupported_runtime` with zero Steam calls and performs no request validation.
The adapter still contains no `any`; it invokes only
`GetConfigForAppAndController(appId, 0)` for reads and
`ShowControllerConfigurator(appId)` for explicit fallback. No export, edit,
save, select, registration, or other forbidden Steam method is invoked.

Fix commit subject: `fix: harden Steam Input probe boundaries`. The final SHA
and push status are reported in the session response.
