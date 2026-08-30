import type {
  DiagnosticEvent,
  DiagnosticEventsResponse,
  DiagnosticSettingsResponse,
} from "../domain/diagnostics/types";

export interface DiagnosticPollingTimers {
  setTimeout(callback: () => void, milliseconds: number): unknown;
  clearTimeout(handle: unknown): void;
}

export interface DiagnosticPollingDependencies {
  loadSettings: () => Promise<DiagnosticSettingsResponse>;
  loadEvents: (request: { cursor: string | undefined; limit: number }) => Promise<DiagnosticEventsResponse>;
  onEvents: (events: readonly DiagnosticEvent[]) => void;
  onSettings: (settings: DiagnosticSettingsResponse) => void;
  onError: () => void;
  timers: DiagnosticPollingTimers;
}

const failureDelays = [2_000, 4_000, 8_000, 10_000] as const;

export const startDiagnosticPolling = (dependencies: DiagnosticPollingDependencies): (() => void) => {
  let stopped = false;
  let timer: unknown;
  let cursor: string | undefined;
  let generation: number | undefined;
  let highestSequence = 0;
  let failures = 0;
  let failureReported = false;

  const schedule = (delay: number) => {
    if (stopped) return;
    timer = dependencies.timers.setTimeout(() => void run(), delay);
  };

  const run = async (): Promise<void> => {
    if (stopped) return;
    try {
      const settings = await dependencies.loadSettings();
      if (stopped) return;
      dependencies.onSettings(settings);
      if (settings.settings.enabled) {
        const response = await dependencies.loadEvents({ cursor, limit: 200 });
        if (stopped) return;
        if (response.cursorReset || generation !== response.generation) {
          generation = response.generation;
          highestSequence = 0;
        }
        const fresh = response.events.filter((event) => event.sequence > highestSequence);
        if (fresh.length > 0) {
          highestSequence = Math.max(...fresh.map((event) => event.sequence));
          dependencies.onEvents(fresh);
        }
        cursor = response.nextCursor;
      }
      failures = 0;
      failureReported = false;
      schedule(1_000);
    } catch {
      if (stopped) return;
      if (!failureReported) {
        failureReported = true;
        dependencies.onError();
      }
      const delay = failureDelays[Math.min(failures, failureDelays.length - 1)];
      failures += 1;
      schedule(delay);
    }
  };

  void run();
  return () => {
    if (stopped) return;
    stopped = true;
    if (timer !== undefined) dependencies.timers.clearTimeout(timer);
  };
};
