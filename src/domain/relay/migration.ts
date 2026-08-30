import { sidecarProgram } from "../features";
import { LaunchOptions } from "../options";
import { parseLaunchOptions, parseRawWords, type SourceSpan } from "../parser";
import { isAbsoluteExecutablePath } from "./path";
import { parseLaunchIdentity } from "./shortcut";

export type LegacyMigrationPlan =
  | { status: "none" }
  | { status: "blocked" }
  | {
      status: "ready";
      trainerPath: string;
      launchOptions: string;
      changes: "container" | "legacy_and_container";
    };

type MigrationInput = string | LaunchOptions;

const legacyDirectoryName = "PRESSURE_VESSEL_FILESYSTEMS_RW";
const legacyTrainerName = "PROTON_REMOTE_DEBUG_CMD";
const containerReentryName = "UMU_CONTAINER_NSENTER";

const toOptions = (input: MigrationInput): LaunchOptions =>
  typeof input === "string" ? LaunchOptions.parse(input) : input;

const isTrainerPath = (path: string | undefined): path is string =>
  path !== undefined && path.length > 0 && isAbsoluteExecutablePath(path);

const removeLegacyAssignments = (source: string, spans: readonly SourceSpan[]): string =>
  [...spans]
    .sort((left, right) => right.start - left.start)
    .reduce((current, span) => {
      const trailing = /[\t ]/.test(current[span.end] ?? "") ? 1 : 0;
      return current.slice(0, span.start) + current.slice(span.end + trailing);
    }, source);

const prepareContainerReentry = (options: LaunchOptions): LaunchOptions | undefined => {
  const result = options.setEnabled({ kind: "environment", name: containerReentryName, value: "1" }, true);
  return result.ok ? LaunchOptions.parse(result.value.toString().trim()) : undefined;
};

export const planLegacyMigration = (input: MigrationInput, configuredTrainerPath?: string): LegacyMigrationPlan => {
  let options = toOptions(input);
  if (!options.editable) {
    const words = parseRawWords(options.toString());
    if (words?.length !== 1 || parseLaunchIdentity(words[0]) === undefined) return { status: "blocked" };
    if (!configuredTrainerPath) return { status: "none" };
    options = LaunchOptions.parse(`%command% ${words[0]}`);
  }

  const parsed = parseLaunchOptions(options.toString());
  if (parsed.diagnostics.length > 0) return { status: "blocked" };

  const hasTrainer = sidecarProgram.isEnabled(options);
  const hasDirectory = options.hasEnvironment(legacyDirectoryName);
  const containerAssignments = parsed.assignments.filter((assignment) => assignment.name === containerReentryName);
  const containerReady = containerAssignments.length === 1 && containerAssignments[0].value === "1";
  if (!hasTrainer && !hasDirectory && (!configuredTrainerPath || containerReady)) return { status: "none" };
  if (hasTrainer !== hasDirectory) return { status: "blocked" };

  const trainerPath = hasTrainer ? sidecarProgram.path(options) : configuredTrainerPath;
  const legacyAssignments = parsed.assignments.filter(
    (assignment) => assignment.name === legacyTrainerName || assignment.name === legacyDirectoryName,
  );
  if (
    !isTrainerPath(trainerPath) ||
    parsed.assignments.some(
      (assignment) =>
        (assignment.name === legacyTrainerName || assignment.name === legacyDirectoryName) &&
        assignment.value === undefined,
    )
  ) {
    return { status: "blocked" };
  }

  const withoutLegacy = removeLegacyAssignments(
    options.toString(),
    legacyAssignments.map((assignment) => assignment.span),
  );
  const prepared = prepareContainerReentry(LaunchOptions.parse(withoutLegacy));
  if (!prepared?.editable) return { status: "blocked" };
  return {
    status: "ready",
    trainerPath,
    launchOptions: prepared.toString(),
    changes: hasTrainer ? "legacy_and_container" : "container",
  };
};
