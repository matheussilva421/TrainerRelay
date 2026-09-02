import type { Sha256Digest, SteamInputMethodShape, SteamInputPrimitiveType } from "../../domain/steamInput/types";

export class SteamInputFingerprintError extends Error {
  constructor(readonly code: string) {
    super(code);
    this.name = "SteamInputFingerprintError";
  }
}

const primitiveTypes = new Set<SteamInputPrimitiveType>([
  "string",
  "number",
  "boolean",
  "bigint",
  "symbol",
  "undefined",
  "null",
]);
const responseKeyPattern = /^[A-Za-z0-9_.-]{1,128}$/;
const methodKeys = [
  "getConfig",
  "exportConfig",
  "startEditing",
  "saveEditing",
  "stopEditing",
  "setActionSet",
  "setActivator",
  "setBinding",
  "setSourceMode",
  "setSelected",
  "showConfigurator",
] as const;

const isPrimitiveType = (value: string): value is SteamInputPrimitiveType =>
  primitiveTypes.has(value as SteamInputPrimitiveType);

const canonicalShape = (shape: SteamInputMethodShape): string => {
  if (
    methodKeys.some((key) => typeof shape[key] !== "boolean") ||
    !Array.isArray(shape.responsePrimitiveKeys) ||
    shape.responsePrimitiveKeys.length > 64 ||
    shape.responsePrimitiveKeys.some((key) => typeof key !== "string" || !responseKeyPattern.test(key)) ||
    new Set(shape.responsePrimitiveKeys).size !== shape.responsePrimitiveKeys.length
  )
    throw new SteamInputFingerprintError("invalid_runtime_shape");

  const responsePrimitiveKeys = [...shape.responsePrimitiveKeys].sort();
  const responsePrimitiveTypes = shape.responsePrimitiveTypes;
  if (
    shape.controllerClassification !== undefined &&
    shape.controllerClassification !== "steam_deck_builtin" &&
    shape.controllerClassification !== "unknown"
  )
    throw new SteamInputFingerprintError("invalid_runtime_shape");
  if (
    typeof responsePrimitiveTypes !== "object" ||
    responsePrimitiveTypes === null ||
    Array.isArray(responsePrimitiveTypes) ||
    Object.keys(responsePrimitiveTypes).length !== responsePrimitiveKeys.length ||
    Object.keys(responsePrimitiveTypes).some(
      (key) =>
        !responsePrimitiveKeys.includes(key) ||
        typeof responsePrimitiveTypes[key] !== "string" ||
        !isPrimitiveType(responsePrimitiveTypes[key]),
    )
  )
    throw new SteamInputFingerprintError("invalid_runtime_shape");

  return JSON.stringify({
    schemaVersion: 1,
    controller: shape.controllerClassification ?? "unknown",
    methods: Object.fromEntries(methodKeys.map((key) => [key, shape[key]])),
    responsePrimitiveKeys,
    responsePrimitiveTypes: Object.fromEntries(responsePrimitiveKeys.map((key) => [key, responsePrimitiveTypes[key]])),
  });
};

export const fingerprintSteamInputShape = async (
  shape: SteamInputMethodShape,
  digest: Sha256Digest,
): Promise<string> => {
  const result = await digest(new TextEncoder().encode(canonicalShape(shape)));
  if (result.length !== 32) throw new SteamInputFingerprintError("invalid_sha256_digest");
  return Array.from(result, (byte) => byte.toString(16).padStart(2, "0")).join("");
};
