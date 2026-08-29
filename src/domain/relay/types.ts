export type LaunchIdentity = `epic:${string}` | `gog:${string}`;

export interface RelayGameConfig {
  enabled: boolean;
  trainerPath: string;
  prefixOverride?: string;
}

export interface RelayConfigV1 {
  schemaVersion: 1;
  games: Partial<Record<LaunchIdentity, RelayGameConfig>>;
}

export type RelayStatus =
  | "disabled"
  | "waiting_for_game"
  | "launching"
  | "running"
  | "retrying"
  | "failed"
  | "ambiguous"
  | "invalid_config";
