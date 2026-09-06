# Current Epic session diagnostic evidence

Source: user-provided `G:/Meu Drive/Steam Deck/TrainerRelay-diagnostics-20260906-101309.txt`, read-only. Export reports experimental.22, exported 2026-09-06T10:13:09.181Z; file size 22,305,271 bytes. Source was not modified or copied into Git.

## Findings

- Current session differs from older September 5 records. At 10:06:06 UTC (07:06 Fortaleza), game anchor PID 37905/start 4917226 passed container preflight; trainer spawned with outer process group 37969 and runinprefix. Reentry confirmed at 10:06:08; trainer_running at 10:06:09.
- At 10:06:17, window snapshot lists game window 0x2600003/PID37911 and separate window 0x3600001/PID38038, both state Normal. Snapshot is explicitly truncated: 26 windows total, only eight properties recorded.
- Process records identify PID38038/start4917465 as `Mortal Shell v1` from 10:06:08 through 10:13:08. Rejection reason process_name_mismatch belongs to GAME candidate discovery, not trainer-launch failure. Executable paths are redacted, so exact binary identity is not proved by this export alone.
- Together with the same-session CEF capture of only [39845891] for app2476768691, evidence supports a missing Steam window association/visibility hypothesis, not a simple failure to create a trainer process/window. X11 Normal and trainer_running do not prove switchability or working cheats.
- Only six trainer/umu events were returned for September 6 by filtering; no later trainer exit/error in that filtered export. No automation tests or live mutation performed in this analysis.

## Resume

Do not ask for more photographs of old diagnostic entries. Next inspect current window association properties and exact PID/executable linkage through a bounded read-only device probe, then use an isolated physical association trial or reviewed candidate with backup/rollback. Experimental.24 remains uninstalled/unvalidated. Pending local test must not be silently staged or used as proof of this symptom. No claim of Epic functionality PASS.

Git: documentation-only note; commit/push attempted after creation. Original export and remote attachments remain untouched.
