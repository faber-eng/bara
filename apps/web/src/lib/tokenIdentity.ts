import { readRecord, readString } from "./api/parse";

export type TokenIdentity = { uid: string; provider: string | null };

function decodeSegment(segment: string): unknown {
  const padded = segment.replace(/-/g, "+").replace(/_/g, "/");
  return JSON.parse(atob(padded));
}

function readProvider(payload: Record<string, unknown>): string | null {
  const firebase = payload.firebase;
  if (typeof firebase !== "object" || firebase === null) return null;
  const provider = (firebase as Record<string, unknown>).sign_in_provider;
  return typeof provider === "string" ? provider : null;
}

export function readTokenIdentity(token: string): TokenIdentity | null {
  const segment = token.split(".")[1];
  if (segment === undefined) return null;
  try {
    const payload = readRecord(decodeSegment(segment), "token");
    return { uid: readString(payload, "sub", "token"), provider: readProvider(payload) };
  } catch {
    return null;
  }
}

export function isRealUser(identity: TokenIdentity | null): identity is TokenIdentity {
  return identity !== null && identity.provider !== null && identity.provider !== "anonymous";
}
