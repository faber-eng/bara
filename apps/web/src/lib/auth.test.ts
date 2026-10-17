import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const signInAnonymously = vi.fn();
const getIdTokenFn = vi.fn();
const fakeAuth: {
  currentUser: { getIdToken: typeof getIdTokenFn } | null;
  authStateReady: () => Promise<void>;
} = {
  currentUser: null,
  authStateReady: () => Promise.resolve(),
};

vi.mock("firebase/app", () => ({ initializeApp: vi.fn().mockReturnValue({}) }));
vi.mock("firebase/auth", () => ({
  getAuth: () => fakeAuth,
  signInAnonymously: (...args: unknown[]) => signInAnonymously(...args),
}));

function stubFirebaseEnv() {
  vi.stubEnv("VITE_FIREBASE_API_KEY", "k");
  vi.stubEnv("VITE_FIREBASE_AUTH_DOMAIN", "d.firebaseapp.com");
  vi.stubEnv("VITE_FIREBASE_PROJECT_ID", "p");
  vi.stubEnv("VITE_FIREBASE_APP_ID", "a");
}

describe("getIdToken", () => {
  beforeEach(() => {
    vi.resetModules();
    fakeAuth.currentUser = null;
    getIdTokenFn.mockResolvedValue("anon-token");
    signInAnonymously.mockImplementation(() => {
      fakeAuth.currentUser = { getIdToken: getIdTokenFn };
      return Promise.resolve();
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.clearAllMocks();
  });

  it("throws FirebaseConfigError naming the missing keys", async () => {
    vi.stubEnv("VITE_FIREBASE_API_KEY", "");
    vi.stubEnv("VITE_FIREBASE_AUTH_DOMAIN", "");
    vi.stubEnv("VITE_FIREBASE_PROJECT_ID", "");
    vi.stubEnv("VITE_FIREBASE_APP_ID", "");
    const { getIdToken, FirebaseConfigError } = await import("./auth");

    const failure = await getIdToken().catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(FirebaseConfigError);
    expect((failure as Error).message).toContain("VITE_FIREBASE_API_KEY");
  });

  it("signs in anonymously once for concurrent callers", async () => {
    stubFirebaseEnv();
    const { getIdToken } = await import("./auth");

    const tokens = await Promise.all([getIdToken(), getIdToken(), getIdToken()]);

    expect(tokens).toEqual(["anon-token", "anon-token", "anon-token"]);
    expect(signInAnonymously).toHaveBeenCalledTimes(1);
  });

  it("keeps a user restored from persistence and skips anonymous sign-in", async () => {
    stubFirebaseEnv();
    fakeAuth.currentUser = { getIdToken: getIdTokenFn };
    getIdTokenFn.mockResolvedValue("google-token");
    const { getIdToken } = await import("./auth");

    expect(await getIdToken()).toBe("google-token");
    expect(signInAnonymously).not.toHaveBeenCalled();
  });

  it("tries again after a failed sign-in", async () => {
    stubFirebaseEnv();
    signInAnonymously.mockRejectedValueOnce(new Error("offline"));
    const { getIdToken } = await import("./auth");

    await expect(getIdToken()).rejects.toThrow("offline");

    expect(await getIdToken()).toBe("anon-token");
  });
});
