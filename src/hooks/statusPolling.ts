import type { LaunchIdentity } from "../domain/relay/types";
import type { RelayStatusPayload } from "../infra/relayRpc";

export interface RelayStatusPollingDependencies {
  identity: LaunchIdentity;
  poll: () => Promise<RelayStatusPayload>;
  onStatus: (status: RelayStatusPayload) => void;
  setInterval: (callback: () => void, milliseconds: number) => unknown;
  clearInterval: (handle: unknown) => void;
}

export const startRelayStatusPolling = (dependencies: RelayStatusPollingDependencies): (() => void) => {
  let stopped = false;
  let inFlight = false;
  const run = async () => {
    if (stopped || inFlight) return;
    inFlight = true;
    try {
      const status = await dependencies.poll();
      if (!stopped) dependencies.onStatus(status);
    } catch {
      if (!stopped) {
        dependencies.onStatus({
          identity: dependencies.identity,
          state: "invalid_config",
          diagnostic: { code: "status_unavailable" },
        });
      }
    } finally {
      inFlight = false;
    }
  };

  const interval = dependencies.setInterval(() => void run(), 1_000);
  void run();
  return () => {
    if (stopped) return;
    stopped = true;
    dependencies.clearInterval(interval);
  };
};

export const canRetryRelay = (status: RelayStatusPayload): boolean => status.state === "failed";
