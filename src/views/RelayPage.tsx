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
import type { FC } from "react";
import { FaArrowsRotate, FaFolderOpen, FaShieldHalved } from "react-icons/fa6";
import type { LegacyMigrationPlan } from "../domain/relay/migration";
import type { LaunchIdentity } from "../domain/relay/types";
import { formatRelayStatus } from "../domain/relay/viewModel";
import { useRelayPageController } from "../hooks/useRelayPageController";

const migrationDescription = (plan: LegacyMigrationPlan): string => {
  if (plan.status === "ready") return `Trainer found: ${plan.trainerPath}`;
  if (plan.status === "blocked")
    return "Legacy trainer launch options are incomplete or unsafe. Repair them manually before configuring Trainer Relay.";
  return "";
};

const RelayPage: FC<{ appid: number }> = ({ appid }) => {
  const controller = useRelayPageController(appid);
  const {
    model,
    configState,
    currentConfig,
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
  } = controller;

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
        onOK={() => void migrate(supportedIdentity, plan)}
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
            description="Browsing saves disabled. A verified legacy migration enables the discovered trainer automatically."
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
