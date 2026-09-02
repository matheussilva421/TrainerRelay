import { describe, expect, it } from "vitest";

import { decodeRadialLayoutRegistry, decodeSteamInputCapabilityResult } from "../src/domain/steamInput/decoder";

const validLayout = {
  appId: 123456789,
  identity: "gog:1482265668",
  trainerSha256: "a".repeat(64),
  catalogFingerprint: "b".repeat(64),
  steamRuntimeFingerprint: "c".repeat(64),
  sourceLayoutId: "autosave://123/source",
  generatedLayoutId: "personal://123/generated",
  generatedLayoutName: "Trainer Relay - BioShock 2 - aaaaaaaa - r1",
  revision: 1,
  createdAt: "2026-09-02T12:00:00Z",
};

const validRegistry = () => ({ schemaVersion: 1, layouts: [validLayout] });

describe("Steam Input wire decoders", () => {
  it("decodes the exact bounded registry shape into fresh data", () => {
    const decoded = decodeRadialLayoutRegistry(validRegistry());

    expect(decoded).toEqual(validRegistry());
    expect(decoded).not.toBe(validRegistry());
  });

  it.each([
    ["extra registry field", { ...validRegistry(), leaked: "private" }],
    ["unsafe AppID", { schemaVersion: 1, layouts: [{ ...validLayout, appId: Number.MAX_SAFE_INTEGER + 1 }] }],
    ["boolean AppID", { schemaVersion: 1, layouts: [{ ...validLayout, appId: true }] }],
    ["malformed hash", { schemaVersion: 1, layouts: [{ ...validLayout, trainerSha256: "A".repeat(64) }] }],
    ["unsafe source identifier", { schemaVersion: 1, layouts: [{ ...validLayout, sourceLayoutId: "\u0000" }] }],
    ["unsafe generated name", { schemaVersion: 1, layouts: [{ ...validLayout, generatedLayoutName: " name" }] }],
    [
      "same source and generated identifiers",
      {
        schemaVersion: 1,
        layouts: [{ ...validLayout, generatedLayoutId: validLayout.sourceLayoutId }],
      },
    ],
    ["malformed timestamp", { schemaVersion: 1, layouts: [{ ...validLayout, createdAt: "2026-02-30T12:00:00Z" }] }],
    [
      "extra layout field",
      {
        schemaVersion: 1,
        layouts: [{ ...validLayout, privatePayload: { accountId: "secret" } }],
      },
    ],
  ])("rejects %s", (_name, value) => {
    expect(() => decodeRadialLayoutRegistry(value)).toThrow();
  });

  it("reports non-distinct layout identifiers explicitly", () => {
    expect(() =>
      decodeRadialLayoutRegistry({
        schemaVersion: 1,
        layouts: [{ ...validLayout, generatedLayoutId: validLayout.sourceLayoutId }],
      }),
    ).toThrowError("radial_layout_ids_must_differ");
  });

  it("rejects duplicate records rather than guessing which layout is authoritative", () => {
    expect(() => decodeRadialLayoutRegistry({ schemaVersion: 1, layouts: [validLayout, validLayout] })).toThrowError(
      "duplicate_radial_layout",
    );
  });

  it("decodes only bounded capability statuses and diagnostics", () => {
    const snapshot = {
      appId: validLayout.appId,
      controllerIndex: 0,
      controller: "steam_deck_builtin" as const,
      sourceLayoutId: validLayout.sourceLayoutId,
      sourceLayoutName: "Source Layout",
      runtimeFingerprint: validLayout.steamRuntimeFingerprint,
    };

    expect(decodeSteamInputCapabilityResult({ status: "readonly", snapshot })).toEqual({
      status: "readonly",
      snapshot,
    });
    expect(decodeSteamInputCapabilityResult({ status: "unavailable", diagnostic: "unsupported_runtime" })).toEqual({
      status: "unavailable",
      diagnostic: "unsupported_runtime",
    });
    expect(() => decodeSteamInputCapabilityResult({ status: "mystery", diagnostic: "private payload" })).toThrowError(
      "invalid_steam_input_capability",
    );
    expect(() =>
      decodeSteamInputCapabilityResult({ status: "unavailable", diagnostic: "private payload" }),
    ).toThrowError("invalid_steam_input_capability");
  });
});
