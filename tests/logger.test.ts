import { afterEach, describe, expect, it, vi } from "vitest";

import { logger } from "../src/utils/logger";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Trainer Relay logger", () => {
  it("uses the matching DevTools console level so errors remain visible with the errors-only filter", () => {
    const consoleLog = vi.spyOn(console, "log").mockImplementation(() => undefined);
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);

    logger.error("[TrainerRelay:picker] api-rejected", { reason: "cancelled" });

    expect(consoleError).toHaveBeenCalledWith(
      expect.stringContaining("Trainer Relay"),
      expect.any(String),
      "[TrainerRelay:picker] api-rejected",
      { reason: "cancelled" },
    );
    expect(consoleLog).not.toHaveBeenCalled();
  });

  it("routes picker progress to the informational console level", () => {
    const consoleInfo = vi.spyOn(console, "info").mockImplementation(() => undefined);

    logger.info("[TrainerRelay:picker] ui-activated", { disabled: false });

    expect(consoleInfo).toHaveBeenCalledWith(
      expect.stringContaining("Trainer Relay"),
      expect.any(String),
      "[TrainerRelay:picker] ui-activated",
      { disabled: false },
    );
  });
});
