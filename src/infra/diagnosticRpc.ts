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

const categories = new Set<DiagnosticCategory>([
  "config",
  "games_map",
  "process",
  "umu",
  "trainer",
  "lifecycle",
  "command",
  "steam_input",
]);
const outcomes = new Set<DiagnosticOutcome>(["info", "accepted", "rejected", "warning", "error"]);
const safeCode = /^[a-z0-9_]{1,64}$/;
const identityPattern = /^(epic|gog):[^\s:]+$/;
const timestampPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/;
const cursorPattern = /^v1:[1-9]\d*:(0|[1-9]\d*)$/;
const forbiddenDetailKey = /(token|secret|password|cookie|authorization|credential)/i;
const steamInputEvents = new Set(["probe_completed", "preview_created", "authority_changed", "configurator_opened"]);
const steamInputResult = /^[a-z0-9_]{1,64}$/;
const steamInputHashPrefix = /^[0-9a-f]{8,16}$/;
const steamInputCorrelationId = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const commandIdPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const commandCheatIdPattern =
  /^(?:[a-z0-9][a-z0-9._-]{0,127}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/;
const commandReasons = /^[a-z0-9_]{1,64}$/;

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
  candidate_revalidated: [
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
  container_reentry_verified: [
    "bus_name",
    "runtime_variant",
    "attempt_count",
    "bus_source",
    "app_id_source",
    "service_marker_present",
  ],
  container_reentry_rejected: [
    "reason",
    "failure_class",
    "probe_exit_code",
    "bus_source",
    "attempt_count",
    "service_marker_present",
  ],
  container_reentry_confirmed: ["bus_name", "elapsed_ms"],
  container_reentry_confirmation_failed: ["bus_name", "elapsed_ms", "failure_observed", "service_marker_present"],
  umu_exit_diagnostics: [
    "stdout_bytes",
    "stderr_bytes",
    "stdout_truncated",
    "stderr_truncated",
    "stdout_tail",
    "stderr_tail",
    "failure_class",
    "group_member_count",
    "group_member_names",
    "observed_descendant_count",
    "observed_descendant_names",
  ],
  trainer_spawned: [
    "trainer_path",
    "process_group_id",
    "wineprefix",
    "steam_compat_data_path",
    "proton_verb",
    "container_reentry",
    "environment_key_count",
    "runtime_flags",
  ],
  trainer_spawn_failed: ["trainer_path", "reason"],
  trainer_running: ["trainer_path", "elapsed_ms"],
  trainer_exited: ["trainer_path", "exit_code", "elapsed_ms"],
  trainer_retry_scheduled: ["retry_count", "delay_ms"],
  trainer_manual_retry: ["retry_count"],
  session_changed: ["previous_pid", "previous_start_time"],
  session_ended: [],
  owned_group_signal: ["process_group_id", "signal", "forced"],
  event_repeated: ["repeated_event", "count", "elapsed_ms"],
  catalog_loaded: ["adapter_count"],
  catalog_rejected: ["reason"],
  manual_control_added: ["cheat_id", "control_count"],
  manual_control_removed: ["cheat_id", "control_count"],
  command_rejected: ["command_id", "cheat_id", "reason"],
  helper_spawned: ["command_id", "cheat_id", "source"],
  helper_completed: ["command_id", "cheat_id", "source", "outcome", "duration_ms"],
  helper_timeout: ["command_id", "cheat_id"],
  cooperative_acknowledged: ["command_id", "cheat_id", "revision"],
  cooperative_stale: ["command_id", "cheat_id", "revision", "reason"],
  cooperative_descriptor_rejected: ["reason"],
  probe_completed: [
    "app_id",
    "primitive_key_count",
    "runtime_fingerprint_prefix",
    "trainer_hash_prefix",
    "catalog_fingerprint_prefix",
    "source_layout_id_hash_prefix",
    "result_code",
    "correlation_id",
  ],
  preview_created: [
    "app_id",
    "command_count",
    "page_count",
    "skipped_count",
    "trainer_hash_prefix",
    "catalog_fingerprint_prefix",
    "runtime_fingerprint_prefix",
    "source_layout_id_hash_prefix",
    "result_code",
    "correlation_id",
  ],
  authority_changed: [
    "app_id",
    "changed_field_count",
    "trainer_hash_prefix",
    "catalog_fingerprint_prefix",
    "runtime_fingerprint_prefix",
    "source_layout_id_hash_prefix",
    "result_code",
    "correlation_id",
  ],
  configurator_opened: ["app_id", "result_code", "correlation_id"],
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
      const maximumLength =
        eventName === "umu_exit_diagnostics" && ["stdout_tail", "stderr_tail"].includes(key) ? 1024 : 4096;
      if (value.length > maximumLength) return invalid();
    } else if (!(value === null || typeof value === "boolean" || Number.isInteger(value))) {
      return invalid();
    }
    details[key] = value as DiagnosticDetailValue;
  }
  validateCommandDetails(eventName, details);
  validateSteamInputDetails(eventName, details);
  return details;
};

const validateCommandDetails = (eventName: string, details: Readonly<Record<string, DiagnosticDetailValue>>): void => {
  if (["catalog_loaded", "manual_control_added", "manual_control_removed"].includes(eventName)) {
    const count = details.adapter_count ?? details.control_count;
    if (typeof count !== "number" || !Number.isSafeInteger(count) || count < 0 || count > 64) invalid();
  }
  if (["catalog_rejected", "cooperative_descriptor_rejected"].includes(eventName)) {
    if (typeof details.reason !== "string" || !commandReasons.test(details.reason)) invalid();
  }
  if (["command_rejected", "cooperative_stale"].includes(eventName)) {
    const reason = details.reason;
    if (reason !== undefined && (typeof reason !== "string" || !commandReasons.test(reason))) invalid();
    if (eventName === "cooperative_stale" && details.command_id === undefined) return;
  }
  if (
    [
      "command_rejected",
      "helper_spawned",
      "helper_completed",
      "helper_timeout",
      "cooperative_acknowledged",
      "cooperative_stale",
    ].includes(eventName)
  ) {
    if (typeof details.command_id !== "string" || !commandIdPattern.test(details.command_id)) invalid();
    if (typeof details.cheat_id !== "string" || !commandCheatIdPattern.test(details.cheat_id)) invalid();
  }
  if (eventName === "helper_spawned" && !["adapter", "manual", "cooperative"].includes(String(details.source)))
    invalid();
  if (eventName === "helper_completed") {
    if (!["adapter", "manual", "cooperative"].includes(String(details.source))) invalid();
    if (!["requested", "failed", "rejected"].includes(String(details.outcome))) invalid();
    const duration = details.duration_ms;
    if (typeof duration !== "number" || !Number.isSafeInteger(duration) || duration < 0 || duration > 300_000)
      invalid();
  }
  if (["cooperative_acknowledged", "cooperative_stale"].includes(eventName)) {
    const revision = details.revision;
    if (typeof revision !== "number" || !Number.isSafeInteger(revision) || revision < 0) invalid();
  }
};

const validateSteamInputDetails = (
  eventName: string,
  details: Readonly<Record<string, DiagnosticDetailValue>>,
): void => {
  if (!steamInputEvents.has(eventName)) return;
  const correlationId = details.correlation_id;
  if (typeof correlationId !== "string" || !steamInputCorrelationId.test(correlationId)) {
    invalid();
  }
  const appId = details.app_id;
  if (typeof appId !== "number" || !Number.isSafeInteger(appId) || appId < 1) {
    invalid();
  }
  for (const key of ["primitive_key_count", "command_count", "page_count", "skipped_count", "changed_field_count"]) {
    const value = details[key];
    if (value !== undefined && (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0 || value > 64)) {
      invalid();
    }
  }
  for (const key of [
    "runtime_fingerprint_prefix",
    "trainer_hash_prefix",
    "catalog_fingerprint_prefix",
    "source_layout_id_hash_prefix",
  ]) {
    const value = details[key];
    if (value !== undefined && (typeof value !== "string" || !steamInputHashPrefix.test(value))) {
      invalid();
    }
  }
  const resultCode = details.result_code;
  if (resultCode !== undefined && (typeof resultCode !== "string" || !steamInputResult.test(resultCode))) {
    invalid();
  }
  const required: Record<string, readonly string[]> = {
    probe_completed: ["app_id", "primitive_key_count", "runtime_fingerprint_prefix", "result_code"],
    preview_created: ["app_id", "command_count", "page_count", "skipped_count"],
    authority_changed: ["app_id", "changed_field_count", "result_code"],
    configurator_opened: ["app_id", "result_code"],
  };
  if (required[eventName].some((key) => details[key] === undefined)) {
    invalid();
  }
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
