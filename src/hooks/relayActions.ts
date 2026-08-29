import type { LegacyMigrationPlan } from "../domain/relay/migration";
import type { LaunchIdentity, RelayGameConfig } from "../domain/relay/types";
import { persistRelayGameConfig, type RelayRpcClient } from "../infra/relayRpc";

export type RelayActionResult =
  | { status: "persisted_disabled"; config: RelayGameConfig }
  | { status: "enabled"; config: RelayGameConfig }
  | { status: "disabled"; config: RelayGameConfig }
  | { status: "blocked"; diagnostic: "trainer_required" | "migration_required" }
  | { status: "failed"; config: RelayGameConfig; diagnostic: "persistence_failed" };

const isTrainerPath = (path: string): boolean =>
  (path.startsWith("/") || /^[A-Za-z]:[\\/]/.test(path)) && path.toLocaleLowerCase().endsWith(".exe");

const disabledConfig = (config: RelayGameConfig, trainerPath = config.trainerPath): RelayGameConfig => ({
  enabled: false,
  trainerPath,
  ...(config.prefixOverride === undefined ? {} : { prefixOverride: config.prefixOverride }),
});

export const selectTrainerPath = async (
  rpc: RelayRpcClient,
  identity: LaunchIdentity,
  current: RelayGameConfig,
  trainerPath: string,
): Promise<RelayActionResult> => {
  const config = disabledConfig(current, trainerPath);
  try {
    return { status: "persisted_disabled", config: await persistRelayGameConfig(rpc, identity, config) };
  } catch {
    return { status: "failed", config, diagnostic: "persistence_failed" };
  }
};

export const enableTrainerRelay = async (
  rpc: RelayRpcClient,
  identity: LaunchIdentity,
  config: RelayGameConfig,
  migration: LegacyMigrationPlan,
): Promise<RelayActionResult> => {
  if (!isTrainerPath(config.trainerPath)) return { status: "blocked", diagnostic: "trainer_required" };
  if (migration.status !== "none") return { status: "blocked", diagnostic: "migration_required" };
  const enabled = { ...config, enabled: true };
  try {
    return { status: "enabled", config: await persistRelayGameConfig(rpc, identity, enabled) };
  } catch {
    return { status: "failed", config: disabledConfig(config), diagnostic: "persistence_failed" };
  }
};

export const disableTrainerRelay = async (
  rpc: RelayRpcClient,
  identity: LaunchIdentity,
  config: RelayGameConfig,
): Promise<RelayActionResult> => {
  const disabled = disabledConfig(config);
  try {
    return { status: "disabled", config: await persistRelayGameConfig(rpc, identity, disabled) };
  } catch {
    return { status: "failed", config: disabled, diagnostic: "persistence_failed" };
  }
};
