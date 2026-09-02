import { describe, expect, it, vi } from "vitest";

import type { SteamInputMethodShape } from "../src/domain/steamInput/types";
import { createSteamInputLayoutAdapter } from "../src/infra/steamInput/adapter";
import { fingerprintSteamInputShape } from "../src/infra/steamInput/runtimeFingerprint";

const appId = 123456789;
const recognizedResponse = {
  controller_type: "neptune",
  url: "autosave://123/source",
  name: "Source Layout",
};

const forbiddenMethods = [
  "ExportCurrentControllerConfiguration",
  "StartEditingControllerConfigurationForAppIDAndControllerIndex",
  "StopEditingControllerConfiguration",
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
      expect(result.observation).toEqual({
        methodShape: {
          getConfig: true,
          exportConfig: true,
          startEditing: true,
          saveEditing: true,
          setSelected: true,
          showConfigurator: true,
        },
        responsePrimitiveKeys: ["controller_type", "url", "name"],
      });
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

  it.each([
    ["invalid primitive key", { ...recognizedResponse, "account id": "76561198000000000" }],
    ["unbounded primitive key", { ...recognizedResponse, ["x".repeat(129)]: "secret-token" }],
  ])("fails closed instead of omitting an %s", async (_name, response) => {
    const dependencies = createDependencies(response);
    const adapter = createSteamInputLayoutAdapter(dependencies);

    await expect(adapter.probe(appId)).resolves.toEqual({
      status: "unavailable",
      diagnostic: "unknown_response_shape",
    });
    expect(dependencies.calls).toEqual(["GetConfigForAppAndController"]);
  });

  it("fingerprints bounded private structure without including account or token values", async () => {
    const accountIdentifier = "76561198000000000";
    const privateToken = "private-token-value";
    const dependencies = createDependencies({
      ...recognizedResponse,
      account_id: accountIdentifier,
      access_token: privateToken,
    });
    const adapter = createSteamInputLayoutAdapter(dependencies);

    await expect(adapter.probe(appId)).resolves.toMatchObject({ status: "readonly" });

    const fingerprintInput = new TextDecoder().decode(dependencies.digest.mock.calls[0][0]);
    const shape = JSON.parse(fingerprintInput) as {
      responsePrimitiveKeys: string[];
      responsePrimitiveTypes: Record<string, string>;
    };
    expect(fingerprintInput).not.toContain(accountIdentifier);
    expect(fingerprintInput).not.toContain(privateToken);
    expect(shape.responsePrimitiveKeys).toEqual(["access_token", "account_id", "controller_type", "name", "url"]);
    expect(shape.responsePrimitiveTypes).toEqual({
      access_token: "string",
      account_id: "string",
      controller_type: "string",
      name: "string",
      url: "string",
    });
    expect(shape.responsePrimitiveKeys.every((key) => key.length <= 128 && /^[A-Za-z0-9_.-]+$/.test(key))).toBe(true);
  });

  it("rejects a runtime shape missing a primitive type for any response key", async () => {
    const shape = {
      getConfig: true,
      exportConfig: false,
      startEditing: false,
      saveEditing: false,
      stopEditing: false,
      setActionSet: false,
      setActivator: false,
      setBinding: false,
      setSourceMode: false,
      setSelected: false,
      showConfigurator: true,
      responsePrimitiveKeys: ["controller_type", "url"],
      responsePrimitiveTypes: { controller_type: "string" },
      controllerClassification: "steam_deck_builtin",
    } satisfies SteamInputMethodShape;
    const digest = vi.fn(async (_value: Uint8Array) => new Uint8Array(32));

    await expect(fingerprintSteamInputShape(shape, digest)).rejects.toMatchObject({ code: "invalid_runtime_shape" });
    expect(digest).not.toHaveBeenCalled();
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

  it("keeps every shipped adapter flow free of write and registration calls", async () => {
    const dependencies = createDependencies();
    const adapter = createSteamInputLayoutAdapter(dependencies);

    await adapter.probe(appId);
    await adapter.inspectSelectedLayout(appId);
    await adapter.createSeparateLayout({
      source: {
        appId,
        controllerIndex: 0,
        controller: "steam_deck_builtin",
        sourceLayoutId: recognizedResponse.url,
        sourceLayoutName: recognizedResponse.name,
        runtimeFingerprint: "a".repeat(64),
      },
      plan: {} as never,
      generatedLayoutName: "Trainer Relay - test",
    });
    await adapter.openConfigurator(appId);

    expect(dependencies.calls).toEqual([
      "GetConfigForAppAndController",
      "GetConfigForAppAndController",
      "ShowControllerConfigurator",
    ]);
    for (const method of forbiddenMethods) expect(dependencies.input[method]).not.toHaveBeenCalled();
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
