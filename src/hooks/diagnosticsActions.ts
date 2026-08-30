import type { DiagnosticEvent, DiagnosticSettingsResponse } from "../domain/diagnostics/types";
import type { DiagnosticRpcClient } from "../infra/diagnosticRpc";

type DiagnosticAction = "toggle" | "export" | "clear";

export interface DiagnosticsActionDependencies {
  rpc: Pick<
    DiagnosticRpcClient,
    "setDiagnosticsEnabled" | "exportDiagnostics" | "getDiagnosticSettings" | "clearDiagnostics"
  >;
  updateResponse: (response: DiagnosticSettingsResponse) => void;
  updateEvents: (events: readonly DiagnosticEvent[]) => void;
  notice: (message: string) => void;
  setBusy: (action: DiagnosticAction | null) => void;
}

export const createDiagnosticsActions = (dependencies: DiagnosticsActionDependencies) => ({
  async toggle(enabled: boolean): Promise<void> {
    dependencies.setBusy("toggle");
    try {
      dependencies.updateResponse(await dependencies.rpc.setDiagnosticsEnabled(enabled));
    } catch {
      dependencies.notice("Diagnostic setting could not be saved. Its previous state was preserved.");
    } finally {
      dependencies.setBusy(null);
    }
  },

  async exportText(): Promise<void> {
    dependencies.setBusy("export");
    try {
      const exported = await dependencies.rpc.exportDiagnostics();
      dependencies.updateResponse(await dependencies.rpc.getDiagnosticSettings());
      dependencies.notice(`Diagnostics exported to ${exported.path}`);
    } catch {
      dependencies.notice("Diagnostic export failed. Existing logs were preserved.");
    } finally {
      dependencies.setBusy(null);
    }
  },

  async clearConfirmed(): Promise<void> {
    dependencies.setBusy("clear");
    try {
      const cleared = await dependencies.rpc.clearDiagnostics();
      dependencies.updateResponse(cleared);
      dependencies.updateEvents([]);
      dependencies.notice("Diagnostic journal cleared. Exported TXT files were preserved.");
    } catch {
      dependencies.notice("Diagnostic journal could not be cleared completely.");
    } finally {
      dependencies.setBusy(null);
    }
  },
});
