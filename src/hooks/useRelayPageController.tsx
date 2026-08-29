import { useEffect, useMemo, useState } from "react";
import type { LegacyMigrationPlan } from "../domain/relay/migration";
import { isAbsolutePath } from "../domain/relay/path";
import type { LaunchIdentity, RelayConfigV1, RelayGameConfig } from "../domain/relay/types";
import { buildTrainerRelayViewModel } from "../domain/relay/viewModel";
import { browseFiles, getHomePath, sendNotice } from "../infra/decky";
import { emptyRelayConfig, persistRelayGameConfig, relayRpc } from "../infra/relayRpc";
import { bindBrowserTimers } from "./browserTimers";
import { activateVerifiedLegacyMigration } from "./legacyMigrationActivation";
import type { LegacyMigrationVerificationResult } from "./migrationVerification";
import { disableTrainerRelay, enableTrainerRelay, selectTrainerPath } from "./relayActions";
import { startRelayStatusPolling } from "./statusPolling";
import { useRelayAppDetails } from "./useRelayAppDetails";

type ConfigState = { status: "loading" | "ready" | "error"; value: RelayConfigV1 };
type ReadyMigration = Extract<LegacyMigrationPlan, { status: "ready" }>;

const defaultGameConfig = (): RelayGameConfig => ({ enabled: false, trainerPath: "" });

const migrationResultMessage = (result: LegacyMigrationVerificationResult): string => {
  switch (result.status) {
    case "verified":
      return "Launch options migrated, verified, and Trainer Relay enabled.";
    case "cancelled":
      return "Migration cancelled. Trainer Relay remains disabled.";
    case "mismatch":
      return "Steam returned different launch options. Trainer Relay remains disabled.";
    case "identity_changed":
      return "The shortcut identity changed during migration. Trainer Relay remains disabled.";
    case "timeout":
      return "Steam did not confirm the migration in time. Trainer Relay remains disabled.";
    case "error":
      return "The launch options could not be written. Trainer Relay remains disabled.";
  }
};

export const useRelayPageController = (appid: number) => {
  const browserTimers = bindBrowserTimers(window);
  const appDetails = useRelayAppDetails(appid);
  const [configState, setConfigState] = useState<ConfigState>({
    status: "loading",
    value: emptyRelayConfig(),
  });
  const [relayStatus, setRelayStatus] = useState<Awaited<ReturnType<typeof relayRpc.getRelayStatus>>>();
  const [busy, setBusy] = useState(false);
  const [migrationBusy, setMigrationBusy] = useState(false);
  const [migrationMessage, setMigrationMessage] = useState<string>();
  const [prefixDraft, setPrefixDraft] = useState("");

  useEffect(() => {
    let active = true;
    setConfigState({ status: "loading", value: emptyRelayConfig() });
    void relayRpc
      .getRelayConfig()
      .then((value) => {
        if (active) setConfigState({ status: "ready", value });
      })
      .catch(() => {
        if (active) setConfigState({ status: "error", value: emptyRelayConfig() });
      });
    return () => {
      active = false;
    };
  }, []);

  const identityModel = useMemo(
    () => buildTrainerRelayViewModel(appDetails.details, undefined, relayStatus),
    [appDetails.details, relayStatus],
  );
  const identity = identityModel.kind === "supported" ? identityModel.identity : undefined;
  const config = identity ? configState.value.games[identity] : undefined;
  const model = useMemo(
    () => buildTrainerRelayViewModel(appDetails.details, config, relayStatus),
    [appDetails.details, config, relayStatus],
  );

  useEffect(() => {
    setPrefixDraft(config?.prefixOverride ?? "");
  }, [identity, config?.prefixOverride]);

  useEffect(() => {
    setRelayStatus(undefined);
    if (!identity) return;
    return startRelayStatusPolling({
      identity,
      poll: () => relayRpc.getRelayStatus({ identity }),
      onStatus: setRelayStatus,
      setInterval: browserTimers.setInterval,
      clearInterval: browserTimers.clearInterval,
    });
  }, [identity]);

  const updateGameConfig = (targetIdentity: LaunchIdentity, next: RelayGameConfig) => {
    setConfigState((current) => ({
      status: "ready",
      value: { schemaVersion: 1, games: { ...current.value.games, [targetIdentity]: next } },
    }));
  };

  const chooseTrainer = async () => {
    if (model.kind !== "supported" || configState.status !== "ready") return;
    setBusy(true);
    try {
      const home = await getHomePath();
      const selection = await browseFiles(home, true, ["exe"]);
      const result = await selectTrainerPath(relayRpc, model.identity, config ?? defaultGameConfig(), selection.path);
      if (result.status === "persisted_disabled") {
        updateGameConfig(model.identity, result.config);
        setMigrationMessage("Trainer selected. Enable it explicitly when ready.");
      } else {
        sendNotice("Trainer path could not be saved; relay remains disabled.");
      }
    } catch {
      sendNotice("Trainer selection cancelled or unavailable.");
    } finally {
      setBusy(false);
    }
  };

  const toggleRelay = async (enabled: boolean) => {
    if (model.kind !== "supported" || configState.status !== "ready") return;
    const current = config ?? defaultGameConfig();
    setBusy(true);
    try {
      const result = enabled
        ? await enableTrainerRelay(relayRpc, model.identity, current, model.migration)
        : await disableTrainerRelay(relayRpc, model.identity, current);
      if (result.status === "enabled" || result.status === "disabled") updateGameConfig(model.identity, result.config);
      else if (result.status === "blocked")
        sendNotice("Choose a valid .exe and complete launch-option migration first.");
      else sendNotice("Relay configuration could not be saved; it remains disabled.");
    } finally {
      setBusy(false);
    }
  };

  const savePrefix = async () => {
    if (model.kind !== "supported" || configState.status !== "ready") return;
    const prefix = prefixDraft.trim();
    if (prefix && !isAbsolutePath(prefix)) {
      sendNotice("Prefix override must be an absolute path.");
      return;
    }
    setBusy(true);
    try {
      const current = config ?? defaultGameConfig();
      const next: RelayGameConfig = {
        enabled: false,
        trainerPath: current.trainerPath,
        ...(prefix ? { prefixOverride: prefix } : {}),
      };
      updateGameConfig(model.identity, await persistRelayGameConfig(relayRpc, model.identity, next));
      setMigrationMessage("Prefix saved with relay disabled. Enable it explicitly afterward.");
    } catch {
      sendNotice("Prefix override could not be saved; relay remains disabled.");
    } finally {
      setBusy(false);
    }
  };

  const retry = async () => {
    if (model.kind !== "supported" || relayStatus?.state !== "failed") return;
    setBusy(true);
    try {
      setRelayStatus(await relayRpc.retryRelay({ identity: model.identity }));
    } catch {
      sendNotice("Retry was rejected; the game was not changed.");
    } finally {
      setBusy(false);
    }
  };

  const migrate = async (supportedIdentity: LaunchIdentity, plan: ReadyMigration) => {
    if (configState.status !== "ready" || identity !== supportedIdentity) return;
    setMigrationBusy(true);
    try {
      const result = await activateVerifiedLegacyMigration({
        rpc: relayRpc,
        identity: supportedIdentity,
        current: config ?? defaultGameConfig(),
        trainerPath: plan.trainerPath,
        verification: {
          appid,
          identity: supportedIdentity,
          expectedSource: plan.launchOptions,
          write: (targetAppid, source) => {
            if (targetAppid !== appid) throw new Error("appid_changed");
            appDetails.writeLaunchOptions(source);
          },
          subscribe: appDetails.subscribe,
          setTimer: browserTimers.setTimeout,
          clearTimer: browserTimers.clearTimeout,
        },
      });
      updateGameConfig(supportedIdentity, result.config);
      if (result.status === "enabled") {
        setMigrationMessage("Launch options migrated, verified, and Trainer Relay enabled.");
      } else if (result.status === "verification_failed") {
        setMigrationMessage(migrationResultMessage(result.verification));
      } else {
        setMigrationMessage("Migration could not begin or finish safely. Trainer Relay remains disabled.");
      }
    } finally {
      setMigrationBusy(false);
    }
  };

  return {
    model,
    configState,
    currentConfig: config ?? defaultGameConfig(),
    busy,
    migrationBusy,
    migrationMessage,
    prefixDraft,
    setPrefixDraft,
    chooseTrainer,
    toggleRelay,
    savePrefix,
    retry,
    migrate,
  };
};
