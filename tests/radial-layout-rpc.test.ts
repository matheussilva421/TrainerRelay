import { describe, expect, it, vi } from "vitest";

vi.mock("@decky/api", () => ({ callable: () => async () => undefined }));

import { createRadialLayoutRpc, RadialLayoutRpcError } from "../src/infra/radialLayoutRpc";

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
  it("uses the exact Task 2 registry wire requests and decodes responses", async () => {
    const transport = {
      getRegistry: vi.fn().mockResolvedValue(registry),
      record: vi.fn().mockResolvedValue(registry),
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
    };
    const rpc = createRadialLayoutRpc(transport);

    await expect(rpc.getRegistry()).rejects.toMatchObject({ code: "invalid_radial_layout_registry" });
  });

  it("maps transport failures to a bounded RadialLayoutRpcError", async () => {
    const transport = {
      getRegistry: vi.fn().mockRejectedValue(new Error("/private/path account-token")),
      record: vi.fn(),
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
    };
    const rpc = createRadialLayoutRpc(transport);

    await expect(rpc.record({ ...record, appId: 0 })).rejects.toMatchObject({ code: "invalid_radial_app_id" });
    expect(transport.record).not.toHaveBeenCalled();
  });
});
