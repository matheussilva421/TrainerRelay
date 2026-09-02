import { useEffect, useState } from "react";
import type {
  CheatCommandResult,
  CheatControlsResponse,
  ManualCheatMutation,
  ManualCheatRemoval,
  SymbolicHotkey,
} from "../domain/cheats/types";
import type { LaunchIdentity } from "../domain/relay/types";
import { type CheatRpcClient, CheatRpcError, cheatRpc } from "../infra/cheatRpc";
import { bindBrowserTimers } from "./browserTimers";

const boundedCodePattern = /^[a-z0-9_]{1,64}$/;

export const boundedCheatErrorCode = (reason: unknown): string => {
  if (reason instanceof CheatRpcError && boundedCodePattern.test(reason.code)) return reason.code;
  return "cheat_rpc_failed";
};

export interface CheatControlsPollingDependencies {
  identity: LaunchIdentity;
  poll: () => Promise<CheatControlsResponse>;
  onResponse: (response: CheatControlsResponse) => void;
  onError: (code: string) => void;
  setInterval: (callback: () => void, milliseconds: number) => unknown;
  clearInterval: (handle: unknown) => void;
  intervalMs?: number;
}

export const startCheatControlsPolling = (dependencies: CheatControlsPollingDependencies): (() => void) => {
  let stopped = false;
  let inFlight = false;

  const run = async () => {
    if (stopped || inFlight) return;
    inFlight = true;
    try {
      const response = await dependencies.poll();
      if (!stopped) dependencies.onResponse(response);
    } catch (reason) {
      if (!stopped) dependencies.onError(boundedCheatErrorCode(reason));
    } finally {
      inFlight = false;
    }
  };

  const interval = dependencies.setInterval(() => void run(), dependencies.intervalMs ?? 1_000);
  void run();

  return () => {
    if (stopped) return;
    stopped = true;
    dependencies.clearInterval(interval);
  };
};

export interface CheatControlsHookResult {
  response: CheatControlsResponse | undefined;
  status: "unavailable" | "waiting" | "ready" | "error";
  error: string | null;
  busy: boolean;
  lastResults: Record<string, string>;
  refresh: () => Promise<void>;
  sendCommand: (cheatId: string) => Promise<CheatCommandResult | undefined>;
  addManualCheatControl: (label: string, hotkey: SymbolicHotkey) => Promise<ManualCheatMutation | undefined>;
  removeManualCheatControl: (cheatId: string) => Promise<ManualCheatRemoval | undefined>;
}

const commandResultMessage = (result: CheatCommandResult): string => {
  if (result.outcome === "requested" && result.state === "unknown") return "Comando enviado; estado desconhecido";
  if (result.diagnostic) return `Comando não concluído: ${result.diagnostic.code}`;
  return "Comando não concluído; estado desconhecido";
};

export const useCheatControls = (
  identity: LaunchIdentity | undefined,
  rpc: CheatRpcClient = cheatRpc,
): CheatControlsHookResult => {
  const [response, setResponse] = useState<CheatControlsResponse>();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [lastResults, setLastResults] = useState<Record<string, string>>({});

  const refresh = async () => {
    if (!identity) {
      setResponse(undefined);
      setError(null);
      return;
    }
    try {
      const next = await rpc.getCheatControls(identity);
      setResponse(next);
      setError(null);
    } catch (reason) {
      setResponse(undefined);
      setError(boundedCheatErrorCode(reason));
    }
  };

  useEffect(() => {
    if (!identity) {
      setResponse(undefined);
      setError(null);
      return;
    }
    const timers = bindBrowserTimers(window);
    return startCheatControlsPolling({
      identity,
      poll: () => rpc.getCheatControls(identity),
      onResponse: (next) => {
        setResponse(next);
        setError(null);
      },
      onError: (code) => {
        setResponse(undefined);
        setError(code);
      },
      setInterval: timers.setInterval,
      clearInterval: timers.clearInterval,
    });
  }, [identity, rpc]);

  const runMutation = async <T>(operation: () => Promise<T>, after?: (result: T) => void): Promise<T | undefined> => {
    setBusy(true);
    try {
      const result = await operation();
      after?.(result);
      return result;
    } catch (reason) {
      setError(boundedCheatErrorCode(reason));
      return undefined;
    } finally {
      setBusy(false);
      await refresh();
    }
  };

  const sendCommand = (cheatId: string) =>
    !identity
      ? Promise.resolve(undefined)
      : runMutation(
          () =>
            rpc.sendCheatCommand({
              identity,
              cheatId,
              allowAuthoritativeState:
                response?.status === "ready" &&
                response.source === "cooperative" &&
                response.capabilities.authoritativeState === true,
            }),
          (result) => setLastResults((current) => ({ ...current, [cheatId]: commandResultMessage(result) })),
        );

  const addManualCheatControl = (label: string, hotkey: SymbolicHotkey) => {
    if (!identity || response?.status !== "ready" || !/^[0-9a-f]{64}$/.test(response.trainerSha256)) {
      setError("cheat_controls_unavailable");
      return Promise.resolve(undefined);
    }
    return runMutation(() =>
      rpc.addManualCheatControl({ identity, trainerSha256: response.trainerSha256, label, hotkey }),
    );
  };

  const removeManualCheatControl = (cheatId: string) => {
    if (!identity) {
      setError("cheat_controls_unavailable");
      return Promise.resolve(undefined);
    }
    return runMutation(() => rpc.removeManualCheatControl({ identity, cheatId }));
  };

  return {
    response,
    status: response?.status ?? (error ? "error" : identity ? "waiting" : "unavailable"),
    error,
    busy,
    lastResults,
    refresh,
    sendCommand,
    addManualCheatControl,
    removeManualCheatControl,
  };
};
