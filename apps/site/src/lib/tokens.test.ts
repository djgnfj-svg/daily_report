import { describe, it, expect } from "vitest";
import { generateToken, isValidTokenFormat } from "./tokens";

describe("tokens", () => {
  it("generates 64-character hex token", () => {
    const t = generateToken();
    expect(t).toMatch(/^[a-f0-9]{64}$/);
  });

  it("two tokens differ", () => {
    expect(generateToken()).not.toEqual(generateToken());
  });

  it("validates format", () => {
    expect(isValidTokenFormat("a".repeat(64))).toBe(true);
    expect(isValidTokenFormat("zzz")).toBe(false);
    expect(isValidTokenFormat("A".repeat(64))).toBe(false);
  });
});
