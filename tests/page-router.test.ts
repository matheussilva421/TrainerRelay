import { describe, expect, it, vi } from "vitest";

vi.hoisted(() => {
  vi.stubGlobal("window", {
    SP_REACT: {
      createElement: (type: unknown, props: Record<string, unknown> | null, ...children: unknown[]) => ({
        type,
        props: {
          ...props,
          children: children.length === 0 ? undefined : children.length === 1 ? children[0] : children,
        },
      }),
      Fragment: "Fragment",
    },
  });
});

vi.mock("@decky/ui", () => ({
  SidebarNavigation: "SidebarNavigation",
  useParams: () => ({ appid: "482265568" }),
}));

vi.mock("../src/views/RelayPage", () => ({
  default: "RelayPage",
}));

vi.mock("react-icons/fa6", () => ({
  FaWrench: "FaWrench",
}));

import PageRouter from "../src/views/PageRouter";

interface ElementNode {
  type?: unknown;
  props?: { [key: string]: any };
}

describe("Trainer Relay routed UI", () => {
  it("uses CheatDeck's SidebarNavigation focus host with one explicit page", () => {
    const view = PageRouter({}) as ElementNode;
    const pages = view?.props?.pages;

    expect(view?.type).toBe("SidebarNavigation");
    expect(view?.props?.title).toBe("Trainer Relay");
    expect(view?.props?.showTitle).toBe(true);
    expect(pages).toHaveLength(1);
    expect(pages?.[0]).toMatchObject({ title: "Trainer Relay", hideTitle: false });
    expect(pages?.[0]?.content).toMatchObject({ type: "RelayPage", props: { appid: 482_265_568 } });
  });
});
