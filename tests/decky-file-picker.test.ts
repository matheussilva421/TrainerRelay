import { afterEach, describe, expect, it, vi } from "vitest";

const deckyApi = vi.hoisted(() => ({
  openFilePicker: vi.fn(),
}));

vi.mock("@decky/api", () => ({
  callable: () => vi.fn(),
  FileSelectionType: { FILE: 7 },
  openFilePicker: deckyApi.openFilePicker,
  toaster: { toast: vi.fn() },
}));

import { browseFiles } from "../src/infra/decky";

afterEach(() => {
  vi.restoreAllMocks();
  deckyApi.openFilePicker.mockReset();
});

describe("Decky file-picker diagnostics", () => {
  it("logs the API boundary and successful result without exposing the selected path", async () => {
    const consoleInfo = vi.spyOn(console, "info").mockImplementation(() => undefined);
    deckyApi.openFilePicker.mockResolvedValue({ path: "/home/deck/private/trainer.exe", realpath: true });

    await expect(browseFiles("/home/deck", true, ["exe"])).resolves.toMatchObject({
      path: "/home/deck/private/trainer.exe",
    });

    expect(consoleInfo).toHaveBeenCalledWith(
      expect.stringContaining("Trainer Relay"),
      expect.any(String),
      "[TrainerRelay:picker] api-call",
      { hasStartPath: true, includeFiles: true, extensions: ["exe"] },
    );
    expect(consoleInfo).toHaveBeenCalledWith(
      expect.stringContaining("Trainer Relay"),
      expect.any(String),
      "[TrainerRelay:picker] api-resolved",
      { hasPath: true, extension: "exe" },
    );
    expect(consoleInfo.mock.calls.flat().join(" ")).not.toContain("/home/deck/private");
  });

  it("logs API rejection at the error level before preserving cancellation semantics", async () => {
    vi.spyOn(console, "info").mockImplementation(() => undefined);
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    deckyApi.openFilePicker.mockRejectedValue(new Error("modal unavailable"));

    await expect(browseFiles("/home/deck", true, ["exe"])).rejects.toBe("User Canceled");

    expect(consoleError).toHaveBeenCalledWith(
      expect.stringContaining("Trainer Relay"),
      expect.any(String),
      "[TrainerRelay:picker] api-rejected",
      { reason: "modal unavailable" },
    );
  });
});
