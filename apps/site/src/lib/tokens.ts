import { randomBytes } from "node:crypto";

export function generateToken(): string {
  return randomBytes(32).toString("hex");
}

export function isValidTokenFormat(t: string): boolean {
  return /^[a-f0-9]{64}$/.test(t);
}
