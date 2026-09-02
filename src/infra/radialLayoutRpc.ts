import { callable } from "@decky/api";
import {
  decodeGeneratedRadialLayout,
  decodeRadialLayoutRegistry,
  SteamInputDecodeError,
} from "../domain/steamInput/decoder";
import type {
  GeneratedRadialLayoutV1,
  RadialLayoutRegistryV1,
  SteamInputProbeEventResult,
  SteamInputProbeExportResult,
  SteamInputProbeMetadataEvent,
  SteamInputProbeReport,
} from "../domain/steamInput/types";

export interface RadialLayoutRpcTransport {
  getRegistry: () => Promise<unknown>;
  record: (record: GeneratedRadialLayoutV1) => Promise<unknown>;
  exportProbe: (report: SteamInputProbeReport) => Promise<unknown>;
  recordProbeEvent: (event: SteamInputProbeMetadataEvent) => Promise<unknown>;
}

export interface RadialLayoutRpcClient {
  getRegistry: () => Promise<RadialLayoutRegistryV1>;
  record: (record: GeneratedRadialLayoutV1) => Promise<RadialLayoutRegistryV1>;
  exportProbe: (report: SteamInputProbeReport) => Promise<SteamInputProbeExportResult>;
  recordProbeEvent: (event: SteamInputProbeMetadataEvent) => Promise<SteamInputProbeEventResult>;
}

const radialLayoutRpcErrorCodes = new Set([
  "radial_layout_rpc_failed",
  "invalid_radial_layout",
  "invalid_radial_layout_registry",
  "invalid_radial_app_id",
  "invalid_radial_source_layout_id",
  "invalid_radial_generated_layout_id",
  "invalid_radial_generated_layout_name",
  "invalid_radial_catalog_fingerprint",
  "invalid_radial_runtime_fingerprint",
  "invalid_radial_revision",
  "invalid_radial_created_at",
  "radial_layout_ids_must_differ",
  "too_many_radial_layouts",
  "duplicate_radial_layout",
  "invalid_steam_input_probe",
  "steam_input_probe_too_large",
  "steam_input_probe_export_failed",
]);

export class RadialLayoutRpcError extends Error {
  readonly code: string;

  constructor(code: string) {
    const boundedCode = radialLayoutRpcErrorCodes.has(code) ? code : "radial_layout_rpc_failed";
    super(boundedCode);
    this.code = boundedCode;
    this.name = "RadialLayoutRpcError";
  }
}

const callTransport = async <T>(operation: () => Promise<T>): Promise<T> => {
  try {
    return await operation();
  } catch {
    throw new RadialLayoutRpcError("radial_layout_rpc_failed");
  }
};

const decodeWire = <T>(operation: () => T, fallback: "invalid_radial_layout" | "invalid_radial_layout_registry"): T => {
  try {
    return operation();
  } catch (error) {
    if (error instanceof SteamInputDecodeError && radialLayoutRpcErrorCodes.has(error.code))
      throw new RadialLayoutRpcError(error.code);
    throw new RadialLayoutRpcError(fallback);
  }
};

const decodeProbeExport = (value: unknown): SteamInputProbeExportResult => {
  const record =
    value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : undefined;
  if (
    !record ||
    typeof record.path !== "string" ||
    !record.path.startsWith("/") ||
    typeof record.bytesWritten !== "number" ||
    !Number.isSafeInteger(record.bytesWritten) ||
    record.bytesWritten < 0
  )
    throw new RadialLayoutRpcError("invalid_steam_input_probe");
  return {
    path: record.path,
    bytesWritten: record.bytesWritten,
  };
};

const decodeProbeEventResult = (value: unknown): SteamInputProbeEventResult => {
  const record =
    value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : undefined;
  if (!record || Object.keys(record).length !== 1 || record.accepted !== true)
    throw new RadialLayoutRpcError("invalid_steam_input_probe");
  return { accepted: true };
};

export const createRadialLayoutRpc = (transport: RadialLayoutRpcTransport): RadialLayoutRpcClient => ({
  async getRegistry() {
    const response = await callTransport(() => transport.getRegistry());
    return decodeWire(() => decodeRadialLayoutRegistry(response), "invalid_radial_layout_registry");
  },
  async record(record) {
    const decoded = decodeWire(() => decodeGeneratedRadialLayout(record), "invalid_radial_layout");
    const response = await callTransport(() => transport.record(decoded));
    return decodeWire(() => decodeRadialLayoutRegistry(response), "invalid_radial_layout_registry");
  },
  async exportProbe(report) {
    const response = await callTransport(() => transport.exportProbe(report));
    return decodeProbeExport(response);
  },
  async recordProbeEvent(event) {
    const response = await callTransport(() => transport.recordProbeEvent(event));
    return decodeProbeEventResult(response);
  },
});

const getRegistryCall = callable<[], unknown>("get_radial_layout_registry");
const recordCall = callable<[GeneratedRadialLayoutV1], unknown>("record_generated_radial_layout");
const exportProbeCall = callable<[SteamInputProbeReport], unknown>("export_steam_input_probe");
const recordProbeEventCall = callable<[SteamInputProbeMetadataEvent], unknown>("record_steam_input_probe_event");

export const radialLayoutRpc = createRadialLayoutRpc({
  getRegistry: () => getRegistryCall(),
  record: (record) => recordCall(record),
  exportProbe: (report) => exportProbeCall(report),
  recordProbeEvent: (event) => recordProbeEventCall(event),
});
