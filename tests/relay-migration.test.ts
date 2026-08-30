import { describe, expect, it } from "vitest";
import { sidecarProgram } from "../src/domain/features";
import { LaunchOptions } from "../src/domain/options";
import { planLegacyMigration } from "../src/domain/relay/migration";

describe("planLegacyMigration", () => {
  it("reports no migration when neither legacy assignment exists", () => {
    expect(planLegacyMigration(LaunchOptions.parse("KEEP=1 %command% gog:game-1"))).toEqual({ status: "none" });
  });

  it("prepares a plain UniFiDeck identity for UMU container re-entry after a trainer is selected", () => {
    expect(planLegacyMigration("gog:1482265568", "/home/deck/Trainers/Game.exe")).toEqual({
      status: "ready",
      trainerPath: "/home/deck/Trainers/Game.exe",
      launchOptions: "UMU_CONTAINER_NSENTER=1 %command% gog:1482265568",
      changes: "container",
    });
  });

  it("requires exactly one canonical container re-entry assignment", () => {
    const trainerPath = "/home/deck/Trainers/Game.exe";
    expect(planLegacyMigration("UMU_CONTAINER_NSENTER=1 %command% gog:one", trainerPath)).toEqual({
      status: "none",
    });
    expect(
      planLegacyMigration("UMU_CONTAINER_NSENTER=0 UMU_CONTAINER_NSENTER=1 %command% gog:one", trainerPath),
    ).toEqual({
      status: "ready",
      trainerPath,
      launchOptions: "UMU_CONTAINER_NSENTER=1 %command% gog:one",
      changes: "container",
    });
  });

  it("returns one decoded exe and the exact source after removing the legacy pair", () => {
    const original = "KEEP='a value' %command% --profile 'Deck Profile' gog:game-1";
    const enabled = sidecarProgram.set(LaunchOptions.parse(original), "/home/deck/Trainers/My Trainer's.exe");
    expect(enabled.ok).toBe(true);
    if (!enabled.ok) throw new Error(enabled.error);

    expect(planLegacyMigration(enabled.value)).toEqual({
      status: "ready",
      trainerPath: "/home/deck/Trainers/My Trainer's.exe",
      launchOptions: "KEEP='a value' UMU_CONTAINER_NSENTER=1 %command% --profile 'Deck Profile' gog:game-1",
      changes: "legacy_and_container",
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
      launchOptions:
        "KEEP=1  OTHER='two words' UNRELATED=3 UMU_CONTAINER_NSENTER=1 %command% --flag 'literal value' epic:one",
      changes: "legacy_and_container",
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
