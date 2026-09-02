import type { LaunchIdentity } from "../relay/types";
import type {
  CheatCommandResult,
  CheatControlsResponse,
  CheatDescriptor,
  CheatOperation,
  CheatSource,
  CheatState,
  ManualCheatMutation,
  ManualCheatRemoval,
  SymbolicHotkey,
} from "./types";

export class CheatDecodeError extends Error {
  constructor(readonly code: string) {
    super(code);
    this.name = "CheatDecodeError";
  }
}

const identityPattern = /^(epic|gog):\S{1,256}$/;
const sha256Pattern = /^[0-9a-f]{64}$/;
const idPattern = /^[a-z0-9][a-z0-9._-]{0,127}$|^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const diagnosticPattern = /^[a-z0-9_]{1,64}$/;
const modifiers = ["ctrl", "alt", "shift"] as const;
const modifierSet = new Set<string>(modifiers);
const operations = new Set<CheatOperation>(["enable", "disable", "toggle"]);
const states = new Set<CheatState>(["unknown", "enabled", "disabled"]);
const sources = new Set<CheatSource>(["adapter", "manual", "cooperative"]);
const keys = new Set<string>([
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

const hasControlCharacter = (value: string): boolean =>
  Array.from(value).some((character) => {
    const codePoint = character.codePointAt(0) ?? 0;
    return codePoint <= 31 || codePoint === 127;
  });

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const exactKeys = (value: Record<string, unknown>, expected: readonly string[]): boolean => {
  const actual = Object.keys(value).sort();
  return actual.length === expected.length && actual.every((key, index) => key === [...expected].sort()[index]);
};

export const decodeLaunchIdentity = (value: unknown): LaunchIdentity => {
  if (typeof value !== "string" || !identityPattern.test(value) || hasControlCharacter(value))
    throw new CheatDecodeError("invalid_identity");
  return value as LaunchIdentity;
};

export const decodeTrainerSha256 = (value: unknown): string => {
  if (typeof value !== "string" || !sha256Pattern.test(value)) throw new CheatDecodeError("invalid_trainer_sha256");
  return value;
};

export const decodeCheatId = (value: unknown): string => {
  if (typeof value !== "string" || !idPattern.test(value)) throw new CheatDecodeError("invalid_cheat_id");
  return value;
};

export const decodeLabel = (value: unknown): string => {
  if (
    typeof value !== "string" ||
    value.length < 1 ||
    value.length > 80 ||
    value.trim() !== value ||
    hasControlCharacter(value)
  )
    throw new CheatDecodeError("invalid_label");
  return value;
};

export const decodeHotkey = (value: unknown): SymbolicHotkey => {
  if (!isRecord(value) || !exactKeys(value, ["key", "modifiers"]) || !Array.isArray(value.modifiers))
    throw new CheatDecodeError("invalid_hotkey");
  if (typeof value.key !== "string" || !keys.has(value.key)) throw new CheatDecodeError("invalid_hotkey");
  const seen = new Set<string>();
  for (const modifier of value.modifiers) {
    if (typeof modifier !== "string" || !modifierSet.has(modifier) || seen.has(modifier))
      throw new CheatDecodeError("invalid_hotkey");
    seen.add(modifier);
  }
  return { modifiers: modifiers.filter((modifier) => seen.has(modifier)), key: value.key };
};

export const formatHotkey = (hotkey: SymbolicHotkey): string =>
  [...hotkey.modifiers.map((modifier) => `${modifier[0].toUpperCase()}${modifier.slice(1)}`), hotkey.key].join(" + ");

const decodeDiagnostic = (value: unknown): { code: string } | null => {
  if (value === null) return null;
  if (
    !isRecord(value) ||
    !exactKeys(value, ["code"]) ||
    typeof value.code !== "string" ||
    !diagnosticPattern.test(value.code)
  )
    throw new CheatDecodeError("invalid_diagnostic");
  return { code: value.code };
};

const decodeDescriptor = (value: unknown, source: CheatSource, authoritativeState: boolean): CheatDescriptor => {
  if (!isRecord(value)) throw new CheatDecodeError("invalid_cheat_response");
  const allowed = new Set(["id", "label", "hotkey", "hotkeys", "operations", "state", "authoritative"]);
  if (Object.keys(value).some((key) => !allowed.has(key))) throw new CheatDecodeError("invalid_cheat_response");
  if (source !== "cooperative" && value.hotkey === undefined) throw new CheatDecodeError("invalid_hotkey");
  if (typeof value.state !== "string" || !states.has(value.state as CheatState))
    throw new CheatDecodeError("invalid_cheat_response");
  const state = value.state as CheatState;
  const authoritative = value.authoritative === true;
  if (value.authoritative !== undefined && typeof value.authoritative !== "boolean")
    throw new CheatDecodeError("invalid_cheat_response");
  if ((state !== "unknown" || authoritative) && (source !== "cooperative" || !authoritativeState || !authoritative))
    throw new CheatDecodeError("cheat_state_untrusted");
  const result: CheatDescriptor = { id: decodeCheatId(value.id), label: decodeLabel(value.label), state };
  if (value.hotkey !== undefined) result.hotkey = decodeHotkey(value.hotkey);
  if (value.hotkeys !== undefined) {
    if (!Array.isArray(value.hotkeys) || value.hotkeys.length < 1 || value.hotkeys.length > 8)
      throw new CheatDecodeError("invalid_hotkey");
    result.hotkeys = value.hotkeys.map(decodeHotkey);
  }
  if (value.operations !== undefined) {
    if (
      !Array.isArray(value.operations) ||
      value.operations.length < 1 ||
      new Set(value.operations).size !== value.operations.length ||
      value.operations.some(
        (operation) => typeof operation !== "string" || !operations.has(operation as CheatOperation),
      )
    )
      throw new CheatDecodeError("invalid_cheat_response");
    result.operations = value.operations as CheatOperation[];
  }
  if (value.authoritative !== undefined) result.authoritative = authoritative;
  return result;
};

export const decodeCheatControlsResponse = (
  expectedIdentity: LaunchIdentity,
  input: unknown,
): CheatControlsResponse => {
  if (!isRecord(input) || input.identity !== expectedIdentity) throw new CheatDecodeError("invalid_cheat_response");
  decodeLaunchIdentity(input.identity);
  if (input.status === "waiting" || input.status === "unavailable") {
    if (!exactKeys(input, ["diagnostic", "identity", "status"])) throw new CheatDecodeError("invalid_cheat_response");
    return { identity: expectedIdentity, status: input.status, diagnostic: decodeDiagnostic(input.diagnostic) };
  }
  if (
    input.status !== "ready" ||
    !exactKeys(input, [
      "capabilities",
      "cheats",
      "diagnostic",
      "identity",
      "source",
      "status",
      "trainerLabel",
      "trainerSha256",
    ])
  )
    throw new CheatDecodeError("invalid_cheat_response");
  if (typeof input.source !== "string" || !sources.has(input.source as CheatSource))
    throw new CheatDecodeError("invalid_cheat_response");
  const source = input.source as CheatSource;
  if (
    !isRecord(input.capabilities) ||
    !exactKeys(input.capabilities, ["authoritativeState", "commands", "toggles"]) ||
    Object.values(input.capabilities).some((flag) => typeof flag !== "boolean")
  )
    throw new CheatDecodeError("invalid_cheat_response");
  const capabilities = input.capabilities as { commands: boolean; authoritativeState: boolean; toggles: boolean };
  if (
    (source !== "cooperative" && (capabilities.authoritativeState || capabilities.toggles)) ||
    (capabilities.toggles && !capabilities.authoritativeState)
  )
    throw new CheatDecodeError("cheat_state_untrusted");
  if (
    !Array.isArray(input.cheats) ||
    input.cheats.length > 64 ||
    (input.cheats.length === 0 && source !== "manual") ||
    (input.cheats.length === 0 && capabilities.commands)
  )
    throw new CheatDecodeError("invalid_cheat_response");
  const cheats = input.cheats.map((cheat) => decodeDescriptor(cheat, source, capabilities.authoritativeState));
  if (new Set(cheats.map((cheat) => cheat.id)).size !== cheats.length)
    throw new CheatDecodeError("invalid_cheat_response");
  return {
    identity: expectedIdentity,
    status: "ready",
    trainerSha256: decodeTrainerSha256(input.trainerSha256),
    source,
    trainerLabel: decodeLabel(input.trainerLabel),
    cheats,
    capabilities,
    diagnostic: decodeDiagnostic(input.diagnostic),
  };
};

export const decodeCheatCommandResult = (
  expectedIdentity: LaunchIdentity,
  expectedCheatId: string,
  input: unknown,
  options: { allowAuthoritativeState?: boolean } = {},
): CheatCommandResult => {
  if (
    !isRecord(input) ||
    !exactKeys(input, ["cheatId", "commandId", "diagnostic", "identity", "outcome", "state"]) ||
    input.identity !== expectedIdentity ||
    input.cheatId !== expectedCheatId ||
    typeof input.commandId !== "string" ||
    !uuidPattern.test(input.commandId) ||
    !["requested", "failed", "rejected"].includes(String(input.outcome)) ||
    typeof input.state !== "string" ||
    !states.has(input.state as CheatState)
  )
    throw new CheatDecodeError("invalid_cheat_response");
  const state = input.state as CheatState;
  if (state !== "unknown" && !options.allowAuthoritativeState) throw new CheatDecodeError("cheat_state_untrusted");
  if (input.outcome !== "requested" && state !== "unknown") throw new CheatDecodeError("cheat_state_untrusted");
  const diagnostic = decodeDiagnostic(input.diagnostic);
  if (input.outcome !== "requested" && diagnostic === null) throw new CheatDecodeError("invalid_cheat_response");
  return {
    commandId: input.commandId,
    identity: expectedIdentity,
    cheatId: expectedCheatId,
    outcome: input.outcome as CheatCommandResult["outcome"],
    state,
    diagnostic,
  };
};

export const decodeManualMutation = (identity: LaunchIdentity, input: unknown): ManualCheatMutation => {
  if (!isRecord(input) || !exactKeys(input, ["cheat", "identity", "trainerSha256"]) || input.identity !== identity)
    throw new CheatDecodeError("invalid_cheat_response");
  const cheat = decodeDescriptor(input.cheat, "manual", false);
  return { identity, trainerSha256: decodeTrainerSha256(input.trainerSha256), cheat };
};

export const decodeManualRemoval = (identity: LaunchIdentity, cheatId: string, input: unknown): ManualCheatRemoval => {
  if (
    !isRecord(input) ||
    !exactKeys(input, ["cheatId", "identity", "removed"]) ||
    input.identity !== identity ||
    input.cheatId !== cheatId ||
    typeof input.removed !== "boolean"
  )
    throw new CheatDecodeError("invalid_cheat_response");
  return { identity, cheatId, removed: input.removed };
};
