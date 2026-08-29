import { describe, expect, it } from "vitest";
import { sidecarProgram } from "../src/domain/features";
import { LaunchOptions } from "../src/domain/options";
import { planLegacyMigration } from "../src/domain/relay/migration";

describe("planLegacyMigration", () => {
  it("reports no migration when neither legacy assignment exists", () => {
    expect(planLegacyMigration(LaunchOptions.parse("KEEP=1 %command% gog:game-1"))).toEqual({ status: "none" });
  });

  it("returns one decoded exe and the exact source after removing the legacy pair", () => {
    const original = "KEEP='a value' %command% --profile 'Deck Profile' gog:game-1";
    const enabled = sidecarProgram.set(LaunchOptions.parse(original), "/home/deck/Trainers/My Trainer's.exe");
    expect(enabled.ok).toBe(true);
    if (!enabled.ok) throw new Error(enabled.error);

    expect(planLegacyMigration(enabled.value)).toEqual({
      status: "ready",
      trainerPath: "/home/deck/Trainers/My Trainer's.exe",
      launchOptions: original,
    });
  });

  it("removes every duplicated legacy assignment while preserving unrelated source", () => {
    const source =
      "KEEP=1  PROTON_REMOTE_DEBUG_CMD='/one.exe' OTHER='two words' " +
      "PROTON_REMOTE_DEBUG_CMD='/two.exe' PRESSURE_VESSEL_FILESYSTEMS_RW=/tmp " +
      "UNRELATED=3 %command% --flag 'literal value' epic:one";

    expect(planLegacyMigration(source)).toEqual({
      status: "ready",
      trainerPath: "/two.exe",
      launchOptions: "KEEP=1  OTHER='two words' UNRELATED=3 %command% --flag 'literal value' epic:one",
    });
  });

  it.each([
    ["partial command pair", "PROTON_REMOTE_DEBUG_CMD='/trainer.exe' %command% epic:one"],
    ["partial directory pair", "PRESSURE_VESSEL_FILESYSTEMS_RW=/tmp %command% gog:one"],
    ["invalid document", "%command% && unsafe"],
    [
      "multiword trainer",
      "PROTON_REMOTE_DEBUG_CMD='/trainer.exe --flag' PRESSURE_VESSEL_FILESYSTEMS_RW=/tmp %command% epic:one",
    ],
    [
      "non exe trainer",
      "PROTON_REMOTE_DEBUG_CMD='/trainer.dll' PRESSURE_VESSEL_FILESYSTEMS_RW=/tmp %command% epic:one",
    ],
    ["dynamic trainer", "PROTON_REMOTE_DEBUG_CMD=$TRAINER PRESSURE_VESSEL_FILESYSTEMS_RW=/tmp %command% epic:one"],
    [
      "malformed trainer quote",
      "PROTON_REMOTE_DEBUG_CMD='/trainer.exe PRESSURE_VESSEL_FILESYSTEMS_RW=/tmp %command% epic:one",
    ],
  ])("blocks %s", (_name, source) => {
    expect(planLegacyMigration(source)).toMatchObject({ status: "blocked" });
  });

  it("accepts an explicit LaunchOptions object without changing it", () => {
    const enabled = sidecarProgram.set(
      LaunchOptions.parse("%command% gog:one"),
      "C:\\Games\\Trainer With Apostrophe's.exe",
    );
    expect(enabled.ok).toBe(true);
    if (!enabled.ok) throw new Error(enabled.error);
    const options = enabled.value;
    const before = options.toString();

    expect(planLegacyMigration(options)).toMatchObject({
      status: "ready",
      trainerPath: "C:\\Games\\Trainer With Apostrophe's.exe",
    });
    expect(options.toString()).toBe(before);
  });
});
