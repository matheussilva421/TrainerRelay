import type {
  CreateRadialLayoutRequest,
  SelectedLayoutSnapshot,
  SteamInputAdapterDependencies,
  SteamInputCapabilityResult,
  SteamInputLayoutAdapter,
  SteamInputLayoutCreationResult,
  SteamInputMethodShape,
  SteamInputPrimitiveType,
  SteamInputProbeObservation,
} from "../../domain/steamInput/types";
import { fingerprintSteamInputShape, SteamInputFingerprintError } from "./runtimeFingerprint";

interface ReadOnlySteamInputApi {
  GetConfigForAppAndController(appId: number, controllerIndex: 0): unknown | Promise<unknown>;
}

interface SteamAppApi {
  ShowControllerConfigurator(appId: number): unknown | Promise<unknown>;
}

const methodNames = {
  getConfig: "GetConfigForAppAndController",
  exportConfig: "ExportCurrentControllerConfiguration",
  startEditing: "StartEditingControllerConfigurationForAppIDAndControllerIndex",
  saveEditing: "SaveEditingControllerConfiguration",
  stopEditing: "StopEditingControllerConfiguration",
  setActionSet: "SetEditingControllerConfigurationActionSet",
  setActivator: "SetEditingControllerConfigurationInputActivator",
  setBinding: "SetEditingControllerConfigurationInputBinding",
  setSourceMode: "SetEditingControllerConfigurationSourceMode",
  setSelected: "SetSelectedConfigForApp",
  showConfigurator: "ShowControllerConfigurator",
} as const;

const unavailableDiagnostics = new Set([
  "invalid_app_id",
  "steam_input_method_unavailable",
  "read_failed",
  "unsupported_controller",
  "unknown_response_shape",
  "fingerprint_failed",
]);

export class SteamInputAdapterError extends Error {
  constructor(readonly code: string) {
    super(code);
    this.name = "SteamInputAdapterError";
  }
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const hasMethod = (value: unknown, name: string): boolean => isRecord(value) && typeof value[name] === "function";

const positiveSafeAppId = (value: number): number => {
  if (!Number.isSafeInteger(value) || value <= 0) throw new SteamInputAdapterError("invalid_app_id");
  return value;
};

const primitiveTypeOf = (value: unknown): SteamInputPrimitiveType | undefined => {
  if (value === null) return "null";
  const type = typeof value;
  if (
    type === "string" ||
    type === "number" ||
    type === "boolean" ||
    type === "bigint" ||
    type === "symbol" ||
    type === "undefined"
  )
    return type;
  return undefined;
};

const methodShapeFor = (input: unknown, app: unknown, response: Record<string, unknown>): SteamInputMethodShape => {
  const responsePrimitiveKeys: string[] = [];
  const responsePrimitiveTypes: Record<string, SteamInputPrimitiveType> = {};
  for (const [key, value] of Object.entries(response)) {
    const type = primitiveTypeOf(value);
    if (type === undefined) continue;
    if (key.length < 1 || key.length > 128 || !/^[A-Za-z0-9_.-]+$/.test(key))
      throw new SteamInputAdapterError("unknown_response_shape");
    if (responsePrimitiveKeys.length >= 64) throw new SteamInputAdapterError("unknown_response_shape");
    responsePrimitiveKeys.push(key);
    responsePrimitiveTypes[key] = type;
  }
  return {
    getConfig: hasMethod(input, methodNames.getConfig),
    exportConfig: hasMethod(input, methodNames.exportConfig),
    startEditing: hasMethod(input, methodNames.startEditing),
    saveEditing: hasMethod(input, methodNames.saveEditing),
    stopEditing: hasMethod(input, methodNames.stopEditing),
    setActionSet: hasMethod(input, methodNames.setActionSet),
    setActivator: hasMethod(input, methodNames.setActivator),
    setBinding: hasMethod(input, methodNames.setBinding),
    setSourceMode: hasMethod(input, methodNames.setSourceMode),
    setSelected: hasMethod(input, methodNames.setSelected),
    showConfigurator: hasMethod(app, methodNames.showConfigurator),
    responsePrimitiveKeys,
    responsePrimitiveTypes,
    controllerClassification: "steam_deck_builtin",
  };
};

const probeObservationFor = (shape: SteamInputMethodShape): SteamInputProbeObservation => ({
  methodShape: {
    getConfig: shape.getConfig,
    exportConfig: shape.exportConfig,
    startEditing: shape.startEditing,
    saveEditing: shape.saveEditing,
    setSelected: shape.setSelected,
    showConfigurator: shape.showConfigurator,
  },
  responsePrimitiveKeys: [...shape.responsePrimitiveKeys],
});

const boundedIdentifier = (value: unknown, code: string): string => {
  if (
    typeof value !== "string" ||
    value.length < 1 ||
    value.length > 256 ||
    !/^[A-Za-z0-9][A-Za-z0-9._:/-]*$/.test(value)
  )
    throw new SteamInputAdapterError(code);
  return value;
};

const boundedName = (value: unknown): string => {
  if (
    typeof value !== "string" ||
    value.length < 1 ||
    value.length > 120 ||
    value.trim() !== value ||
    Array.from(value).some((character) => {
      const codePoint = character.codePointAt(0) ?? 0;
      return codePoint <= 31 || (codePoint >= 0x7f && codePoint <= 0x9f);
    })
  )
    throw new SteamInputAdapterError("unknown_response_shape");
  return value;
};

const responseToSnapshot = async (
  appId: number,
  input: unknown,
  app: unknown,
  digest: SteamInputAdapterDependencies["digest"],
  response: unknown,
): Promise<{ snapshot: SelectedLayoutSnapshot; observation: SteamInputProbeObservation }> => {
  if (!isRecord(response)) throw new SteamInputAdapterError("unknown_response_shape");
  if (
    typeof response.controller_type !== "string" ||
    typeof response.url !== "string" ||
    typeof response.name !== "string"
  )
    throw new SteamInputAdapterError("unknown_response_shape");
  if (response.controller_type !== "neptune") throw new SteamInputAdapterError("unsupported_controller");

  const shape = methodShapeFor(input, app, response);
  let runtimeFingerprint: string;
  try {
    runtimeFingerprint = await fingerprintSteamInputShape(shape, digest);
  } catch (error) {
    if (error instanceof SteamInputAdapterError) throw error;
    if (error instanceof SteamInputFingerprintError) throw new SteamInputAdapterError("fingerprint_failed");
    throw new SteamInputAdapterError("fingerprint_failed");
  }
  return {
    snapshot: {
      appId,
      controllerIndex: 0,
      controller: "steam_deck_builtin",
      sourceLayoutId: boundedIdentifier(response.url, "unknown_response_shape"),
      sourceLayoutName: boundedName(response.name),
      runtimeFingerprint,
    },
    observation: probeObservationFor(shape),
  };
};

const readSelectedLayout = async (
  appId: number,
  input: unknown,
  app: unknown,
  digest: SteamInputAdapterDependencies["digest"],
): Promise<{ snapshot: SelectedLayoutSnapshot; observation: SteamInputProbeObservation }> => {
  positiveSafeAppId(appId);
  if (!hasMethod(input, methodNames.getConfig)) throw new SteamInputAdapterError("steam_input_method_unavailable");
  const api = input as ReadOnlySteamInputApi;
  let response: unknown;
  try {
    response = await api.GetConfigForAppAndController(appId, 0);
  } catch {
    throw new SteamInputAdapterError("read_failed");
  }
  return responseToSnapshot(appId, input, app, digest, response);
};

const diagnosticFor = (error: unknown): string => {
  if (error instanceof SteamInputAdapterError && unavailableDiagnostics.has(error.code)) return error.code;
  return "probe_failed";
};

export const createSteamInputLayoutAdapter = (
  dependencies: SteamInputAdapterDependencies,
): SteamInputLayoutAdapter => ({
  async probe(appId): Promise<SteamInputCapabilityResult> {
    try {
      const result = await readSelectedLayout(appId, dependencies.input, dependencies.app, dependencies.digest);
      return {
        status: "readonly",
        ...result,
      };
    } catch (error) {
      return { status: "unavailable", diagnostic: diagnosticFor(error) };
    }
  },

  async inspectSelectedLayout(appId): Promise<SelectedLayoutSnapshot> {
    return (await readSelectedLayout(appId, dependencies.input, dependencies.app, dependencies.digest)).snapshot;
  },

  async createSeparateLayout(_request: CreateRadialLayoutRequest): Promise<SteamInputLayoutCreationResult> {
    return { status: "unsupported_runtime", diagnostic: "steam_input_runtime_not_validated" };
  },

  async openConfigurator(appId): Promise<void> {
    positiveSafeAppId(appId);
    if (!hasMethod(dependencies.app, methodNames.showConfigurator))
      throw new SteamInputAdapterError("steam_input_method_unavailable");
    try {
      await (dependencies.app as SteamAppApi).ShowControllerConfigurator(appId);
    } catch {
      throw new SteamInputAdapterError("configurator_open_failed");
    }
  },
});
