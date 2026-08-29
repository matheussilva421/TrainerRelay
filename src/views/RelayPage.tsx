import {
  ConfirmModal,
  DialogButton,
  Field,
  Focusable,
  Navigation,
  PanelSection,
  PanelSectionRow,
  showModal,
  TextField,
  ToggleField,
} from "@decky/ui";
import { type FC, useEffect, useMemo, useState } from "react";
import { FaArrowsRotate, FaFolderOpen, FaShieldHalved } from "react-icons/fa6";
import type { LegacyMigrationPlan } from "../domain/relay/migration";
import type { LaunchIdentity, RelayConfigV1, RelayGameConfig } from "../domain/relay/types";
import { buildTrainerRelayViewModel, formatRelayStatus } from "../domain/relay/viewModel";
import { type LegacyMigrationVerificationResult, verifyLegacyMigration } from "../hooks/migrationVerification";
import { disableTrainerRelay, enableTrainerRelay, selectTrainerPath } from "../hooks/relayActions";
import { startRelayStatusPolling } from "../hooks/statusPolling";
import { useRelayAppDetails } from "../hooks/useRelayAppDetails";
import { browseFiles, getHomePath, sendNotice } from "../infra/decky";
import { emptyRelayConfig, persistRelayGameConfig, relayRpc } from "../infra/relayRpc";

const absolutePath = (value: string): boolean => value.startsWith("/") || /^[A-Za-z]:[\\/]/.test(value);

const defaultGameConfig = (): RelayGameConfig => ({ enabled: false, trainerPath: "" });

const migrationDescription = (plan: LegacyMigrationPlan): string => {
  if (plan.status === "ready") return `Trainer found: ${plan.trainerPath}`;
  if (plan.status === "blocked")
    return "Legacy trainer launch options are incomplete or unsafe. Repair them manually before configuring Trainer Relay.";
  return "";
};

const migrationResultMessage = (result: LegacyMigrationVerificationResult): string => {
  switch (result.status) {
    case "verified":
      return "Launch options migrated and verified.";
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

const RelayPage: FC<{ appid: number }> = ({ appid }) => {
  const appDetails = useRelayAppDetails(appid);
  const [configState, setConfigState] = useState<{ status: "loading" | "ready" | "error"; value: RelayConfigV1 }>({
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
      setInterval: window.setInterval,
      clearInterval: (handle) => window.clearInterval(handle as number),
    });
  }, [identity]);

  const updateGameConfig = (next: RelayGameConfig) => {
    if (!identity) return;
    setConfigState((current) => ({
      status: "ready",
      value: { schemaVersion: 1, games: { ...current.value.games, [identity]: next } },
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
        updateGameConfig(result.config);
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
      if (result.status === "enabled" || result.status === "disabled") updateGameConfig(result.config);
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
    if (prefix && !absolutePath(prefix)) {
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
      updateGameConfig(await persistRelayGameConfig(relayRpc, model.identity, next));
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

  const confirmMigration = (
    supportedIdentity: LaunchIdentity,
    plan: Extract<LegacyMigrationPlan, { status: "ready" }>,
  ) => {
    showModal(
      <ConfirmModal
        strTitle="Migrate legacy trainer settings?"
        strDescription={`Trainer Relay found ${plan.trainerPath}. It will remove only PROTON_REMOTE_DEBUG_CMD and PRESSURE_VESSEL_FILESYSTEMS_RW, preserving the rest of the launch options.`}
        strOKButtonText="Migrate"
        strCancelButtonText="Cancel"
        onCancel={() => undefined}
        onOK={() => {
          void (async () => {
            setMigrationBusy(true);
            const result = await verifyLegacyMigration({
              appid,
              identity: supportedIdentity,
              expectedSource: plan.launchOptions,
              write: (targetAppid, source) => {
                if (targetAppid !== appid) throw new Error("appid_changed");
                appDetails.writeLaunchOptions(source);
              },
              subscribe: appDetails.subscribe,
              setTimer: window.setTimeout,
              clearTimer: (handle) => window.clearTimeout(handle as number),
            });
            setMigrationMessage(migrationResultMessage(result));
            setMigrationBusy(false);
          })();
        }}
        bOKDisabled={migrationBusy}
      />,
      window,
    );
  };

  if (model.kind === "loading")
    return (
      <PanelSection title={model.heading} spinner>
        <PanelSectionRow>
          <Field description={model.message} padding="standard" />
        </PanelSectionRow>
      </PanelSection>
    );
  if (model.kind === "error")
    return (
      <PanelSection title={model.heading}>
        <PanelSectionRow>
          <Field description={model.message} padding="standard" />
        </PanelSectionRow>
      </PanelSection>
    );
  if (model.kind === "unsupported") {
    return (
      <PanelSection title={model.heading}>
        <PanelSectionRow>
          <Field
            icon={<FaShieldHalved />}
            label="Unsupported shortcut"
            description={model.message}
            padding="standard"
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <DialogButton
            onClick={() => {
              Navigation.CloseSideMenus();
              Navigation.NavigateToExternalWeb(model.repositoryUrl);
            }}
          >
            Open GitHub
          </DialogButton>
        </PanelSectionRow>
      </PanelSection>
    );
  }

  const currentConfig = config ?? defaultGameConfig();
  const controlsDisabled = busy || migrationBusy || configState.status !== "ready" || model.migration.status !== "none";
  const readyMigration = model.migration.status === "ready" ? model.migration : undefined;
  const statusText = formatRelayStatus(model.status);
  const statusExplanation =
    model.status.state === "ambiguous" || model.status.state === "invalid_config"
      ? "Nothing was launched because the session could not be identified safely."
      : model.status.state === "failed"
        ? "The trainer failed without affecting the game."
        : "The watcher is monitoring the game session.";

  return (
    <Focusable style={{ display: "flex", flexDirection: "column" }}>
      <PanelSection title="Trainer Relay">
        <PanelSectionRow>
          <Field label="Launch identity" description={model.identity} padding="standard" bottomSeparator="standard" />
        </PanelSectionRow>
        <PanelSectionRow>
          <Field
            label="Status"
            description={`${statusText}. ${statusExplanation}`}
            padding="standard"
            bottomSeparator="standard"
          />
        </PanelSectionRow>
        {configState.status === "error" && (
          <PanelSectionRow>
            <Field
              description="Relay configuration is unavailable. Nothing can be changed."
              padding="standard"
              bottomSeparator="standard"
            />
          </PanelSectionRow>
        )}
        {readyMigration && (
          <PanelSectionRow>
            <Field
              label="Legacy migration"
              description={migrationDescription(readyMigration)}
              padding="standard"
              childrenLayout="below"
              bottomSeparator="standard"
            >
              <DialogButton
                disabled={migrationBusy || configState.status !== "ready"}
                onClick={() => confirmMigration(model.identity, readyMigration)}
              >
                Confirm migration
              </DialogButton>
            </Field>
          </PanelSectionRow>
        )}
        {model.migration.status === "blocked" && (
          <PanelSectionRow>
            <Field
              label="Legacy migration"
              description={migrationDescription(model.migration)}
              padding="standard"
              bottomSeparator="standard"
            />
          </PanelSectionRow>
        )}
        {migrationMessage && (
          <PanelSectionRow>
            <Field description={migrationMessage} padding="standard" bottomSeparator="standard" />
          </PanelSectionRow>
        )}
      </PanelSection>

      <PanelSection title="Configuration">
        <PanelSectionRow>
          <Field
            label="Trainer executable"
            description="Select one absolute .exe file. Selecting it saves a disabled configuration."
            padding="standard"
            childrenLayout="below"
            bottomSeparator="standard"
          >
            <DialogButton disabled={controlsDisabled} onClick={() => void chooseTrainer()}>
              <FaFolderOpen /> {currentConfig.trainerPath || "Choose trainer"}
            </DialogButton>
          </Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field
            label="Prefix override (advanced)"
            description="Optional absolute Wine prefix directory. Leave empty to use UniFiDeck's prefix."
            padding="standard"
            childrenLayout="below"
            bottomSeparator="standard"
          >
            <TextField
              disabled={controlsDisabled || !currentConfig.trainerPath}
              value={prefixDraft}
              onChange={(event) => setPrefixDraft(event.currentTarget.value)}
            />
            <DialogButton
              disabled={
                controlsDisabled ||
                !currentConfig.trainerPath ||
                prefixDraft.trim() === (currentConfig.prefixOverride ?? "")
              }
              onClick={() => void savePrefix()}
            >
              Save prefix
            </DialogButton>
          </Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label="Enabled"
            description="Trainer Relay never enables itself after browsing or migration."
            checked={currentConfig.enabled}
            disabled={controlsDisabled || !currentConfig.trainerPath}
            onChange={(enabled) => void toggleRelay(enabled)}
          />
        </PanelSectionRow>
        {model.controls.retry && (
          <PanelSectionRow>
            <DialogButton disabled={busy} onClick={() => void retry()}>
              <FaArrowsRotate /> Retry trainer
            </DialogButton>
          </PanelSectionRow>
        )}
      </PanelSection>
    </Focusable>
  );
};

export default RelayPage;
