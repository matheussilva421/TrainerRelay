import type { LaunchIdentity } from "../relay/types";

export interface DiagnosticSettingsV1 {
  readonly schemaVersion: 1;
  readonly enabled: boolean;
}

export type DiagnosticCategory = "config" | "games_map" | "process" | "umu" | "trainer" | "lifecycle";
export type DiagnosticOutcome = "info" | "accepted" | "rejected" | "warning" | "error";
export type DiagnosticDetailValue = string | number | boolean | null;

export interface DiagnosticEvent {
  readonly sequence: number;
  readonly timestamp: string;
  readonly identity?: LaunchIdentity;
  readonly session?: { readonly pid: number; readonly startTime: number };
  readonly category: DiagnosticCategory;
  readonly event: string;
  readonly outcome: DiagnosticOutcome;
  readonly details: Readonly<Record<string, DiagnosticDetailValue>>;
}

export interface DiagnosticSettingsResponse {
  readonly settings: DiagnosticSettingsV1;
  readonly bytesUsed: number;
  readonly byteLimit: 52_428_800;
  readonly eventCount: number;
  readonly storageDiagnostic: string | null;
  readonly lastExportPath: string | null;
}

export interface DiagnosticEventsRequest {
  readonly cursor?: string;
  readonly limit?: number;
}

export interface DiagnosticEventsResponse {
  readonly generation: number;
  readonly nextCursor: string;
  readonly cursorReset: boolean;
  readonly events: readonly DiagnosticEvent[];
}

export interface DiagnosticExportResponse {
  readonly path: string;
  readonly bytesWritten: number;
}

export interface DiagnosticClearResponse extends DiagnosticSettingsResponse {
  readonly generation: number;
}
