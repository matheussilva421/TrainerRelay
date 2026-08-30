import { callable } from "@decky/api";

import type {
  DiagnosticCategory,
  DiagnosticClearResponse,
  DiagnosticDetailValue,
  DiagnosticEvent,
  DiagnosticEventsRequest,
  DiagnosticEventsResponse,
  DiagnosticExportResponse,
  DiagnosticOutcome,
  DiagnosticSettingsResponse,
} from "../domain/diagnostics/types";
import type { LaunchIdentity } from "../domain/relay/types";

export class DiagnosticRpcError extends Error {
  constructor(readonly code: "invalid_diagnostic_response" | "diagnostic_rpc_failed") {
    super(code);
    this.name = "DiagnosticRpcError";
  }
}

export interface DiagnosticRpcClient {
  getDiagnosticSettings: () => Promise<DiagnosticSettingsResponse>;
  setDiagnosticsEnabled: (enabled: boolean) => Promise<DiagnosticSettingsResponse>;
  getDiagnosticEvents: (request?: DiagnosticEventsRequest) => Promise<DiagnosticEventsResponse>;
  exportDiagnostics: () => Promise<DiagnosticExportResponse>;
  clearDiagnostics: () => Promise<DiagnosticClearResponse>;
}

export interface DiagnosticRpcTransport {
  getDiagnosticSettings: () => Promise<unknown>;
  setDiagnosticsEnabled: (request: { enabled: boolean }) => Promise<unknown>;
  getDiagnosticEvents: (request: DiagnosticEventsRequest) => Promise<unknown>;
  exportDiagnostics: () => Promise<unknown>;
  clearDiagnostics: () => Promise<unknown>;
}

const categories = new Set<DiagnosticCategory>(["config", "games_map", "process", "umu", "trainer", "lifecycle"]);
const outcomes = new Set<DiagnosticOutcome>(["info", "accepted", "rejected", "warning", "error"]);
const safeCode = /^[a-z0-9_]{1,64}$/;
const identityPattern = /^(epic|gog):[^\s:]+$/;
const timestampPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/;
const cursorPattern = /^v1:[1-9]\d*:(0|[1-9]\d*)$/;
const forbiddenDetailKey = /(token|secret|password|cookie|authorization|credential)/i;

const detailKeys: Readonly<Record<string, readonly string[]>> = {
  diagnostic_mode_changed: ["enabled"],
  plugin_loaded: ["version"],
  plugin_unloaded: ["version"],
  config_loaded: ["game_count"],
  config_persisted: ["game_count", "enabled", "trainer_path", "prefix_override"],
  games_map_loaded: ["entry_count", "map_path", "expected_executable"],
  games_map_rejected: ["reason", "map_path"],
  prefix_selected: ["source", "expected_prefix"],
  process_scan_summary: [
    "process_count",
    "readable_count",
    "relevant_count",
    "accepted_count",
    "proc_entry_unreadable_count",
    "pid_reused_during_scan_count",
    "missing_required_environment_count",
    "game_id_mismatch_count",
    "process_name_mismatch_count",
    "store_mismatch_count",
    "prefix_mismatch_count",
    "executable_mismatch_count",
    "legacy_settings_present_count",
  ],
  candidate_rejected: [
    "reason",
    "expected_executable",
    "observed_executable",
    "expected_prefix",
    "observed_prefix",
    "game_id",
    "process_name",
    "store",
    "wineprefix",
    "protonpath",
  ],
  candidate_accepted: [
    "expected_executable",
    "observed_executable",
    "expected_prefix",
    "observed_prefix",
    "game_id",
    "process_name",
    "store",
    "wineprefix",
    "protonpath",
  ],
  umu_resolved: ["source", "umu_path"],
  umu_rejected: ["reason"],
  trainer_spawned: ["trainer_path", "process_group_id"],
  trainer_spawn_failed: ["trainer_path", "reason"],
  trainer_running: ["trainer_path", "elapsed_ms"],
  trainer_exited: ["trainer_path", "exit_code", "elapsed_ms"],
  trainer_retry_scheduled: ["retry_count", "delay_ms"],
  trainer_manual_retry: ["retry_count"],
  session_changed: ["previous_pid", "previous_start_time"],
  session_ended: [],
  owned_group_signal: ["process_group_id", "signal", "forced"],
  event_repeated: ["repeated_event", "count", "elapsed_ms"],
};

const invalid = (): never => {
  throw new DiagnosticRpcError("invalid_diagnostic_response");
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const hasOnlyKeys = (value: Record<string, unknown>, allowed: readonly string[]): boolean =>
  Object.keys(value).every((key) => allowed.includes(key));

const parseInput = (input: unknown): unknown => {
  if (typeof input !== "string") return input;
  try {
    return JSON.parse(input) as unknown;
  } catch {
    return invalid();
  }
};

const nonNegativeInteger = (value: unknown): value is number => Number.isInteger(value) && Number(value) >= 0;
const positiveInteger = (value: unknown): value is number => Number.isInteger(value) && Number(value) > 0;

const decodeSettingsBase = (input: unknown, allowGeneration = false): DiagnosticSettingsResponse => {
  const value = parseInput(input);
  const allowedKeys = [
    "settings",
    "bytesUsed",
    "byteLimit",
    "eventCount",
    "storageDiagnostic",
    "lastExportPath",
    ...(allowGeneration ? ["generation"] : []),
  ];
  if (
    !isRecord(value) ||
    !hasOnlyKeys(value, allowedKeys) ||
    !isRecord(value.settings) ||
    !hasOnlyKeys(value.settings, ["schemaVersion", "enabled"]) ||
    value.settings.schemaVersion !== 1 ||
    typeof value.settings.enabled !== "boolean" ||
    !nonNegativeInteger(value.bytesUsed) ||
    value.byteLimit !== 52_428_800 ||
    !nonNegativeInteger(value.eventCount) ||
    !(
      value.storageDiagnostic === null ||
      (typeof value.storageDiagnostic === "string" && safeCode.test(value.storageDiagnostic))
    ) ||
    !(
      value.lastExportPath === null ||
      (typeof value.lastExportPath === "string" && value.lastExportPath.startsWith("/"))
    )
  ) {
    return invalid();
  }
  return {
    settings: { schemaVersion: 1, enabled: value.settings.enabled },
    bytesUsed: value.bytesUsed,
    byteLimit: 52_428_800,
    eventCount: value.eventCount,
    storageDiagnostic: value.storageDiagnostic,
    lastExportPath: value.lastExportPath,
  };
};

export const decodeDiagnosticSettingsResponse = (input: unknown): DiagnosticSettingsResponse =>
  decodeSettingsBase(input);

const decodeDetails = (eventName: string, input: unknown): Readonly<Record<string, DiagnosticDetailValue>> => {
  const allowed = detailKeys[eventName];
  if (!allowed || !isRecord(input) || !hasOnlyKeys(input, allowed)) return invalid();
  const details: Record<string, DiagnosticDetailValue> = {};
  for (const [key, value] of Object.entries(input)) {
    if (forbiddenDetailKey.test(key)) return invalid();
    if (typeof value === "string") {
      if (value.length > 4096) return invalid();
    } else if (!(value === null || typeof value === "boolean" || Number.isInteger(value))) {
      return invalid();
    }
    details[key] = value as DiagnosticDetailValue;
  }
  return details;
};

const decodeEvent = (input: unknown): DiagnosticEvent => {
  if (
    !isRecord(input) ||
    !hasOnlyKeys(input, ["sequence", "timestamp", "identity", "session", "category", "event", "outcome", "details"]) ||
    !positiveInteger(input.sequence) ||
    typeof input.timestamp !== "string" ||
    !timestampPattern.test(input.timestamp) ||
    typeof input.category !== "string" ||
    !categories.has(input.category as DiagnosticCategory) ||
    typeof input.event !== "string" ||
    typeof input.outcome !== "string" ||
    !outcomes.has(input.outcome as DiagnosticOutcome)
  ) {
    return invalid();
  }
  if (input.identity !== undefined && (typeof input.identity !== "string" || !identityPattern.test(input.identity))) {
    return invalid();
  }
  let session: { pid: number; startTime: number } | undefined;
  if (input.session !== undefined) {
    if (
      !isRecord(input.session) ||
      !hasOnlyKeys(input.session, ["pid", "startTime"]) ||
      !positiveInteger(input.session.pid) ||
      !nonNegativeInteger(input.session.startTime)
    ) {
      return invalid();
    }
    session = { pid: input.session.pid, startTime: input.session.startTime };
  }
  const decoded: DiagnosticEvent = {
    sequence: input.sequence,
    timestamp: input.timestamp,
    category: input.category as DiagnosticCategory,
    event: input.event,
    outcome: input.outcome as DiagnosticOutcome,
    details: decodeDetails(input.event, input.details),
  };
  if (input.identity !== undefined)
    (decoded as { identity: LaunchIdentity }).identity = input.identity as LaunchIdentity;
  if (session !== undefined) (decoded as { session: typeof session }).session = session;
  return decoded;
};

export const decodeDiagnosticEventsResponse = (input: unknown): DiagnosticEventsResponse => {
  const value = parseInput(input);
  if (
    !isRecord(value) ||
    !hasOnlyKeys(value, ["generation", "nextCursor", "cursorReset", "events"]) ||
    !positiveInteger(value.generation) ||
    typeof value.nextCursor !== "string" ||
    !cursorPattern.test(value.nextCursor) ||
    typeof value.cursorReset !== "boolean" ||
    !Array.isArray(value.events)
  ) {
    return invalid();
  }
  if (Number(value.nextCursor.split(":")[1]) !== value.generation) return invalid();
  return {
    generation: value.generation,
    nextCursor: value.nextCursor,
    cursorReset: value.cursorReset,
    events: value.events.map(decodeEvent),
  };
};

export const decodeDiagnosticExportResponse = (input: unknown): DiagnosticExportResponse => {
  const value = parseInput(input);
  if (
    !isRecord(value) ||
    !hasOnlyKeys(value, ["path", "bytesWritten"]) ||
    typeof value.path !== "string" ||
    !value.path.startsWith("/") ||
    !nonNegativeInteger(value.bytesWritten)
  ) {
    return invalid();
  }
  return { path: value.path, bytesWritten: value.bytesWritten };
};

const decodeClearResponse = (input: unknown): DiagnosticClearResponse => {
  const value = parseInput(input);
  if (!isRecord(value) || !positiveInteger(value.generation)) return invalid();
  return { ...decodeSettingsBase(value, true), generation: value.generation };
};

const safeCall = async <T>(operation: () => Promise<unknown>, decode: (value: unknown) => T): Promise<T> => {
  try {
    return decode(await operation());
  } catch (error) {
    if (error instanceof DiagnosticRpcError) throw error;
    throw new DiagnosticRpcError("diagnostic_rpc_failed");
  }
};

export const createDiagnosticRpc = (transport: DiagnosticRpcTransport): DiagnosticRpcClient => ({
  getDiagnosticSettings: () => safeCall(transport.getDiagnosticSettings, decodeDiagnosticSettingsResponse),
  setDiagnosticsEnabled: (enabled) =>
    safeCall(() => transport.setDiagnosticsEnabled({ enabled }), decodeDiagnosticSettingsResponse),
  getDiagnosticEvents: (request = {}) => {
    const bounded: DiagnosticEventsRequest = {
      ...(request.cursor === undefined ? {} : { cursor: request.cursor }),
      ...(request.limit === undefined
        ? {}
        : { limit: Number.isFinite(request.limit) ? Math.max(1, Math.min(200, Math.trunc(request.limit))) : 20 }),
    };
    return safeCall(() => transport.getDiagnosticEvents(bounded), decodeDiagnosticEventsResponse);
  },
  exportDiagnostics: () => safeCall(transport.exportDiagnostics, decodeDiagnosticExportResponse),
  clearDiagnostics: () => safeCall(transport.clearDiagnostics, decodeClearResponse),
});

const getDiagnosticSettingsCall = callable<[], unknown>("get_diagnostic_settings");
const setDiagnosticsEnabledCall = callable<[{ enabled: boolean }], unknown>("set_diagnostics_enabled");
const getDiagnosticEventsCall = callable<[DiagnosticEventsRequest], unknown>("get_diagnostic_events");
const exportDiagnosticsCall = callable<[], unknown>("export_diagnostics");
const clearDiagnosticsCall = callable<[], unknown>("clear_diagnostics");

export const diagnosticRpc = createDiagnosticRpc({
  getDiagnosticSettings: () => getDiagnosticSettingsCall(),
  setDiagnosticsEnabled: (request) => setDiagnosticsEnabledCall(request),
  getDiagnosticEvents: (request) => getDiagnosticEventsCall(request),
  exportDiagnostics: () => exportDiagnosticsCall(),
  clearDiagnostics: () => clearDiagnosticsCall(),
});
