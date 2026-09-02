import { describe, expect, it } from "vitest";
import type { ReadyCheatControls } from "../src/domain/cheats/types";
import {
  buildSteamInputCommandItems,
  buildSteamInputRadialPlan,
  canonicalizeCheatAuthority,
  computeCatalogFingerprint,
} from "../src/domain/steamInput/planner";
import type { BuildRadialPlanInput } from "../src/domain/steamInput/types";

const controls: ReadyCheatControls = {
  identity: "gog:1482265668",
  status: "ready",
  trainerSha256: "a".repeat(64),
  source: "adapter",
  trainerLabel: "BioShock 2 FLiNG",
  capabilities: { commands: true, authoritativeState: false, toggles: false },
  diagnostic: null,
  cheats: [
    { id: "health", label: "Infinite Health", hotkey: { modifiers: [], key: "NUMPAD1" }, state: "unknown" },
    {
      id: "ammo",
      label: "Infinite Ammo",
      hotkeys: [
        { modifiers: [], key: "NUMPAD2" },
        { modifiers: ["ctrl"], key: "F2" },
      ],
      state: "unknown",
    },
  ],
};

describe("Steam Input radial planner command expansion", () => {
  it("expands one-hotkey and multiple-hotkey cheats in stable order", () => {
    expect(buildSteamInputCommandItems(controls).map(({ label }) => label)).toEqual([
      "Infinite Health",
      "Infinite Ammo (NUMPAD2)",
      "Infinite Ammo (Ctrl+F2)",
    ]);
  });

  it("does not produce commands when command capability is disabled", () => {
    expect(
      buildSteamInputCommandItems({
        ...controls,
        capabilities: { ...controls.capabilities, commands: false },
      }),
    ).toEqual([]);
  });

  it("skips malformed labels and hotkeys without changing valid input order", () => {
    const result = buildSteamInputCommandItems({
      ...controls,
      cheats: [
        { id: "bad-label", label: " ", hotkey: { modifiers: [], key: "F1" }, state: "enabled" },
        { id: "first", label: "First", hotkey: { modifiers: [], key: "F3" }, state: "disabled" },
        { id: "bad-key", label: "Bad key", hotkey: { modifiers: [], key: "not-a-key" }, state: "unknown" },
        { id: "second", label: "Second", hotkey: { modifiers: ["ctrl"], key: "F4" }, state: "unknown" },
      ],
    });

    expect(result.map(({ itemId, label }) => ({ itemId, label }))).toEqual([
      { itemId: "first:0", label: "First" },
      { itemId: "second:0", label: "Second" },
    ]);
  });

  it("deduplicates alternative hotkeys by canonical chord", () => {
    const result = buildSteamInputCommandItems({
      ...controls,
      cheats: [
        {
          id: "duplicate",
          label: "Duplicate",
          hotkeys: [
            { modifiers: ["ctrl", "shift"], key: "F5" },
            { modifiers: ["shift", "ctrl"], key: "F5" },
            { modifiers: ["ctrl"], key: "F5" },
          ],
          state: "unknown",
        },
      ],
    });

    expect(result.map(({ itemId, label, hotkey }) => ({ itemId, label, hotkey }))).toEqual([
      {
        itemId: "duplicate:0",
        label: "Duplicate (Ctrl+Shift+F5)",
        hotkey: { modifiers: ["ctrl", "shift"], key: "F5" },
      },
      { itemId: "duplicate:1", label: "Duplicate (Ctrl+F5)", hotkey: { modifiers: ["ctrl"], key: "F5" } },
    ]);
  });

  it("keeps state out of labels and serializes authority deterministically", async () => {
    const value = canonicalizeCheatAuthority(controls);
    expect(value).not.toContain("unknown");
    expect(value).toBe(
      '{"identity":"gog:1482265668","trainerSha256":"' +
        "a".repeat(64) +
        '","source":"adapter","commands":[{"itemId":"health:0","cheatId":"health","label":"Infinite Health","hotkey":{"modifiers":[],"key":"NUMPAD1"}},{"itemId":"ammo:0","cheatId":"ammo","label":"Infinite Ammo (NUMPAD2)","hotkey":{"modifiers":[],"key":"NUMPAD2"}},{"itemId":"ammo:1","cheatId":"ammo","label":"Infinite Ammo (Ctrl+F2)","hotkey":{"modifiers":["ctrl"],"key":"F2"}}]}',
    );

    const digestInput: Uint8Array[] = [];
    const fingerprint = await computeCatalogFingerprint(controls, async (input) => {
      digestInput.push(input);
      return new Uint8Array(32).fill(0xab);
    });

    expect(new TextDecoder().decode(digestInput[0])).toBe(value);
    expect(fingerprint).toBe("ab".repeat(32));
  });

  it("rejects a digest that is not exactly 32 bytes", async () => {
    await expect(computeCatalogFingerprint(controls, async () => new Uint8Array(31))).rejects.toThrow(
      "invalid_sha256_digest",
    );
  });
});

const fourteenCommandControls: ReadyCheatControls = {
  ...controls,
  cheats: Array.from({ length: 14 }, (_, index) => ({
    id: `cheat-${index}`,
    label: `Cheat ${index}`,
    hotkey: { modifiers: [], key: `F${index + 1}` },
    state: "unknown" as const,
  })),
};

const validPlanInput = (overrides: Partial<BuildRadialPlanInput> = {}): BuildRadialPlanInput => ({
  appId: 123456,
  identity: controls.identity,
  trainerSha256: controls.trainerSha256,
  catalogFingerprint: "b".repeat(64),
  controls: fourteenCommandControls,
  ...overrides,
});

describe("Steam Input radial planner pages and activation", () => {
  it("creates deterministic six-command pages with fixed command sectors and navigation targets", () => {
    const plan = buildSteamInputRadialPlan(validPlanInput());

    expect(plan.pages.map(({ items }) => items.length)).toEqual([6, 6, 2]);
    expect(plan.pages.map(({ items }) => items.map((_, sector) => sector))).toEqual([
      [0, 1, 2, 3, 4, 5],
      [0, 1, 2, 3, 4, 5],
      [0, 1],
    ]);
    expect(plan.pages.map(({ items }) => items.map(({ itemId }) => itemId))).toEqual([
      ["cheat-0:0", "cheat-1:0", "cheat-2:0", "cheat-3:0", "cheat-4:0", "cheat-5:0"],
      ["cheat-6:0", "cheat-7:0", "cheat-8:0", "cheat-9:0", "cheat-10:0", "cheat-11:0"],
      ["cheat-12:0", "cheat-13:0"],
    ]);

    expect(plan.pages[0]).toMatchObject({ page: 1, nextPage: 2 });
    expect(plan.pages[0]).not.toHaveProperty("previousPage");
    expect(plan.pages[1]).toMatchObject({ page: 2, previousPage: 1, nextPage: 3 });
    expect(plan.pages[2]).toMatchObject({ page: 3, previousPage: 2 });
    expect(plan.pages[2]).not.toHaveProperty("nextPage");
  });

  it("uses the physical-click left-trackpad activation contract without state or release actions", () => {
    const plan = buildSteamInputRadialPlan(validPlanInput());

    expect(plan).toMatchObject({
      controller: "steam_deck_builtin",
      input: "left_trackpad",
      activation: "physical_click",
    });
    expect(JSON.stringify(plan)).not.toContain("touch_release");
    expect(JSON.stringify(plan)).not.toContain("release");
    expect(JSON.stringify(plan)).not.toContain('"state"');
  });

  it("validates the plan authority and requires at least one command", () => {
    const invalidCases: [string, Partial<BuildRadialPlanInput>][] = [
      ["invalid_app_id", { appId: 0 }],
      ["invalid_app_id", { appId: 1.5 }],
      ["invalid_app_id", { appId: Number.MAX_SAFE_INTEGER + 1 }],
      ["identity_mismatch", { identity: "gog:other" as never }],
      ["invalid_trainer_sha256", { trainerSha256: "A".repeat(64) }],
      ["invalid_catalog_fingerprint", { catalogFingerprint: "b".repeat(63) }],
      ["no_commands", { controls: { ...fourteenCommandControls, cheats: [] } }],
    ];

    for (const [error, overrides] of invalidCases) {
      expect(() => buildSteamInputRadialPlan(validPlanInput(overrides))).toThrow(error);
    }
  });

  it("does not mutate the command snapshot while paginating", () => {
    const input = validPlanInput();
    const originalCheats = [...input.controls.cheats];

    buildSteamInputRadialPlan(input);

    expect(input.controls.cheats).toEqual(originalCheats);
  });
});
