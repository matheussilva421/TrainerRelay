import { describe, expect, it, vi } from "vitest";

import { canRetryRelay, startRelayStatusPolling } from "../src/hooks/statusPolling";
import type { RelayStatusPayload } from "../src/infra/relayRpc";

const status: RelayStatusPayload = { identity: "epic:game-1", state: "waiting_for_game", diagnostic: null };

describe("Trainer Relay status polling", () => {
  it("polls once per second and stops delivering updates after cleanup", async () => {
    let tick: (() => void) | undefined;
    const clearInterval = vi.fn();
    const onStatus = vi.fn();
    const poll = vi.fn().mockResolvedValue(status);
    const stop = startRelayStatusPolling({
      identity: status.identity,
      poll,
      onStatus,
      setInterval: (callback, milliseconds) => {
        expect(milliseconds).toBe(1_000);
        tick = callback;
        return 1;
      },
      clearInterval,
    });

    await Promise.resolve();
    expect(poll).toHaveBeenCalledTimes(1);
    expect(onStatus).toHaveBeenCalledWith(status);
    tick?.();
    await Promise.resolve();
    expect(poll).toHaveBeenCalledTimes(2);

    stop();
    expect(clearInterval).toHaveBeenCalledWith(1);
    tick?.();
    await Promise.resolve();
    expect(poll).toHaveBeenCalledTimes(2);
  });

  it("offers retry only for failed and never invents a running state", () => {
    expect(canRetryRelay({ ...status, state: "failed" })).toBe(true);
    expect(canRetryRelay({ ...status, state: "running" })).toBe(false);
    expect(canRetryRelay({ ...status, state: "invalid_config" })).toBe(false);
  });
});
