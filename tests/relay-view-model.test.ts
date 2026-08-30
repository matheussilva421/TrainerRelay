import { describe, expect, it } from "vitest";

import { buildTrainerRelayViewModel } from "../src/domain/relay/viewModel";

describe("Trainer Relay view model", () => {
  it("keeps loading fail-closed without configuration controls", () => {
    const model = buildTrainerRelayViewModel({ status: "loading" });

    expect(model).toEqual({ kind: "loading", heading: "Trainer Relay", message: "Reading shortcut details…" });
    expect("controls" in model).toBe(false);
  });

  it("shows only identity, explanation, and repository for unsupported shortcuts", () => {
    const model = buildTrainerRelayViewModel({
      status: "ready",
      snapshot: { command: "/usr/bin/other-launcher", launchOptions: "gog:game-1" },
    });

    expect(model).toEqual({
      kind: "unsupported",
      heading: "Trainer Relay",
      message: "This shortcut is not a recognised UniFiDeck Epic/GOG launch.",
      repositoryUrl: "https://github.com/matheussilva421/TrainerRelay",
    });
    expect("controls" in model).toBe(false);
  });

  it("exposes supported controls only for an exact classified identity and no legacy pair", () => {
    const model = buildTrainerRelayViewModel({
      status: "ready",
      snapshot: { command: "/usr/bin/unifideck-launcher", launchOptions: "%command% epic:game-1" },
    });

    expect(model.kind).toBe("supported");
    if (model.kind !== "supported") throw new Error("expected supported model");
    expect(model.identity).toBe("epic:game-1");
    expect(model.migration).toEqual({ status: "none" });
    expect(model.controls).toEqual({ browse: true, enable: false, retry: false });
  });

  it("keeps configuration available for a plain UniFiDeck GOG identity", () => {
    const model = buildTrainerRelayViewModel({
      status: "ready",
      snapshot: { command: "/usr/bin/unifideck-launcher", launchOptions: "gog:1482265568" },
    });

    expect(model.kind).toBe("supported");
    if (model.kind !== "supported") throw new Error("expected supported model");
    expect(model.identity).toBe("gog:1482265568");
    expect(model.migration).toEqual({ status: "none" });
    expect(model.controls).toEqual({ browse: true, enable: false, retry: false });
  });

  it("requires verified container preparation after a trainer is selected", () => {
    const model = buildTrainerRelayViewModel(
      {
        status: "ready",
        snapshot: { command: "/usr/bin/unifideck-launcher", launchOptions: "gog:1482265568" },
      },
      { enabled: false, trainerPath: "/home/deck/Trainers/Game.exe" },
    );

    expect(model.kind).toBe("supported");
    if (model.kind !== "supported") throw new Error("expected supported model");
    expect(model.migration).toEqual({
      status: "ready",
      trainerPath: "/home/deck/Trainers/Game.exe",
      launchOptions: "UMU_CONTAINER_NSENTER=1 %command% gog:1482265568",
      changes: "container",
    });
    expect(model.controls.enable).toBe(false);
  });

  it("blocks configuration when a legacy pair is present and renders the safe status code", () => {
    const model = buildTrainerRelayViewModel(
      {
        status: "ready",
        snapshot: {
          command: "/usr/bin/unifideck-launcher",
          launchOptions:
            "PROTON_REMOTE_DEBUG_CMD=/home/deck/trainer.exe PRESSURE_VESSEL_FILESYSTEMS_RW=/tmp %command% gog:game-1",
        },
      },
      undefined,
      { identity: "gog:game-1", state: "ambiguous", diagnostic: { code: "unsafe raw detail" } },
    );

    expect(model.kind).toBe("supported");
    if (model.kind !== "supported") throw new Error("expected supported model");
    expect(model.migration.status).toBe("ready");
    expect(model.controls).toEqual({ browse: true, enable: false, retry: false });
    expect(model.status).toEqual({ state: "ambiguous", diagnosticCode: "status_unavailable" });
  });

  it("keeps manual browsing available while incomplete legacy options block enablement", () => {
    const model = buildTrainerRelayViewModel({
      status: "ready",
      snapshot: {
        command: "/usr/bin/unifideck-launcher",
        launchOptions: "PROTON_REMOTE_DEBUG_CMD=/home/deck/trainer.exe %command% gog:game-1",
      },
    });

    expect(model.kind).toBe("supported");
    if (model.kind !== "supported") throw new Error("expected supported model");
    expect(model.migration).toEqual({ status: "blocked" });
    expect(model.controls).toEqual({ browse: true, enable: false, retry: false });
  });

  it("allows an already-enabled relay to be disabled when legacy options reappear", () => {
    const model = buildTrainerRelayViewModel(
      {
        status: "ready",
        snapshot: {
          command: "/usr/bin/unifideck-launcher",
          launchOptions: "PROTON_REMOTE_DEBUG_CMD=/home/deck/trainer.exe %command% gog:game-1",
        },
      },
      { enabled: true, trainerPath: "/home/deck/trainer.exe" },
    );

    expect(model.kind).toBe("supported");
    if (model.kind !== "supported") throw new Error("expected supported model");
    expect(model.controls.enable).toBe(true);
  });

  it("does not carry a previous game's status into a newly classified identity", () => {
    const model = buildTrainerRelayViewModel(
      {
        status: "ready",
        snapshot: { command: "/usr/bin/unifideck-launcher", launchOptions: "%command% epic:game-2" },
      },
      undefined,
      { identity: "epic:game-1", state: "failed", diagnostic: { code: "trainer_failed" } },
    );

    expect(model.kind).toBe("supported");
    if (model.kind !== "supported") throw new Error("expected supported model");
    expect(model.status).toEqual({ state: "disabled", diagnosticCode: null });
  });
});
