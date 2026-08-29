import type { LaunchOptions } from "../options";
import { parseLaunchOptions, parseLiteralWord, parseRawWords } from "../parser";

import type { LaunchIdentity } from "./types";

export type LaunchOptionsInput = string | LaunchOptions;

const supportedIdentity = /^(epic|gog):[^\s:]+$/;

const sourceOf = (launchOptions: LaunchOptionsInput): string =>
  typeof launchOptions === "string" ? launchOptions : launchOptions.toString();

export const parseLaunchIdentity = (word: string): LaunchIdentity | undefined => {
  const literal = parseLiteralWord(word);
  if (literal === undefined) return undefined;
  const match = supportedIdentity.exec(literal);
  return match === null ? undefined : (literal as LaunchIdentity);
};

const normalizeCommand = (command: string): string => {
  const first = command[0];
  if (first !== "'" && first !== '"') return command;
  return parseLiteralWord(command) ?? command;
};

export const commandBasename = (command: string): string => {
  const normalized = normalizeCommand(command);
  return normalized.slice(Math.max(normalized.lastIndexOf("/"), normalized.lastIndexOf("\\")) + 1);
};

const isExactLauncher = (command: string): boolean =>
  commandBasename(command).toLocaleLowerCase() === "unifideck-launcher";

const isLiteral = (word: string): boolean => parseLiteralWord(word) !== undefined;

const classifyMarkerSource = (source: string): LaunchIdentity | undefined => {
  const parsed = parseLaunchOptions(source);
  if (parsed.diagnostics.length > 0 || parsed.implicitMarker) return undefined;
  if (parsed.assignments.some((assignment) => assignment.value === undefined)) return undefined;
  if (parsed.prefixes.some((prefix) => prefix.words.some((word) => !isLiteral(word.raw)))) return undefined;
  if (parsed.arguments.some((word) => !isLiteral(word.raw))) return undefined;

  const identities = parsed.arguments
    .map((word) => parseLaunchIdentity(word.raw))
    .filter((identity): identity is LaunchIdentity => identity !== undefined);
  return identities.length === 1 ? identities[0] : undefined;
};

const classifyPlainSource = (source: string): LaunchIdentity | undefined => {
  const words = parseRawWords(source);
  if (words?.length !== 1) return undefined;
  return parseLaunchIdentity(words[0]);
};

export const classifyShortcut = (command: string, launchOptions: LaunchOptionsInput): LaunchIdentity | undefined => {
  if (!isExactLauncher(command)) return undefined;
  const source = sourceOf(launchOptions);
  return source.includes("%command%") ? classifyMarkerSource(source) : classifyPlainSource(source);
};
