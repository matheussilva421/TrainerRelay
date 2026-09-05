# Epic runtime continuation checkpoint

## Current evidence

- HEAD at inspection: `4000c92`, branch `feat/trainer-relay`, tracking `origin/feat/trainer-relay` without reported divergence (no fetch performed).
- Existing uncommitted `tests_backend/test_window_probe.py` change preserved. `.codex-remote-attachments/` untouched.
- Ran `python -m unittest tests_backend.test_window_probe.WindowProbeTests.test_never_adopts_a_matching_trainer_process_that_predates_the_relay_spawn -v`: 1 test, 0 passed, 1 failed. The injected writer was called for window `0x20` and app ID `2476768691`.
- This test supplies an accepted identity through a mock but no launch timestamp or prelaunch identity set. Its failure does not itself demonstrate that the process predates a Relay launch, nor reproduce the Epic visibility symptom. Do not use it alone to justify a new release.
- CEF GET `http://192.168.1.247:8081/json/list`: sandbox socket restriction, then elevated read-only retry timed out after 5 seconds. This does not prove the Deck is powered off; current access is unavailable.
- `git diff --check`: exit 0, only LF/CRLF notice.

## Scope and status

No production changes, package generation, installation, game manipulation or new physical validation in this continuation. Prior .24 suite results remain historical; the current working tree includes a failing pending test. Epic trainer opening, Steam window selection and in-game functionality remain unproven. No .25 correction has been implemented.

## Resume

1. Ask user to confirm the Deck is awake, on the same network, and its current IP. Restore access before another physical trial.
2. Rediscover CEF targets, installed plugin version and game state; do not reuse old target/PID identities.
3. Preserve known-good package and follow the documented install/rollback checkpoint before any deployment.
4. Capture actual trainer launch, Steam-recognized windows, switchability and intended offline in-game behavior. A live process or mocked X11 write is not a runtime PASS.
5. Resolve the pending test at a seam that actually models launch provenance if that contract is pursued; do not infer that provenance is the cause of the observed Epic failure.

Git delivery: attempted documentation-only staging failed with index.lock permission denied; subsequent commit/push failed with dubious ownership. No global safe.directory setting changed. A command-scoped safe.directory status check succeeded and confirmed this note remains untracked. Do not stage the pre-existing test change or remote attachments.

Independent local-source research agent `01a073ff-1f24-7251-8281-29bcb32e9fcd` completed `docs/notes/2026-09-05-preexisting-test-evidence.md`; main agent read the result. It confirms the pending test does not model temporal provenance or demonstrate Epic visibility. No production correction follows from this test alone.

Follow-up continuation: elevated CEF GET timed out again after 5 seconds. Agent wait returned nonterminal timeout; expected research file not yet present. No restart or duplicate research launched. Previous turn classified as progress (new test/network evidence); current device blocker has recurred for two goal turns, not yet the three-turn blocked threshold. Staging area verified empty before retrying documentation-only Git delivery.

Delivery subsequently recovered using elevated Git with invocation-only safe.directory: checkpoint commit `50ad6eb` pushed successfully to `origin/feat/trainer-relay`. Research completed after that push; this final documentation update incorporates its result. No new tests executed in the follow-up, no new ZIP, and physical Epic validation remains blocked on restored Deck access/current IP confirmation.
