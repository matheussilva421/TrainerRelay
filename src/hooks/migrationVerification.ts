import { classifyShortcut } from "../domain/relay/shortcut";
import type { LaunchIdentity } from "../domain/relay/types";

export interface AppDetailsSnapshot {
  command: string;
  launchOptions: string;
}

export interface LegacyMigrationVerificationDependencies {
  appid: number;
  identity: LaunchIdentity;
  expectedSource: string;
  cancelled?: boolean;
  write: (appid: number, source: string) => void | Promise<void>;
  subscribe: (listener: (snapshot: AppDetailsSnapshot) => void) => () => void;
  setTimer: (callback: () => void, milliseconds: number) => unknown;
  clearTimer: (handle: unknown) => void;
  timeoutMs?: number;
}

export type LegacyMigrationVerificationResult =
  | { status: "cancelled" }
  | { status: "verified"; identity: LaunchIdentity }
  | { status: "mismatch"; identity: LaunchIdentity; diagnostic: "launch_options_mismatch" }
  | { status: "identity_changed"; identity: LaunchIdentity }
  | { status: "timeout"; identity: LaunchIdentity; diagnostic: "app_details_timeout" }
  | { status: "error"; identity: LaunchIdentity; diagnostic: "write_failed" };

const DEFAULT_TIMEOUT_MS = 1_000;

export const verifyLegacyMigration = async (
  dependencies: LegacyMigrationVerificationDependencies,
): Promise<LegacyMigrationVerificationResult> => {
  const { appid, identity } = dependencies;
  if (dependencies.cancelled) return { status: "cancelled" };

  let unsubscribe: (() => void) | undefined;
  let timer: unknown;
  let acceptingSnapshots = false;
  let finished = false;
  let resolveResult: (result: LegacyMigrationVerificationResult) => void = () => undefined;

  const resultPromise = new Promise<LegacyMigrationVerificationResult>((resolve) => {
    resolveResult = resolve;
  });

  const finish = (result: LegacyMigrationVerificationResult) => {
    if (finished) return;
    finished = true;
    if (timer !== undefined) dependencies.clearTimer(timer);
    unsubscribe?.();
    resolveResult(result);
  };

  const onSnapshot = (snapshot: AppDetailsSnapshot) => {
    if (!acceptingSnapshots || finished) return;
    const actualIdentity = classifyShortcut(snapshot.command, snapshot.launchOptions);
    if (actualIdentity !== identity) {
      finish({ status: "identity_changed", identity });
      return;
    }
    if (snapshot.launchOptions !== dependencies.expectedSource) {
      finish({ status: "mismatch", identity, diagnostic: "launch_options_mismatch" });
      return;
    }
    finish({ status: "verified", identity });
  };

  try {
    unsubscribe = dependencies.subscribe(onSnapshot);
    timer = dependencies.setTimer(
      () => finish({ status: "timeout", identity, diagnostic: "app_details_timeout" }),
      dependencies.timeoutMs ?? DEFAULT_TIMEOUT_MS,
    );
    // The Steam client may emit the post-write snapshot synchronously. The
    // initial cached snapshot was delivered while acceptingSnapshots was
    // false, so enabling the gate here still requires a fresh requery.
    acceptingSnapshots = true;
    await dependencies.write(appid, dependencies.expectedSource);
  } catch {
    finish({ status: "error", identity, diagnostic: "write_failed" });
  }

  return resultPromise;
};
