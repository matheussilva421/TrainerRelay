import { describe, expect, it } from "vitest";

import { LaunchOptions } from "../src/domain/options";
import { classifyShortcut } from "../src/domain/relay/shortcut";

describe("classifyShortcut", () => {
  it("classifies a plain supported store token", () => {
    expect(classifyShortcut("/home/deck/.local/bin/unifideck-launcher", "gog:the-witcher-3")).toBe("gog:the-witcher-3");
  });

  it("classifies a marker form with static assignments and unrelated literal arguments", () => {
    const source = `KEEP='a value' OTHER=literal %command% --profile 'Deck Profile' epic:game-42`;

    expect(classifyShortcut("C:\\Games\\UNIFIDECK-LAUNCHER", source)).toBe("epic:game-42");
    expect(classifyShortcut("C:\\Games\\UNIFIDECK-LAUNCHER", LaunchOptions.parse(source))).toBe("epic:game-42");
  });

  it.each([
    ["unsupported store", "steam:123", "/usr/bin/unifideck-launcher"],
    ["empty id", "epic:", "/usr/bin/unifideck-launcher"],
    ["identity with nested colon", "epic:one:two", "/usr/bin/unifideck-launcher"],
    ["multiple supported identities", "%command% epic:one gog:two", "/usr/bin/unifideck-launcher"],
    ["dynamic identity", "%command% epic:$GAME", "/usr/bin/unifideck-launcher"],
    ["dynamic assignment", "STORE=$GAME %command% epic:one", "/usr/bin/unifideck-launcher"],
    ["malformed quote", "%command% 'epic:one", "/usr/bin/unifideck-launcher"],
    ["dynamic shell syntax", "%command% epic:one && echo unsafe", "/usr/bin/unifideck-launcher"],
    ["lookalike basename", "%command% epic:one", "/usr/bin/unifideck-launcher-extra"],
    ["executable suffix", "%command% epic:one", "/usr/bin/unifideck-launcher.exe"],
    ["missing command", "epic:one", "/usr/bin/other-launcher"],
  ])("rejects %s", (_name, launchOptions, command) => {
    expect(classifyShortcut(command, launchOptions)).toBeUndefined();
  });

  it("requires the exact command basename after normalising separators and case", () => {
    expect(classifyShortcut("/opt/UNIFIDECK-LAUNCHER", "gog:one")).toBe("gog:one");
    expect(classifyShortcut("/opt/unifideck-launcher/child", "gog:one")).toBeUndefined();
    expect(classifyShortcut("unifideck-launcher ", "gog:one")).toBeUndefined();
  });
});
