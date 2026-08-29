import { describe, expect, it, vi } from "vitest";

vi.mock("@decky/api", () => ({ callable: () => async () => undefined }));

import type { LaunchIdentity, RelayGameConfig } from "../src/domain/relay/types";
import { createRelayRpc, decodeRelayStatusResponse, persistRelayGameConfig } from "../src/infra/relayRpc";

const identity: LaunchIdentity = "gog:game-1";
const game: RelayGameConfig = { enabled: false, trainerPath: "/home/deck/Trainer.exe" };

describe("Trainer Relay RPC boundary", () => {
  it("turns unknown status payloads into invalid_config with a safe code", () => {
    expect(
      decodeRelayStatusResponse(identity, { identity, state: "launched", diagnostic: { message: "secret" } }),
    ).toEqual({
      identity,
      state: "invalid_config",
      diagnostic: { code: "unknown_status" },
    });
  });

  it("does not expose arbitrary diagnostic text from a valid status payload", () => {
    expect(
      decodeRelayStatusResponse(identity, {
        identity,
        state: "failed",
        diagnostic: { code: "trainer_failed", detail: "private environment" },
      }),
    ).toEqual({ identity, state: "failed", diagnostic: { code: "trainer_failed" } });
  });

  it("decodes a relay RPC response through the typed transport", async () => {
    const rpc = createRelayRpc({
      getRelayConfig: vi.fn().mockResolvedValue({ schemaVersion: 1, games: { [identity]: game } }),
      setRelayGameConfig: vi.fn().mockResolvedValue({ schemaVersion: 1, games: { [identity]: game } }),
      getRelayStatus: vi.fn().mockResolvedValue({ identity, state: "waiting_for_game", diagnostic: null }),
      retryRelay: vi.fn().mockResolvedValue({ identity, state: "retrying", diagnostic: { code: "manual_retry" } }),
    });

    await expect(rpc.getRelayConfig()).resolves.toEqual({ schemaVersion: 1, games: { [identity]: game } });
    await expect(rpc.getRelayStatus({ identity })).resolves.toEqual({
      identity,
      state: "waiting_for_game",
      diagnostic: null,
    });
  });

  it("accepts persistence only when the backend returns the exact identity and config", async () => {
    const setRelayGameConfig = vi.fn().mockResolvedValue({ schemaVersion: 1, games: { [identity]: game } });
    const rpc = createRelayRpc({
      getRelayConfig: vi.fn(),
      setRelayGameConfig,
      getRelayStatus: vi.fn(),
      retryRelay: vi.fn(),
    });

    await expect(persistRelayGameConfig(rpc, identity, game)).resolves.toEqual(game);
    expect(setRelayGameConfig).toHaveBeenCalledWith({ identity, config: game });
  });

  it("fails closed when persistence returns an unknown or different config", async () => {
    const rpc = createRelayRpc({
      getRelayConfig: vi.fn(),
      setRelayGameConfig: vi.fn().mockResolvedValue({ schemaVersion: 1, games: {} }),
      getRelayStatus: vi.fn(),
      retryRelay: vi.fn(),
    });

    await expect(persistRelayGameConfig(rpc, identity, game)).rejects.toMatchObject({ code: "invalid_config" });
  });
});
