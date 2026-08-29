import { sidecarProgram } from "../features";
import { LaunchOptions } from "../options";
import { parseLaunchOptions, type SourceSpan } from "../parser";
import { isAbsoluteExecutablePath } from "./path";

export type LegacyMigrationPlan =
  | { status: "none" }
  | { status: "blocked" }
  | { status: "ready"; trainerPath: string; launchOptions: string };

type MigrationInput = string | LaunchOptions;

const legacyDirectoryName = "PRESSURE_VESSEL_FILESYSTEMS_RW";
const legacyTrainerName = "PROTON_REMOTE_DEBUG_CMD";

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

export const planLegacyMigration = (input: MigrationInput): LegacyMigrationPlan => {
  const options = toOptions(input);
  if (!options.editable) return { status: "blocked" };

  const parsed = parseLaunchOptions(options.toString());
  if (parsed.diagnostics.length > 0) return { status: "blocked" };

  const hasTrainer = sidecarProgram.isEnabled(options);
  const hasDirectory = options.hasEnvironment(legacyDirectoryName);
  if (!hasTrainer && !hasDirectory) return { status: "none" };
  if (!hasTrainer || !hasDirectory) return { status: "blocked" };

  const trainerPath = sidecarProgram.path(options);
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

  const launchOptions = removeLegacyAssignments(
    options.toString(),
    legacyAssignments.map((assignment) => assignment.span),
  );
  if (!LaunchOptions.parse(launchOptions).editable) return { status: "blocked" };
  return { status: "ready", trainerPath, launchOptions };
};
