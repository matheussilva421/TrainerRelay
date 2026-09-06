# Temporary SSH key checkpoint

User explicitly authorized a dedicated temporary key so agent can run diagnosis directly instead of relying on user's separately authenticated PowerShell session.

- Generated ED25519 key in Windows TEMP: `C:/Users/slvma/AppData/Local/Temp/trainerrelay-ssh-eaff13a736814f9db4703fa8cc00a97b/id_ed25519`. Private key must never be read into conversation, copied into repository or committed.
- Public key: `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBPOvd78WuJz9fd17tzcVUlrZeWp7mNJtnjuWy799gWK trainerrelay-diagnostic-20260906`.
- User installation pending. Proposed authorized_keys entry uses restrict (no PTY/forwarding); do not overwrite existing keys.
- Deck host fingerprint verified by user on device: `SHA256:YkrB6o3zby/e8NdZ/Kzx3yBDH01ZFQEg9XBTl/0/8mI`. Verify/pin this on agent connection; never disable host checking.
- Fresh user evidence: game window0x2200003 PID20980, Normal; unnamed 960x600 window0x3600003 PID21213 with no WM_STATE. Both lack STEAM_GAME. Do not infer missing property alone explains failure; identify PID21213 and map state before mutation.
- Next after authorization: strict host verification and explicit key, BatchMode, IdentitiesOnly. Read ps for the two PIDs and xwininfo stats. Rediscover if session changed. No password authentication or secret from earlier photo.
- Cleanup: remove ONLY matching public-key entry from Deck authorized_keys, preserving all other entries; remove only dedicated temporary key files after confirming path. User enabled sshd persistently for diagnosis; arrange `sudo systemctl disable --now sshd` at completion.
- No runtime test or authenticated agent SSH completed at checkpoint. Key generation succeeded; no production code changed. Documentation commit/push pending at creation.
