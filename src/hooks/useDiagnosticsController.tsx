import { useEffect, useMemo, useState } from "react";

import type { DiagnosticEvent, DiagnosticSettingsResponse } from "../domain/diagnostics/types";
import { sendNotice } from "../infra/decky";
import { diagnosticRpc } from "../infra/diagnosticRpc";
import { bindBrowserTimers } from "./browserTimers";
import { startDiagnosticPolling } from "./diagnosticPolling";
import { createDiagnosticsActions } from "./diagnosticsActions";

type DiagnosticsState = "loading" | "ready" | "error";
type BusyAction = "toggle" | "export" | "clear" | null;

const emptyResponse = (): DiagnosticSettingsResponse => ({
  settings: { schemaVersion: 1, enabled: false },
  bytesUsed: 0,
  byteLimit: 52_428_800,
  eventCount: 0,
  storageDiagnostic: null,
  lastExportPath: null,
});

const mergeLatest = (current: readonly DiagnosticEvent[], incoming: readonly DiagnosticEvent[]): DiagnosticEvent[] =>
  [...current, ...incoming].slice(-20);

export const useDiagnosticsController = () => {
  const timers = bindBrowserTimers(window);
  const [state, setState] = useState<DiagnosticsState>("loading");
  const [response, setResponse] = useState<DiagnosticSettingsResponse>(emptyResponse);
  const [events, setEvents] = useState<readonly DiagnosticEvent[]>([]);
  const [busy, setBusy] = useState<BusyAction>(null);
  const [clearRequested, setClearRequested] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let stopPolling: (() => void) | undefined;

    const loadRetainedHistory = async () => {
      let cursor: string | undefined;
      let latest: readonly DiagnosticEvent[] = [];
      for (;;) {
        const page = await diagnosticRpc.getDiagnosticEvents({ cursor, limit: 200 });
        if (cancelled) return;
        latest = mergeLatest(latest, page.events);
        if (page.events.length < 200 || page.nextCursor === cursor) break;
        cursor = page.nextCursor;
      }
      if (!cancelled) setEvents(latest);
    };

    const initialize = async () => {
      try {
        const initial = await diagnosticRpc.getDiagnosticSettings();
        if (cancelled) return;
        setResponse(initial);
        setState("ready");
        if (!initial.settings.enabled) await loadRetainedHistory();
        if (cancelled) return;
        stopPolling = startDiagnosticPolling({
          loadSettings: diagnosticRpc.getDiagnosticSettings,
          loadEvents: diagnosticRpc.getDiagnosticEvents,
          onSettings(next) {
            setResponse(next);
            if (next.eventCount === 0) setEvents([]);
            setState("ready");
          },
          onEvents(incoming) {
            setEvents((current) => mergeLatest(current, incoming));
          },
          onError() {
            setState("error");
          },
          timers,
        });
      } catch {
        if (!cancelled) setState("error");
      }
    };

    void initialize();
    return () => {
      cancelled = true;
      stopPolling?.();
    };
  }, []);

  const actions = useMemo(
    () =>
      createDiagnosticsActions({
        rpc: diagnosticRpc,
        updateResponse: (next) => {
          setResponse(next);
          setState("ready");
        },
        updateEvents: setEvents,
        notice: sendNotice,
        setBusy,
      }),
    [],
  );

  return {
    state,
    response,
    events: events.slice(-20),
    busy,
    clearRequested,
    toggle: actions.toggle,
    exportText: actions.exportText,
    requestClear: () => setClearRequested(true),
    cancelClear: () => setClearRequested(false),
    clearConfirmed: async () => {
      await actions.clearConfirmed();
      setClearRequested(false);
    },
  };
};
