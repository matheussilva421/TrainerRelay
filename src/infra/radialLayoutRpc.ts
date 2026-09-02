import { callable } from "@decky/api";
import {
  decodeGeneratedRadialLayout,
  decodeRadialLayoutRegistry,
  SteamInputDecodeError,
} from "../domain/steamInput/decoder";
import type { GeneratedRadialLayoutV1, RadialLayoutRegistryV1 } from "../domain/steamInput/types";

export interface RadialLayoutRpcTransport {
  getRegistry: () => Promise<unknown>;
  record: (record: GeneratedRadialLayoutV1) => Promise<unknown>;
}

export interface RadialLayoutRpcClient {
  getRegistry: () => Promise<RadialLayoutRegistryV1>;
  record: (record: GeneratedRadialLayoutV1) => Promise<RadialLayoutRegistryV1>;
}

export class RadialLayoutRpcError extends Error {
  constructor(readonly code: string) {
    super(code);
    this.name = "RadialLayoutRpcError";
  }
}

const guarded = async <T>(operation: () => Promise<T>): Promise<T> => {
  try {
    return await operation();
  } catch (error) {
    if (error instanceof RadialLayoutRpcError) throw error;
    if (error instanceof SteamInputDecodeError) throw new RadialLayoutRpcError(error.code);
    throw new RadialLayoutRpcError("radial_layout_rpc_failed");
  }
};

export const createRadialLayoutRpc = (transport: RadialLayoutRpcTransport): RadialLayoutRpcClient => ({
  getRegistry: () => guarded(async () => decodeRadialLayoutRegistry(await transport.getRegistry())),
  record: (record) =>
    guarded(async () => {
      let decoded: GeneratedRadialLayoutV1;
      try {
        decoded = decodeGeneratedRadialLayout(record);
      } catch (error) {
        if (error instanceof SteamInputDecodeError) throw error;
        throw new SteamInputDecodeError("invalid_radial_layout");
      }
      return decodeRadialLayoutRegistry(await transport.record(decoded));
    }),
});

const getRegistryCall = callable<[], unknown>("get_radial_layout_registry");
const recordCall = callable<[GeneratedRadialLayoutV1], unknown>("record_generated_radial_layout");

export const radialLayoutRpc = createRadialLayoutRpc({
  getRegistry: () => getRegistryCall(),
  record: (record) => recordCall(record),
});
