import { callable } from "@decky/api";

import { decodeRelayConfig } from "../domain/relay/config";
import type { LaunchIdentity, RelayConfigV1, RelayGameConfig, RelayStatus } from "../domain/relay/types";

export interface RelayStatusPayload {
  identity: LaunchIdentity;
  state: RelayStatus;
  diagnostic: { code: string } | null;
}

export interface RelayRpcClient {
  getRelayConfig: () => Promise<RelayConfigV1>;
  setRelayGameConfig: (request: { identity: LaunchIdentity; config: RelayGameConfig | null }) => Promise<RelayConfigV1>;
  getRelayStatus: (request: { identity: LaunchIdentity }) => Promise<RelayStatusPayload>;
  retryRelay: (request: { identity: LaunchIdentity }) => Promise<RelayStatusPayload>;
}

export interface RelayRpcTransport {
  getRelayConfig: () => Promise<unknown>;
  setRelayGameConfig: (request: { identity: LaunchIdentity; config: RelayGameConfig | null }) => Promise<unknown>;
  getRelayStatus: (request: { identity: LaunchIdentity }) => Promise<unknown>;
  retryRelay: (request: { identity: LaunchIdentity }) => Promise<unknown>;
}

export class RelayRpcError extends Error {
  constructor(readonly code: "invalid_config") {
    super(code);
    this.name = "RelayRpcError";
  }
}

const statuses = new Set<RelayStatus>([
  "disabled",
  "waiting_for_game",
  "launching",
  "running",
  "retrying",
  "failed",
  "ambiguous",
  "invalid_config",
]);

const safeDiagnosticCode = /^[a-z0-9_]{1,32}$/;

const emptyConfig = (): RelayConfigV1 => ({ schemaVersion: 1, games: {} });

const parseInput = (input: unknown): unknown => {
  if (typeof input !== "string") return input;
  try {
    return JSON.parse(input) as unknown;
  } catch {
    throw new RelayRpcError("invalid_config");
  }
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

export const decodeRelayConfigResponse = (input: unknown): RelayConfigV1 => {
  const value = parseInput(input);
  if (!isRecord(value) || value.schemaVersion !== 1 || !isRecord(value.games)) {
    throw new RelayRpcError("invalid_config");
  }
  return decodeRelayConfig(value);
};

const invalidStatus = (identity: LaunchIdentity, code: string): RelayStatusPayload => ({
  identity,
  state: "invalid_config",
  diagnostic: { code },
});

export const decodeRelayStatusResponse = (identity: LaunchIdentity, input: unknown): RelayStatusPayload => {
  if (!isRecord(input) || input.identity !== identity || typeof input.state !== "string") {
    return invalidStatus(identity, "status_unavailable");
  }
  if (!statuses.has(input.state as RelayStatus)) return invalidStatus(identity, "unknown_status");

  if (input.diagnostic === null || input.diagnostic === undefined) {
    return { identity, state: input.state as RelayStatus, diagnostic: null };
  }
  if (!isRecord(input.diagnostic) || typeof input.diagnostic.code !== "string") {
    return invalidStatus(identity, "status_unavailable");
  }
  const code = input.diagnostic.code;
  return {
    identity,
    state: input.state as RelayStatus,
    diagnostic: { code: safeDiagnosticCode.test(code) ? code : "status_unavailable" },
  };
};

export const createRelayRpc = (transport: RelayRpcTransport): RelayRpcClient => ({
  async getRelayConfig() {
    return decodeRelayConfigResponse(await transport.getRelayConfig());
  },

  async setRelayGameConfig(request) {
    return decodeRelayConfigResponse(await transport.setRelayGameConfig(request));
  },

  async getRelayStatus({ identity }) {
    return decodeRelayStatusResponse(identity, await transport.getRelayStatus({ identity }));
  },

  async retryRelay({ identity }) {
    return decodeRelayStatusResponse(identity, await transport.retryRelay({ identity }));
  },
});

const getRelayConfigCall = callable<[], unknown>("get_relay_config");
const setRelayGameConfigCall = callable<[{ identity: LaunchIdentity; config: RelayGameConfig | null }], unknown>(
  "set_relay_game_config",
);
const getRelayStatusCall = callable<[{ identity: LaunchIdentity }], unknown>("get_relay_status");
const retryRelayCall = callable<[{ identity: LaunchIdentity }], unknown>("retry_relay");

export const relayRpc = createRelayRpc({
  getRelayConfig: () => getRelayConfigCall(),
  setRelayGameConfig: (request) => setRelayGameConfigCall(request),
  getRelayStatus: (request) => getRelayStatusCall(request),
  retryRelay: (request) => retryRelayCall(request),
});

const sameGameConfig = (left: RelayGameConfig | undefined, right: RelayGameConfig): boolean =>
  left?.enabled === right.enabled &&
  left.trainerPath === right.trainerPath &&
  left.prefixOverride === right.prefixOverride;

export const persistRelayGameConfig = async (
  rpc: RelayRpcClient,
  identity: LaunchIdentity,
  config: RelayGameConfig,
): Promise<RelayGameConfig> => {
  const persisted = await rpc.setRelayGameConfig({ identity, config });
  const returned = persisted.games[identity];
  if (!returned || !sameGameConfig(returned, config)) throw new RelayRpcError("invalid_config");
  return { ...returned };
};

export const isRelayConfig = (value: unknown): value is RelayConfigV1 => {
  try {
    decodeRelayConfigResponse(value);
    return true;
  } catch {
    return false;
  }
};

export const emptyRelayConfig = emptyConfig;
