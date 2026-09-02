import { decodeLaunchIdentity, decodeTrainerSha256 } from "../cheats/decoder";
import type {
  GeneratedRadialLayoutV1,
  RadialLayoutRegistryV1,
  SelectedLayoutSnapshot,
  SteamInputCapabilityResult,
  SteamInputProbeObservation,
} from "./types";

export class SteamInputDecodeError extends Error {
  constructor(readonly code: string) {
    super(code);
    this.name = "SteamInputDecodeError";
  }
}

const sha256Pattern = /^[0-9a-f]{64}$/;
const capabilityDiagnostics = new Set([
  "invalid_app_id",
  "steam_input_method_unavailable",
  "read_failed",
  "unsupported_controller",
  "unknown_response_shape",
  "fingerprint_failed",
  "probe_failed",
  "unsupported_runtime",
]);
const identifierPattern = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$/;
const timestampPattern = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|\+00:00)$/;

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const exactKeys = (value: Record<string, unknown>, expected: readonly string[]): boolean => {
  const actual = Object.keys(value).sort();
  const sortedExpected = [...expected].sort();
  return actual.length === sortedExpected.length && actual.every((key, index) => key === sortedExpected[index]);
};

const fail = (code: string): never => {
  throw new SteamInputDecodeError(code);
};

const decodeAppId = (value: unknown): number =>
  typeof value === "number" && Number.isSafeInteger(value) && value > 0 ? value : fail("invalid_radial_app_id");

const decodeSha256 = (value: unknown, code: string): string =>
  typeof value === "string" && sha256Pattern.test(value) ? value : fail(code);

const hasControlCharacter = (value: string): boolean =>
  Array.from(value).some((character) => {
    const codePoint = character.codePointAt(0) ?? 0;
    return codePoint <= 31 || (codePoint >= 0x7f && codePoint <= 0x9f);
  });

const decodeIdentifier = (value: unknown, code: string): string =>
  typeof value === "string" && identifierPattern.test(value) && !hasControlCharacter(value) ? value : fail(code);

const decodeName = (value: unknown): string => {
  if (
    typeof value !== "string" ||
    value.length < 1 ||
    value.length > 120 ||
    value.trim() !== value ||
    hasControlCharacter(value)
  )
    return fail("invalid_radial_generated_layout_name");
  return value;
};

const decodeTimestamp = (value: unknown): string => {
  if (typeof value !== "string") return fail("invalid_radial_created_at");
  const match = timestampPattern.exec(value);
  if (match === null) return fail("invalid_radial_created_at");
  const [, year, month, day, hour, minute, second] = match;
  const parsed = new Date(
    Date.UTC(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute), Number(second)),
  );
  if (
    Number.isNaN(parsed.getTime()) ||
    parsed.getUTCFullYear() !== Number(year) ||
    parsed.getUTCMonth() !== Number(month) - 1 ||
    parsed.getUTCDate() !== Number(day) ||
    parsed.getUTCHours() !== Number(hour) ||
    parsed.getUTCMinutes() !== Number(minute) ||
    parsed.getUTCSeconds() !== Number(second)
  )
    return fail("invalid_radial_created_at");
  return value;
};

const decodeSnapshot = (value: unknown): SelectedLayoutSnapshot => {
  if (
    !isRecord(value) ||
    !exactKeys(value, [
      "appId",
      "controllerIndex",
      "controller",
      "sourceLayoutId",
      "sourceLayoutName",
      "runtimeFingerprint",
    ]) ||
    value.controllerIndex !== 0 ||
    value.controller !== "steam_deck_builtin"
  )
    return fail("invalid_steam_input_snapshot");
  return {
    appId: decodeAppId(value.appId),
    controllerIndex: 0,
    controller: "steam_deck_builtin",
    sourceLayoutId: decodeIdentifier(value.sourceLayoutId, "invalid_radial_source_layout_id"),
    sourceLayoutName: decodeName(value.sourceLayoutName),
    runtimeFingerprint: decodeSha256(value.runtimeFingerprint, "invalid_radial_runtime_fingerprint"),
  };
};

const decodeProbeObservation = (value: unknown): SteamInputProbeObservation => {
  if (
    !isRecord(value) ||
    !exactKeys(value, ["methodShape", "responsePrimitiveKeys"]) ||
    !isRecord(value.methodShape) ||
    !exactKeys(value.methodShape, [
      "getConfig",
      "exportConfig",
      "startEditing",
      "saveEditing",
      "setSelected",
      "showConfigurator",
    ]) ||
    Object.values(value.methodShape).some((present) => typeof present !== "boolean") ||
    !Array.isArray(value.responsePrimitiveKeys) ||
    value.responsePrimitiveKeys.length > 64
  )
    return fail("invalid_steam_input_capability");
  const responsePrimitiveKeys: string[] = [];
  for (const key of value.responsePrimitiveKeys) {
    if (
      typeof key !== "string" ||
      key.length < 1 ||
      key.length > 256 ||
      !/^[A-Za-z0-9_.-]+$/.test(key) ||
      responsePrimitiveKeys.includes(key)
    )
      return fail("invalid_steam_input_capability");
    responsePrimitiveKeys.push(key);
  }
  return {
    methodShape: {
      getConfig: value.methodShape.getConfig as boolean,
      exportConfig: value.methodShape.exportConfig as boolean,
      startEditing: value.methodShape.startEditing as boolean,
      saveEditing: value.methodShape.saveEditing as boolean,
      setSelected: value.methodShape.setSelected as boolean,
      showConfigurator: value.methodShape.showConfigurator as boolean,
    },
    responsePrimitiveKeys,
  };
};

export const decodeGeneratedRadialLayout = (value: unknown): GeneratedRadialLayoutV1 => {
  if (
    !isRecord(value) ||
    !exactKeys(value, [
      "appId",
      "identity",
      "trainerSha256",
      "catalogFingerprint",
      "steamRuntimeFingerprint",
      "sourceLayoutId",
      "generatedLayoutId",
      "generatedLayoutName",
      "revision",
      "createdAt",
    ])
  )
    return fail("invalid_radial_layout");

  const sourceLayoutId = decodeIdentifier(value.sourceLayoutId, "invalid_radial_source_layout_id");
  const generatedLayoutId = decodeIdentifier(value.generatedLayoutId, "invalid_radial_generated_layout_id");
  if (sourceLayoutId === generatedLayoutId) return fail("radial_layout_ids_must_differ");
  if (
    typeof value.revision !== "number" ||
    !Number.isSafeInteger(value.revision) ||
    value.revision < 1 ||
    value.revision > 2 ** 31 - 1
  )
    return fail("invalid_radial_revision");

  try {
    return {
      appId: decodeAppId(value.appId),
      identity: decodeLaunchIdentity(value.identity),
      trainerSha256: decodeTrainerSha256(value.trainerSha256),
      catalogFingerprint: decodeSha256(value.catalogFingerprint, "invalid_radial_catalog_fingerprint"),
      steamRuntimeFingerprint: decodeSha256(value.steamRuntimeFingerprint, "invalid_radial_runtime_fingerprint"),
      sourceLayoutId,
      generatedLayoutId,
      generatedLayoutName: decodeName(value.generatedLayoutName),
      revision: value.revision,
      createdAt: decodeTimestamp(value.createdAt),
    };
  } catch (error) {
    if (error instanceof SteamInputDecodeError) throw error;
    return fail("invalid_radial_layout");
  }
};

export const decodeRadialLayoutRegistry = (value: unknown): RadialLayoutRegistryV1 => {
  if (
    !isRecord(value) ||
    !exactKeys(value, ["schemaVersion", "layouts"]) ||
    value.schemaVersion !== 1 ||
    !Array.isArray(value.layouts)
  )
    return fail("invalid_radial_layout_registry");
  if (value.layouts.length > 128) return fail("too_many_radial_layouts");

  const layouts: GeneratedRadialLayoutV1[] = [];
  const generatedIds = new Set<string>();
  const records = new Set<string>();
  for (const candidate of value.layouts) {
    let layout: GeneratedRadialLayoutV1;
    try {
      layout = decodeGeneratedRadialLayout(candidate);
    } catch (error) {
      if (error instanceof SteamInputDecodeError && error.code === "radial_layout_ids_must_differ") throw error;
      return fail("invalid_radial_layout_registry");
    }
    const key = JSON.stringify(layout);
    if (records.has(key) || generatedIds.has(layout.generatedLayoutId)) return fail("duplicate_radial_layout");
    records.add(key);
    generatedIds.add(layout.generatedLayoutId);
    layouts.push(layout);
  }
  return { schemaVersion: 1, layouts };
};

const decodeDiagnostic = (value: unknown): string =>
  typeof value === "string" && capabilityDiagnostics.has(value) ? value : fail("invalid_steam_input_capability");

export const decodeSteamInputCapabilityResult = (value: unknown): SteamInputCapabilityResult => {
  if (!isRecord(value) || typeof value.status !== "string") return fail("invalid_steam_input_capability");
  if (value.status === "unavailable") {
    if (!exactKeys(value, ["status", "diagnostic"])) return fail("invalid_steam_input_capability");
    return { status: "unavailable", diagnostic: decodeDiagnostic(value.diagnostic) };
  }
  if (value.status !== "readonly" && value.status !== "writable") return fail("invalid_steam_input_capability");
  if (!exactKeys(value, ["status", "snapshot", "observation"])) return fail("invalid_steam_input_capability");
  return {
    status: value.status,
    snapshot: decodeSnapshot(value.snapshot),
    observation: decodeProbeObservation(value.observation),
  };
};
