import type { LaunchIdentity, RelayConfigV1, RelayGameConfig } from "./types";

const emptyConfig = (): RelayConfigV1 => ({ schemaVersion: 1, games: {} });
const identityPattern = /^(epic|gog):[^\s:]+$/;

const isAbsoluteLooking = (value: string): boolean => value.startsWith("/") || /^[A-Za-z]:[\\/]/.test(value);

const isGameConfig = (value: unknown): value is RelayGameConfig => {
  if (!value || typeof value !== "object") return false;
  const game = value as Record<string, unknown>;
  if (typeof game.enabled !== "boolean" || typeof game.trainerPath !== "string") return false;
  if (!isAbsoluteLooking(game.trainerPath) || !game.trainerPath.toLocaleLowerCase().endsWith(".exe")) return false;
  if (
    game.prefixOverride !== undefined &&
    (typeof game.prefixOverride !== "string" || !isAbsoluteLooking(game.prefixOverride))
  ) {
    return false;
  }
  return true;
};

const copyGameConfig = (game: RelayGameConfig): RelayGameConfig => ({
  enabled: game.enabled,
  trainerPath: game.trainerPath,
  ...(game.prefixOverride === undefined ? {} : { prefixOverride: game.prefixOverride }),
});

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const parseInput = (value: unknown): unknown => {
  if (typeof value !== "string") return value;
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return undefined;
  }
};

export const decodeRelayConfig = (input: unknown): RelayConfigV1 => {
  const value = parseInput(input);
  if (!isRecord(value) || value.schemaVersion !== 1 || !isRecord(value.games)) return emptyConfig();

  const games: Partial<Record<LaunchIdentity, RelayGameConfig>> = {};
  for (const [identity, game] of Object.entries(value.games)) {
    if (identityPattern.test(identity) && isGameConfig(game)) {
      games[identity as LaunchIdentity] = copyGameConfig(game);
    }
  }
  return { schemaVersion: 1, games };
};

export const getRelayGameConfig = (config: RelayConfigV1, identity: LaunchIdentity): RelayGameConfig | undefined => {
  const game = config.games[identity];
  return game ? copyGameConfig(game) : undefined;
};

export const upsertRelayGameConfig = (
  config: RelayConfigV1,
  identity: LaunchIdentity,
  game: RelayGameConfig,
): RelayConfigV1 => ({
  schemaVersion: 1,
  games: { ...config.games, [identity]: copyGameConfig(game) },
});

export const removeRelayGameConfig = (config: RelayConfigV1, identity: LaunchIdentity): RelayConfigV1 => {
  const { [identity]: _removed, ...games } = config.games;
  return { schemaVersion: 1, games };
};
