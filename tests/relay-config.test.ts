import { describe, expect, it } from "vitest";

import {
  decodeRelayConfig,
  getRelayGameConfig,
  removeRelayGameConfig,
  upsertRelayGameConfig,
} from "../src/domain/relay/config";
import type { RelayConfigV1, RelayGameConfig } from "../src/domain/relay/types";

const validGame: RelayGameConfig = {
  enabled: true,
  trainerPath: "/home/deck/trainers/My Trainer's.exe",
  prefixOverride: "C:\\Users\\deck\\prefix",
};

describe("relay configuration", () => {
  it("decodes schema version 1 and preserves absolute-looking paths", () => {
    const decoded = decodeRelayConfig({
      schemaVersion: 1,
      games: { "epic:game-1": validGame },
    });

    expect(decoded).toEqual({ schemaVersion: 1, games: { "epic:game-1": validGame } });
  });

  it.each([
    undefined,
    null,
    {},
    { schemaVersion: 2, games: {} },
    { schemaVersion: 1 },
    { schemaVersion: 1, games: [] },
    { schemaVersion: 1, games: null },
    '{"schemaVersion":2,"games":{}}',
    "not json",
  ])("falls back for an invalid whole document: %j", (value) => {
    expect(decodeRelayConfig(value)).toEqual({ schemaVersion: 1, games: {} });
  });

  it("omits invalid entries while retaining valid entries", () => {
    expect(
      decodeRelayConfig({
        schemaVersion: 1,
        games: {
          "epic:valid": validGame,
          "steam:unsupported": validGame,
          "gog:": validGame,
          "epic:nested:colon": validGame,
          "gog:bad-enabled": { ...validGame, enabled: "yes" },
          "gog:relative": { ...validGame, trainerPath: "trainers/game.exe" },
          "gog:not-exe": { ...validGame, trainerPath: "/home/deck/trainer.dll" },
          "gog:bad-prefix": { ...validGame, prefixOverride: "prefix" },
          "gog:null": null,
          "gog:extra-is-okay": { ...validGame, unexpected: true },
        },
      }),
    ).toEqual({
      schemaVersion: 1,
      games: {
        "epic:valid": validGame,
        "gog:extra-is-okay": validGame,
      },
    });
  });

  it("accepts JSON text for storage decoding", () => {
    expect(decodeRelayConfig(JSON.stringify({ schemaVersion: 1, games: { "gog:one": validGame } }))).toEqual({
      schemaVersion: 1,
      games: { "gog:one": validGame },
    });
  });

  it("reads a defensive copy of one game", () => {
    const config: RelayConfigV1 = { schemaVersion: 1, games: { "epic:one": validGame } };
    const read = getRelayGameConfig(config, "epic:one");

    expect(read).toEqual(validGame);
    expect(read).not.toBe(validGame);
    if (read) read.trainerPath = "/changed.exe";
    expect(config.games["epic:one"]).toEqual(validGame);
  });

  it("upserts immutably and replaces only the selected game", () => {
    const original: RelayConfigV1 = { schemaVersion: 1, games: { "epic:one": validGame } };
    const nextGame = { ...validGame, enabled: false };
    const updated = upsertRelayGameConfig(original, "gog:two", nextGame);

    expect(updated).toEqual({ schemaVersion: 1, games: { "epic:one": validGame, "gog:two": nextGame } });
    expect(updated).not.toBe(original);
    expect(updated.games).not.toBe(original.games);
    expect(original).toEqual({ schemaVersion: 1, games: { "epic:one": validGame } });
    nextGame.trainerPath = "/mutated-after-upsert.exe";
    expect(updated.games["gog:two"]?.trainerPath).toBe(validGame.trainerPath);
  });

  it("removes one game immutably", () => {
    const original: RelayConfigV1 = { schemaVersion: 1, games: { "epic:one": validGame, "gog:two": validGame } };
    const updated = removeRelayGameConfig(original, "epic:one");

    expect(updated).toEqual({ schemaVersion: 1, games: { "gog:two": validGame } });
    expect(updated).not.toBe(original);
    expect(original.games["epic:one"]).toEqual(validGame);
  });
});
