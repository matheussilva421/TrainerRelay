import { describe, expect, it, vi } from "vitest";

import { createSteamInputLayoutAdapter } from "../src/infra/steamInput/adapter";

const appId = 123456789;
const recognizedResponse = {
  controller_type: "neptune",
  url: "autosave://123/source",
  name: "Source Layout",
};

const forbiddenMethods = [
  "ExportCurrentControllerConfiguration",
  "StartEditingControllerConfigurationForAppIDAndControllerIndex",
  "SetEditingControllerConfigurationActionSet",
  "SetEditingControllerConfigurationInputActivator",
  "SetEditingControllerConfigurationInputBinding",
  "SetEditingControllerConfigurationSourceMode",
  "SaveEditingControllerConfiguration",
  "SetSelectedConfigForApp",
  "RegisterForControllerConfigInfoMessages",
] as const;

const createDependencies = (response: unknown = recognizedResponse) => {
  const calls: string[] = [];
  const input: Record<string, unknown> = {
    GetConfigForAppAndController: vi.fn(() => {
      calls.push("GetConfigForAppAndController");
      return response;
    }),
  };
  for (const method of forbiddenMethods) {
    input[method] = vi.fn(() => calls.push(method));
  }
  const app = {
    ShowControllerConfigurator: vi.fn(() => {
      calls.push("ShowControllerConfigurator");
    }),
  };
  const digest = vi.fn(async (_value: Uint8Array) => new Uint8Array(32).fill(0xab));
  return { calls, input, app, digest };
};

describe("read-only Steam Input adapter", () => {
  it("probes Neptune with exactly one read and never invokes mutation or registration methods", async () => {
    const dependencies = createDependencies();
    const adapter = createSteamInputLayoutAdapter(dependencies);

    const result = await adapter.probe(appId);

    expect(result.status).toBe("readonly");
    if (result.status === "readonly") {
      expect(result.snapshot).toMatchObject({
        appId,
        controllerIndex: 0,
        controller: "steam_deck_builtin",
        sourceLayoutId: recognizedResponse.url,
        sourceLayoutName: recognizedResponse.name,
      });
      expect(result.snapshot.runtimeFingerprint).toHaveLength(64);
    }
    expect(dependencies.input.GetConfigForAppAndController).toHaveBeenCalledWith(appId, 0);
    expect(dependencies.calls).toEqual(["GetConfigForAppAndController"]);
    const fingerprintInput = new TextDecoder().decode(dependencies.digest.mock.calls[0][0]);
    expect(fingerprintInput).toContain('"controller":"steam_deck_builtin"');
    expect(fingerprintInput).toContain('"controller_type"');
    expect(fingerprintInput).toContain('"string"');
    expect(fingerprintInput).not.toContain(recognizedResponse.url);
    expect(fingerprintInput).not.toContain(recognizedResponse.name);
    for (const method of forbiddenMethods) expect(dependencies.input[method]).not.toHaveBeenCalled();
  });

  it.each([
    ["missing read method", undefined, "steam_input_method_unavailable"],
    ["non-Neptune response", { ...recognizedResponse, controller_type: "xbox" }, "unsupported_controller"],
    ["unknown response shape", { private_value: { accountId: "secret" } }, "unknown_response_shape"],
  ])("fails closed for %s", async (_name, response, diagnostic) => {
    const dependencies = createDependencies(response);
    if (_name === "missing read method") delete dependencies.input.GetConfigForAppAndController;
    const adapter = createSteamInputLayoutAdapter(dependencies);

    await expect(adapter.probe(appId)).resolves.toMatchObject({ status: "unavailable", diagnostic });
    expect(dependencies.calls.filter((call) => call !== "GetConfigForAppAndController")).toEqual([]);
  });

  it("maps thrown and rejected reads to bounded unavailable results", async () => {
    const dependencies = createDependencies();
    dependencies.input.GetConfigForAppAndController = vi.fn().mockRejectedValue(new Error("private payload"));
    const adapter = createSteamInputLayoutAdapter(dependencies);

    await expect(adapter.probe(appId)).resolves.toMatchObject({ status: "unavailable", diagnostic: "read_failed" });
    await expect(adapter.inspectSelectedLayout(appId)).rejects.toMatchObject({ code: "read_failed" });
  });

  it("does not attempt separate-layout creation before a writable runtime profile exists", async () => {
    const dependencies = createDependencies();
    const adapter = createSteamInputLayoutAdapter(dependencies);
    const request = {
      source: {
        appId,
        controllerIndex: 0 as const,
        controller: "steam_deck_builtin" as const,
        sourceLayoutId: recognizedResponse.url,
        sourceLayoutName: recognizedResponse.name,
        runtimeFingerprint: "a".repeat(64),
      },
      plan: {} as never,
      generatedLayoutName: "Trainer Relay - test",
    };

    await expect(adapter.createSeparateLayout(request)).resolves.toEqual({
      status: "unsupported_runtime",
      diagnostic: "steam_input_runtime_not_validated",
    });
    expect(dependencies.calls).toEqual([]);
  });

  it("opens only the normal configurator after positive safe AppID validation", async () => {
    const dependencies = createDependencies();
    const adapter = createSteamInputLayoutAdapter(dependencies);

    await adapter.openConfigurator(appId);

    expect(dependencies.app.ShowControllerConfigurator).toHaveBeenCalledWith(appId);
    await expect(adapter.openConfigurator(0)).rejects.toMatchObject({ code: "invalid_app_id" });
    await expect(adapter.openConfigurator(Number.MAX_SAFE_INTEGER + 1)).rejects.toMatchObject({
      code: "invalid_app_id",
    });
    expect(dependencies.app.ShowControllerConfigurator).toHaveBeenCalledTimes(1);
  });
});
