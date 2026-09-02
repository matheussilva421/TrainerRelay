import { ConfirmModal, DialogButton, Field, Focusable, showModal, TextField, ToggleField } from "@decky/ui";
import type { FC } from "react";
import { FaArrowsRotate, FaShieldHalved } from "react-icons/fa6";
import { CheatControlList } from "../components/CheatControlList";
import { ManualCheatEditor } from "../components/ManualCheatEditor";
import { SteamInputRadialMenu } from "../components/SteamInputRadialMenu";
import { TrainerFilePicker } from "../components/TrainerFilePicker";
import type { LegacyMigrationPlan } from "../domain/relay/migration";
import type { LaunchIdentity } from "../domain/relay/types";
import { formatRelayStatus } from "../domain/relay/viewModel";
import { useCheatControls } from "../hooks/useCheatControls";
import { useRelayPageController } from "../hooks/useRelayPageController";

const migrationDescription = (plan: LegacyMigrationPlan): string => {
  if (plan.status === "ready" && plan.changes === "container")
    return "Prepare UMU container re-entry before enabling the trainer. The game launch remains otherwise unchanged.";
  if (plan.status === "ready")
    return `Trainer found: ${plan.trainerPath}. Legacy options will be removed and UMU container re-entry prepared.`;
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
  const cheatIdentity = model.kind === "supported" ? model.identity : undefined;
  const cheatControls = useCheatControls(cheatIdentity);

  const confirmMigration = (
    supportedIdentity: LaunchIdentity,
    plan: Extract<LegacyMigrationPlan, { status: "ready" }>,
  ) => {
    const containerOnly = plan.changes === "container";
    showModal(
      <ConfirmModal
        strTitle={containerOnly ? "Prepare UMU container re-entry?" : "Migrate legacy trainer settings?"}
        strDescription={
          containerOnly
            ? "Trainer Relay will add UMU_CONTAINER_NSENTER=1 to this shortcut so the game exposes a container service that the trainer can re-enter. Other launch options are preserved."
            : `Trainer Relay found ${plan.trainerPath}. It will remove only PROTON_REMOTE_DEBUG_CMD and PRESSURE_VESSEL_FILESYSTEMS_RW, add UMU_CONTAINER_NSENTER=1, and preserve the rest.`
        }
        strOKButtonText={containerOnly ? "Prepare" : "Migrate"}
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
      <Focusable style={{ display: "flex", flexDirection: "column" }}>
        <Field label={model.heading} description={model.message} padding="standard" bottomSeparator="standard" />
      </Focusable>
    );
  if (model.kind === "error")
    return (
      <Focusable style={{ display: "flex", flexDirection: "column" }}>
        <Field label={model.heading} description={model.message} padding="standard" bottomSeparator="standard" />
      </Focusable>
    );
  if (model.kind === "unsupported") {
    return (
      <Focusable style={{ display: "flex", flexDirection: "column" }}>
        <Field
          icon={<FaShieldHalved />}
          label="Unsupported shortcut"
          description={model.message}
          padding="standard"
          bottomSeparator="standard"
        />
      </Focusable>
    );
  }

  const configurationDisabled = busy || migrationBusy || configState.status !== "ready";
  const readyMigration = model.migration.status === "ready" ? model.migration : undefined;
  const statusText = formatRelayStatus(model.status);
  const statusExplanation =
    model.status.diagnosticCode === "container_reentry_missing"
      ? "Restart the game after completing UMU container preparation. Nothing was launched."
      : model.status.state === "ambiguous" || model.status.state === "invalid_config"
        ? "Nothing was launched because the session could not be identified safely."
        : model.status.state === "failed"
          ? "The trainer failed without affecting the game."
          : "The watcher is monitoring the game session.";

  return (
    <Focusable style={{ display: "flex", flexDirection: "column" }}>
      <Field label="Launch identity" description={model.identity} padding="standard" bottomSeparator="standard" />
      <Field
        label="Status"
        description={`${statusText}. ${statusExplanation}`}
        padding="standard"
        bottomSeparator="standard"
      />
      {cheatControls.response?.status === "ready" ? (
        <>
          <CheatControlList
            controls={cheatControls.response}
            busy={cheatControls.busy || busy || migrationBusy}
            onCommand={(cheatId) => cheatControls.sendCommand(cheatId)}
            lastResults={cheatControls.lastResults}
          />
          <SteamInputRadialMenu
            appId={appid}
            identity={cheatControls.response.identity}
            controls={cheatControls.response}
          />
          {cheatControls.response.source === "manual" && (
            <ManualCheatEditor
              ready={true}
              trainerSha256={cheatControls.response.trainerSha256}
              busy={cheatControls.busy || busy || migrationBusy}
              cheats={cheatControls.response.cheats}
              onAdd={(label, hotkey) => cheatControls.addManualCheatControl(label, hotkey)}
              onRemove={(cheatId) => cheatControls.removeManualCheatControl(cheatId)}
            />
          )}
        </>
      ) : (
        <Field
          label="Cheat controls"
          description={
            cheatControls.error
              ? `Controles indisponíveis (${cheatControls.error}). Nenhum comando foi enviado.`
              : "Aguardando uma resposta segura do Trainer Relay."
          }
          padding="standard"
          bottomSeparator="standard"
        />
      )}
      {configState.status === "error" && (
        <Field
          description="Relay configuration is unavailable. Nothing can be changed."
          padding="standard"
          bottomSeparator="standard"
        />
      )}
      {readyMigration && (
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
            {readyMigration.changes === "container" ? "Prepare UMU container re-entry" : "Confirm migration"}
          </DialogButton>
        </Field>
      )}
      {model.migration.status === "blocked" && (
        <Field
          label="Legacy migration"
          description={migrationDescription(model.migration)}
          padding="standard"
          bottomSeparator="standard"
        />
      )}
      {migrationMessage && <Field description={migrationMessage} padding="standard" bottomSeparator="standard" />}

      <TrainerFilePicker
        disabled={configurationDisabled || !model.controls.browse}
        value={currentConfig.trainerPath}
        onBrowse={chooseTrainer}
      />

      <Field
        label="Prefix override (advanced)"
        description="Optional absolute Wine prefix directory. Leave empty to use UniFiDeck's prefix."
        padding="standard"
        childrenLayout="below"
        bottomSeparator="standard"
      >
        <TextField
          disabled={configurationDisabled || !currentConfig.trainerPath}
          value={prefixDraft}
          onChange={(event) => setPrefixDraft(event.currentTarget.value)}
        />
        <DialogButton
          disabled={
            configurationDisabled ||
            !currentConfig.trainerPath ||
            prefixDraft.trim() === (currentConfig.prefixOverride ?? "")
          }
          onClick={() => void savePrefix()}
        >
          Save prefix
        </DialogButton>
      </Field>
      <ToggleField
        label="Enabled"
        description="Browsing saves disabled. Verified launch preparation enables the trainer automatically."
        checked={currentConfig.enabled}
        disabled={configurationDisabled || !model.controls.enable}
        onChange={(enabled) => void toggleRelay(enabled)}
        bottomSeparator="standard"
        highlightOnFocus
      />
      {model.controls.retry && (
        <Field padding="standard" childrenLayout="below" bottomSeparator="standard">
          <DialogButton disabled={busy} onClick={() => void retry()}>
            <FaArrowsRotate /> Retry trainer
          </DialogButton>
        </Field>
      )}
    </Focusable>
  );
};

export default RelayPage;
