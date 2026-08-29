import { describe, expect, it, vi } from "vitest";

vi.mock("@decky/api", () => ({ callable: () => async () => undefined }));

import type { LaunchIdentity, RelayGameConfig } from "../src/domain/relay/types";
import { activateVerifiedLegacyMigration } from "../src/hooks/legacyMigrationActivation";
import type { LegacyMigrationVerificationResult } from "../src/hooks/migrationVerification";
import type { RelayRpcClient } from "../src/infra/relayRpc";

const identity: LaunchIdentity = "epic:game-1";
const current: RelayGameConfig = {
  enabled: true,
  trainerPath: "/home/deck/old.exe",
  prefixOverride: "/home/deck/custom-prefix",
};
const migratedDisabled: RelayGameConfig = {
  enabled: false,
  trainerPath: "/home/deck/migrated.exe",
  prefixOverride: "/home/deck/custom-prefix",
};
const migratedEnabled: RelayGameConfig = { ...migratedDisabled, enabled: true };

const client = (setRelayGameConfig: RelayRpcClient["setRelayGameConfig"]): RelayRpcClient => ({
  getRelayConfig: vi.fn(),
  setRelayGameConfig,
  getRelayStatus: vi.fn(),
  retryRelay: vi.fn(),
});

const echoed = (config: RelayGameConfig) => ({ schemaVersion: 1 as const, games: { [identity]: config } });

describe("verified legacy migration activation", () => {
  it("persists disabled before verification and enables only after a verified snapshot", async () => {
    const calls: string[] = [];
    const setRelayGameConfig = vi.fn(async ({ config }: { config: RelayGameConfig | null }) => {
      if (!config) throw new Error("unexpected removal");
      calls.push(config.enabled ? "enabled" : "disabled");
      return echoed(config);
    });
    const verify = vi.fn(async () => {
      calls.push("verified");
      return { status: "verified", identity } satisfies LegacyMigrationVerificationResult;
    });

    await expect(
      activateVerifiedLegacyMigration({
        rpc: client(setRelayGameConfig),
        identity,
        current,
        trainerPath: "/home/deck/migrated.exe",
        verification: {} as never,
        verify,
      }),
    ).resolves.toEqual({ status: "enabled", config: migratedEnabled });
    expect(calls).toEqual(["disabled", "verified", "enabled"]);
  });

  it("keeps the persisted configuration disabled when verification fails", async () => {
    const setRelayGameConfig = vi.fn(async ({ config }: { config: RelayGameConfig | null }) => {
      if (!config) throw new Error("unexpected removal");
      return echoed(config);
    });
    const verification = {
      status: "mismatch",
      identity,
      diagnostic: "launch_options_mismatch",
    } satisfies LegacyMigrationVerificationResult;

    await expect(
      activateVerifiedLegacyMigration({
        rpc: client(setRelayGameConfig),
        identity,
        current,
        trainerPath: "/home/deck/migrated.exe",
        verification: {} as never,
        verify: vi.fn().mockResolvedValue(verification),
      }),
    ).resolves.toEqual({ status: "verification_failed", config: migratedDisabled, verification });
    expect(setRelayGameConfig).toHaveBeenCalledTimes(1);
  });

  it("does not edit launch options when disabling cannot be persisted", async () => {
    const verify = vi.fn();
    await expect(
      activateVerifiedLegacyMigration({
        rpc: client(vi.fn().mockRejectedValue(new Error("backend detail"))),
        identity,
        current,
        trainerPath: "/home/deck/migrated.exe",
        verification: {} as never,
        verify,
      }),
    ).resolves.toEqual({ status: "failed", config: migratedDisabled, diagnostic: "persistence_failed" });
    expect(verify).not.toHaveBeenCalled();
  });

  it("leaves the backend disabled if the final enable write fails", async () => {
    const setRelayGameConfig = vi
      .fn()
      .mockResolvedValueOnce(echoed(migratedDisabled))
      .mockRejectedValueOnce(new Error("backend detail"));

    await expect(
      activateVerifiedLegacyMigration({
        rpc: client(setRelayGameConfig),
        identity,
        current,
        trainerPath: "/home/deck/migrated.exe",
        verification: {} as never,
        verify: vi.fn().mockResolvedValue({ status: "verified", identity }),
      }),
    ).resolves.toEqual({ status: "failed", config: migratedDisabled, diagnostic: "persistence_failed" });
    expect(setRelayGameConfig).toHaveBeenCalledTimes(2);
  });
});
