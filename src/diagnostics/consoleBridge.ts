import { type DiagnosticPollingTimers, startDiagnosticPolling } from "../hooks/diagnosticPolling";
import type { DiagnosticRpcClient } from "../infra/diagnosticRpc";

export type DiagnosticConsoleRpc = Pick<DiagnosticRpcClient, "getDiagnosticSettings" | "getDiagnosticEvents">;

export const startDiagnosticConsoleBridge = (
  rpc: DiagnosticConsoleRpc,
  timers: DiagnosticPollingTimers,
): (() => void) =>
  startDiagnosticPolling({
    loadSettings: rpc.getDiagnosticSettings,
    loadEvents: rpc.getDiagnosticEvents,
    onEvents(events) {
      for (const event of events) console.info("[TrainerRelay:diagnostic]", event);
    },
    onSettings() {
      return;
    },
    onError() {
      console.warn("[TrainerRelay:diagnostic] polling_unavailable");
    },
    timers,
  });
