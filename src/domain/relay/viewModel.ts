import type { RelayStatusPayload } from "../../infra/relayRpc";
import { type LegacyMigrationPlan, planLegacyMigration } from "./migration";
import { classifyShortcut } from "./shortcut";
import type { LaunchIdentity, RelayGameConfig, RelayStatus } from "./types";

export const TRAINER_RELAY_REPOSITORY = "https://github.com/matheussilva421/TrainerRelay";

export interface RelayAppDetailsSnapshot {
  command: string;
  launchOptions: string;
}

export type TrainerRelayDetailsState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; snapshot: RelayAppDetailsSnapshot };

export interface RelayStatusViewModel {
  state: RelayStatus;
  diagnosticCode: string | null;
}

export type TrainerRelayViewModel =
  | { kind: "loading"; heading: "Trainer Relay"; message: "Reading shortcut details…" }
  | { kind: "error"; heading: "Trainer Relay"; message: "Shortcut details are unavailable. Nothing can be changed." }
  | {
      kind: "unsupported";
      heading: "Trainer Relay";
      message: "This shortcut is not a recognised UniFiDeck Epic/GOG launch.";
      repositoryUrl: string;
    }
  | {
      kind: "supported";
      heading: "Trainer Relay";
      identity: LaunchIdentity;
      migration: LegacyMigrationPlan;
      controls: { browse: boolean; enable: boolean; retry: boolean };
      status: RelayStatusViewModel;
      config?: RelayGameConfig;
    };

const safeDiagnostic = (code: string | undefined): string | null =>
  code !== undefined && /^[a-z0-9_]{1,32}$/.test(code) ? code : code === undefined ? null : "status_unavailable";

const statusViewModel = (identity: LaunchIdentity, status: RelayStatusPayload | undefined): RelayStatusViewModel => {
  if (!status || status.identity !== identity) return { state: "disabled", diagnosticCode: null };
  return { state: status.state, diagnosticCode: safeDiagnostic(status.diagnostic?.code) };
};

export const buildTrainerRelayViewModel = (
  details: TrainerRelayDetailsState,
  config?: RelayGameConfig,
  relayStatus?: RelayStatusPayload,
): TrainerRelayViewModel => {
  if (details.status === "loading")
    return { kind: "loading", heading: "Trainer Relay", message: "Reading shortcut details…" };
  if (details.status === "error") {
    return {
      kind: "error",
      heading: "Trainer Relay",
      message: "Shortcut details are unavailable. Nothing can be changed.",
    };
  }

  const identity = classifyShortcut(details.snapshot.command, details.snapshot.launchOptions);
  if (!identity) {
    return {
      kind: "unsupported",
      heading: "Trainer Relay",
      message: "This shortcut is not a recognised UniFiDeck Epic/GOG launch.",
      repositoryUrl: TRAINER_RELAY_REPOSITORY,
    };
  }

  const migration = planLegacyMigration(details.snapshot.launchOptions);
  const migrationClear = migration.status === "none";
  return {
    kind: "supported",
    heading: "Trainer Relay",
    identity,
    migration,
    controls: {
      browse: true,
      enable: Boolean(config?.enabled) || (migrationClear && Boolean(config?.trainerPath)),
      retry: relayStatus?.state === "failed",
    },
    status: statusViewModel(identity, relayStatus),
    ...(config === undefined ? {} : { config }),
  };
};

export const formatRelayStatus = (status: RelayStatusViewModel): string =>
  status.diagnosticCode ? `${status.state} (${status.diagnosticCode})` : status.state;
