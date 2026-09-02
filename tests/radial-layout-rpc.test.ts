import { beforeEach, describe, expect, it, vi } from "vitest";

const deckyMock = vi.hoisted(() => {
  type Handler = (...args: unknown[]) => unknown;
  const handlers = new Map<string, Handler>();
  const registrations: string[] = [];
  const invocations: Array<{ name: string; args: unknown[] }> = [];
  const callable = vi.fn((name: string) => {
    registrations.push(name);
    return (...args: unknown[]) => {
      invocations.push({ name, args });
      const handler = handlers.get(name);
      return handler === undefined ? Promise.resolve(undefined) : handler(...args);
    };
  });
  return { callable, handlers, registrations, invocations };
});

vi.mock("@decky/api", () => ({ callable: deckyMock.callable }));

import { createRadialLayoutRpc, RadialLayoutRpcError, radialLayoutRpc } from "../src/infra/radialLayoutRpc";

const record = {
  appId: 123456789,
  identity: "gog:1482265668" as const,
  trainerSha256: "a".repeat(64),
  catalogFingerprint: "b".repeat(64),
  steamRuntimeFingerprint: "c".repeat(64),
  sourceLayoutId: "autosave://123/source",
  generatedLayoutId: "personal://123/generated",
  generatedLayoutName: "Trainer Relay - BioShock 2 - aaaaaaaa - r1",
  revision: 1,
  createdAt: "2026-09-02T12:00:00Z",
};

const registry = { schemaVersion: 1 as const, layouts: [record] };

describe("radial layout RPC", () => {
  beforeEach(() => {
    deckyMock.handlers.clear();
    deckyMock.invocations.length = 0;
  });

  it("registers and exercises the exact exported Decky callable names", async () => {
    deckyMock.handlers.set("get_radial_layout_registry", () => Promise.resolve(registry));
    deckyMock.handlers.set("record_generated_radial_layout", () => Promise.resolve(registry));

    await expect(radialLayoutRpc.getRegistry()).resolves.toEqual(registry);
    await expect(radialLayoutRpc.record(record)).resolves.toEqual(registry);

    expect(deckyMock.registrations).toEqual([
      "get_radial_layout_registry",
      "record_generated_radial_layout",
      "export_steam_input_probe",
    ]);
    expect(deckyMock.invocations).toEqual([
      { name: "get_radial_layout_registry", args: [] },
      { name: "record_generated_radial_layout", args: [record] },
    ]);
  });

  it.each(["get", "record"] as const)("maps exported %s transport failures to one bounded code", async (operation) => {
    deckyMock.handlers.set("get_radial_layout_registry", () =>
      Promise.reject(new RadialLayoutRpcError("account_token_from_transport")),
    );
    deckyMock.handlers.set("record_generated_radial_layout", () =>
      Promise.reject({ code: "private_backend_path", detail: "C:\\private\\account" }),
    );

    const result = operation === "get" ? radialLayoutRpc.getRegistry() : radialLayoutRpc.record(record);

    await expect(result).rejects.toEqual(expect.objectContaining({ code: "radial_layout_rpc_failed" }));
    await expect(result).rejects.not.toThrow("account_token_from_transport");
    await expect(result).rejects.not.toThrow("private_backend_path");
  });

  it("uses the exact Task 2 registry wire requests and decodes responses", async () => {
    const transport = {
      getRegistry: vi.fn().mockResolvedValue(registry),
      record: vi.fn().mockResolvedValue(registry),
      exportProbe: vi.fn(),
    };
    const rpc = createRadialLayoutRpc(transport);

    await expect(rpc.getRegistry()).resolves.toEqual(registry);
    await expect(rpc.record(record)).resolves.toEqual(registry);

    expect(transport.getRegistry).toHaveBeenCalledWith();
    expect(transport.record).toHaveBeenCalledWith(record);
  });

  it("rejects malformed responses before they reach callers", async () => {
    const transport = {
      getRegistry: vi.fn().mockResolvedValue({ schemaVersion: 1, layouts: [{ ...record, leaked: "private" }] }),
      record: vi.fn(),
      exportProbe: vi.fn(),
    };
    const rpc = createRadialLayoutRpc(transport);

    await expect(rpc.getRegistry()).rejects.toMatchObject({ code: "invalid_radial_layout_registry" });
  });

  it("maps transport failures to a bounded RadialLayoutRpcError", async () => {
    const transport = {
      getRegistry: vi.fn().mockRejectedValue(new RadialLayoutRpcError("private_transport_code")),
      record: vi.fn(),
      exportProbe: vi.fn(),
    };
    const rpc = createRadialLayoutRpc(transport);

    await expect(rpc.getRegistry()).rejects.toMatchObject({ code: "radial_layout_rpc_failed" });
    await expect(rpc.getRegistry()).rejects.not.toThrow("account-token");
    expect(new RadialLayoutRpcError("invalid_radial_layout_registry")).toBeInstanceOf(Error);
  });

  it("fails closed before transport for an unsafe record", async () => {
    const transport = {
      getRegistry: vi.fn(),
      record: vi.fn(),
      exportProbe: vi.fn(),
    };
    const rpc = createRadialLayoutRpc(transport);

    await expect(rpc.record({ ...record, appId: 0 })).rejects.toMatchObject({ code: "invalid_radial_app_id" });
    expect(transport.record).not.toHaveBeenCalled();
  });
});
