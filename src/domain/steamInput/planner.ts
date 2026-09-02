import { formatHotkey } from "../cheats/decoder";
import type { CheatDescriptor, ReadyCheatControls, SymbolicHotkey } from "../cheats/types";
import type {
  BuildRadialPlanInput,
  Sha256Digest,
  SteamInputCommandItem,
  SteamInputRadialPage,
  SteamInputRadialPlanV1,
} from "./types";

const hotkeyModifiers = new Set(["ctrl", "alt", "shift"]);
const hotkeyModifierOrder = ["ctrl", "alt", "shift"] as const;
const hotkeyKeys = new Set([
  ...Array.from({ length: 26 }, (_, index) => String.fromCharCode(65 + index)),
  ...Array.from({ length: 10 }, (_, index) => String(index)),
  ...Array.from({ length: 24 }, (_, index) => `F${index + 1}`),
  ...Array.from({ length: 10 }, (_, index) => `NUMPAD${index}`),
  "MULTIPLY",
  "ADD",
  "SUBTRACT",
  "DECIMAL",
  "DIVIDE",
  "INSERT",
  "DELETE",
  "HOME",
  "END",
  "PAGEUP",
  "PAGEDOWN",
  "UP",
  "DOWN",
  "LEFT",
  "RIGHT",
  "SPACE",
  "TAB",
  "ENTER",
  "BACKSPACE",
  "PAUSE",
  "CAPSLOCK",
  "SCROLLLOCK",
  "NUMLOCK",
]);

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const maximumLabelLength = 80;

const hasControlCharacter = (value: string): boolean =>
  Array.from(value).some((character) => {
    const codePoint = character.codePointAt(0) ?? 0;
    return codePoint <= 31 || (codePoint >= 0x7f && codePoint <= 0x9f);
  });

const isValidLabel = (value: unknown): value is string =>
  typeof value === "string" &&
  value.length >= 1 &&
  value.length <= maximumLabelLength &&
  value.trim() === value &&
  !hasControlCharacter(value);

const isValidHotkey = (value: unknown): value is SymbolicHotkey => {
  if (!isRecord(value) || !Array.isArray(value.modifiers) || typeof value.key !== "string") return false;
  if (!hotkeyKeys.has(value.key)) return false;
  const modifiers = value.modifiers;
  return (
    modifiers.every((modifier) => typeof modifier === "string" && hotkeyModifiers.has(modifier)) &&
    new Set(modifiers).size === modifiers.length
  );
};

const normalizeHotkey = (hotkey: SymbolicHotkey): SymbolicHotkey => ({
  modifiers: hotkeyModifierOrder.filter((modifier) => hotkey.modifiers.includes(modifier)),
  key: hotkey.key,
});

const hotkeyChord = (hotkey: SymbolicHotkey): string => JSON.stringify(normalizeHotkey(hotkey));

const compactHotkey = (hotkey: SymbolicHotkey): string => formatHotkey(hotkey).replace(/ \+ /g, "+");

const labelWithHotkey = (label: string, hotkey: SymbolicHotkey): string => {
  const suffix = ` (${compactHotkey(hotkey)})`;
  const boundedLabel = label.slice(0, maximumLabelLength - suffix.length).trimEnd();
  return `${boundedLabel}${suffix}`;
};

const hotkeysFor = (cheat: CheatDescriptor): unknown[] => {
  if (Array.isArray(cheat.hotkeys)) return cheat.hotkeys;
  return cheat.hotkey === undefined ? [] : [cheat.hotkey];
};

export const buildSteamInputCommandItems = (controls: ReadyCheatControls): SteamInputCommandItem[] => {
  if (controls.capabilities.commands !== true) return [];

  const items: SteamInputCommandItem[] = [];
  for (const cheat of controls.cheats) {
    if (!isRecord(cheat) || typeof cheat.id !== "string" || !isValidLabel(cheat.label)) continue;

    const seenChords = new Set<string>();
    const validHotkeys: SymbolicHotkey[] = [];
    for (const candidate of hotkeysFor(cheat)) {
      if (!isValidHotkey(candidate)) continue;
      const chord = hotkeyChord(candidate);
      if (seenChords.has(chord)) continue;
      seenChords.add(chord);
      validHotkeys.push(candidate);
    }

    const appendHotkey = validHotkeys.length > 1;
    for (const [index, hotkey] of validHotkeys.entries()) {
      const normalizedHotkey = normalizeHotkey(hotkey);
      items.push({
        itemId: `${cheat.id}:${index}`,
        cheatId: cheat.id,
        label: appendHotkey ? labelWithHotkey(cheat.label, normalizedHotkey) : cheat.label,
        hotkey: normalizedHotkey,
      });
    }
  }
  return items;
};

export const canonicalizeCheatAuthority = (controls: ReadyCheatControls): string =>
  JSON.stringify({
    identity: controls.identity,
    trainerSha256: controls.trainerSha256,
    source: controls.source,
    commands: buildSteamInputCommandItems(controls).map(({ itemId, cheatId, label, hotkey }) => ({
      itemId,
      cheatId,
      label,
      hotkey,
    })),
  });

export const computeCatalogFingerprint = async (
  controls: ReadyCheatControls,
  digest: Sha256Digest,
): Promise<string> => {
  const result = await digest(new TextEncoder().encode(canonicalizeCheatAuthority(controls)));
  if (result.length !== 32) throw new Error("invalid_sha256_digest");
  return Array.from(result, (byte) => byte.toString(16).padStart(2, "0")).join("");
};

const sha256Pattern = /^[0-9a-f]{64}$/;
const pageSize = 6;

export const buildSteamInputRadialPlan = (input: BuildRadialPlanInput): SteamInputRadialPlanV1 => {
  if (!Number.isSafeInteger(input.appId) || input.appId <= 0) throw new Error("invalid_app_id");
  if (input.identity !== input.controls.identity) throw new Error("identity_mismatch");
  if (!sha256Pattern.test(input.trainerSha256)) throw new Error("invalid_trainer_sha256");
  if (input.trainerSha256 !== input.controls.trainerSha256) throw new Error("trainer_sha256_mismatch");
  if (!sha256Pattern.test(input.catalogFingerprint)) throw new Error("invalid_catalog_fingerprint");

  const commands = buildSteamInputCommandItems(input.controls);
  if (commands.length === 0) throw new Error("no_commands");

  const pageCount = Math.ceil(commands.length / pageSize);
  const pages: SteamInputRadialPage[] = Array.from({ length: pageCount }, (_, pageIndex) => {
    const page = pageIndex + 1;
    const radialPage: SteamInputRadialPage = {
      page,
      items: commands.slice(pageIndex * pageSize, (pageIndex + 1) * pageSize),
    };
    if (page > 1) radialPage.previousPage = page - 1;
    if (page < pageCount) radialPage.nextPage = page + 1;
    return radialPage;
  });

  return {
    schemaVersion: 1,
    appId: input.appId,
    identity: input.identity,
    trainerSha256: input.trainerSha256,
    catalogFingerprint: input.catalogFingerprint,
    controller: "steam_deck_builtin",
    input: "left_trackpad",
    activation: "physical_click",
    pages,
  };
};
