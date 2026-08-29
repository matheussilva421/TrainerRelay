import type { LaunchIdentity, RelayGameConfig } from "../domain/relay/types";
import { persistRelayGameConfig, type RelayRpcClient } from "../infra/relayRpc";
import {
  type LegacyMigrationVerificationDependencies,
  type LegacyMigrationVerificationResult,
  verifyLegacyMigration,
} from "./migrationVerification";

export type LegacyMigrationActivationResult =
  | { status: "enabled"; config: RelayGameConfig }
  | {
      status: "verification_failed";
      config: RelayGameConfig;
      verification: Exclude<LegacyMigrationVerificationResult, { status: "verified" }>;
    }
  | { status: "failed"; config: RelayGameConfig; diagnostic: "persistence_failed" };

export interface LegacyMigrationActivationDependencies {
  rpc: RelayRpcClient;
  identity: LaunchIdentity;
  current: RelayGameConfig;
  trainerPath: string;
  verification: LegacyMigrationVerificationDependencies;
  verify?: typeof verifyLegacyMigration;
}

const migratedConfig = (current: RelayGameConfig, trainerPath: string, enabled: boolean): RelayGameConfig => ({
  enabled,
  trainerPath,
  ...(current.prefixOverride === undefined ? {} : { prefixOverride: current.prefixOverride }),
});

export const activateVerifiedLegacyMigration = async (
  dependencies: LegacyMigrationActivationDependencies,
): Promise<LegacyMigrationActivationResult> => {
  const disabled = migratedConfig(dependencies.current, dependencies.trainerPath, false);
  try {
    await persistRelayGameConfig(dependencies.rpc, dependencies.identity, disabled);
  } catch {
    return { status: "failed", config: disabled, diagnostic: "persistence_failed" };
  }

  const verification = await (dependencies.verify ?? verifyLegacyMigration)(dependencies.verification);
  if (verification.status !== "verified") {
    return { status: "verification_failed", config: disabled, verification };
  }

  const enabled = migratedConfig(dependencies.current, dependencies.trainerPath, true);
  try {
    return {
      status: "enabled",
      config: await persistRelayGameConfig(dependencies.rpc, dependencies.identity, enabled),
    };
  } catch {
    return { status: "failed", config: disabled, diagnostic: "persistence_failed" };
  }
};
