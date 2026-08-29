import { describe, expect, it, vi } from "vitest";

vi.mock("@decky/api", () => ({ callable: () => async () => undefined }));

import type { LaunchIdentity, RelayGameConfig } from "../src/domain/relay/types";
import { disableTrainerRelay, enableTrainerRelay, selectTrainerPath } from "../src/hooks/relayActions";
import type { RelayRpcClient } from "../src/infra/relayRpc";

const identity: LaunchIdentity = "gog:game-1";
const current: RelayGameConfig = { enabled: true, trainerPath: "/home/deck/old.exe" };
const disabled: RelayGameConfig = { enabled: false, trainerPath: "/home/deck/new.exe" };

const client = (setRelayGameConfig: RelayRpcClient["setRelayGameConfig"]): RelayRpcClient => ({
  getRelayConfig: vi.fn(),
  setRelayGameConfig,
  getRelayStatus: vi.fn(),
  retryRelay: vi.fn(),
});

describe("Trainer Relay configuration actions", () => {
  it("persists a browsed trainer path disabled before any explicit enable", async () => {
    const setRelayGameConfig = vi.fn().mockResolvedValue({ schemaVersion: 1, games: { [identity]: disabled } });

    await expect(
      selectTrainerPath(client(setRelayGameConfig), identity, current, "/home/deck/new.exe"),
    ).resolves.toEqual({
      status: "persisted_disabled",
      config: disabled,
    });
    expect(setRelayGameConfig).toHaveBeenCalledWith({ identity, config: disabled });
  });

  it("requires a trainer path and no legacy migration before enabling", async () => {
    const setRelayGameConfig = vi.fn();
    const rpc = client(setRelayGameConfig);

    await expect(
      enableTrainerRelay(rpc, identity, { ...current, trainerPath: "" }, { status: "none" }),
    ).resolves.toEqual({ status: "blocked", diagnostic: "trainer_required" });
    await expect(enableTrainerRelay(rpc, identity, current, { status: "blocked" })).resolves.toEqual({
      status: "blocked",
      diagnostic: "migration_required",
    });
    expect(setRelayGameConfig).not.toHaveBeenCalled();
  });

  it("accepts enablement only after the backend echoes the exact enabled config", async () => {
    const enabled = { ...current, enabled: true };
    const setRelayGameConfig = vi.fn().mockResolvedValue({ schemaVersion: 1, games: { [identity]: enabled } });

    await expect(
      enableTrainerRelay(client(setRelayGameConfig), identity, current, { status: "none" }),
    ).resolves.toEqual({
      status: "enabled",
      config: enabled,
    });
  });

  it("keeps disable fail-closed when backend persistence fails", async () => {
    const setRelayGameConfig = vi.fn().mockRejectedValue(new Error("private backend detail"));

    await expect(disableTrainerRelay(client(setRelayGameConfig), identity, current)).resolves.toEqual({
      status: "failed",
      config: { ...current, enabled: false },
      diagnostic: "persistence_failed",
    });
  });
});
