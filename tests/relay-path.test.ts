import { describe, expect, it } from "vitest";

import { isAbsoluteExecutablePath, isAbsolutePath } from "../src/domain/relay/path";

describe("relay path validation", () => {
  it.each([
    "/home/deck/Trainer.exe",
    "C:\\Trainers\\Game.exe",
    "d:/tools/game.EXE",
  ])("accepts absolute trainer executable %s", (value) => {
    expect(isAbsolutePath(value)).toBe(true);
    expect(isAbsoluteExecutablePath(value)).toBe(true);
  });

  it.each([
    "trainer.exe",
    "./trainer.exe",
    "../trainer.exe",
    "/home/deck/trainer.dll",
    "C:trainer.exe",
  ])("rejects unsafe trainer path %s", (value) => {
    expect(isAbsoluteExecutablePath(value)).toBe(false);
  });
});
