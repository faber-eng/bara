import type { Auth, User } from "firebase/auth";

const CONFIG_KEYS = [
  "VITE_FIREBASE_API_KEY",
  "VITE_FIREBASE_AUTH_DOMAIN",
  "VITE_FIREBASE_PROJECT_ID",
  "VITE_FIREBASE_APP_ID",
] as const;

export class FirebaseConfigError extends Error {
  override name = "FirebaseConfigError";
}

type ConfigKey = (typeof CONFIG_KEYS)[number];

function readConfigValue(key: ConfigKey): string {
  const value: unknown = import.meta.env[key];
  return typeof value === "string" ? value : "";
}

function readFirebaseConfig() {
  const missing = CONFIG_KEYS.filter((key) => readConfigValue(key) === "");
  if (missing.length > 0) {
    throw new FirebaseConfigError(`Firebase web config is missing: ${missing.join(", ")}`);
  }
  return {
    apiKey: readConfigValue("VITE_FIREBASE_API_KEY"),
    authDomain: readConfigValue("VITE_FIREBASE_AUTH_DOMAIN"),
    projectId: readConfigValue("VITE_FIREBASE_PROJECT_ID"),
    appId: readConfigValue("VITE_FIREBASE_APP_ID"),
  };
}

let signedIn: Promise<Auth> | null = null;

async function signIn(): Promise<Auth> {
  const config = readFirebaseConfig();
  const [{ initializeApp }, { getAuth, signInAnonymously }] = await Promise.all([
    import("firebase/app"),
    import("firebase/auth"),
  ]);
  const auth = getAuth(initializeApp(config));
  await auth.authStateReady();
  if (auth.currentUser === null) await signInAnonymously(auth);
  return auth;
}

function ensureSignedIn(): Promise<Auth> {
  if (signedIn === null) {
    signedIn = signIn().catch((error: unknown) => {
      signedIn = null;
      throw error;
    });
  }
  return signedIn;
}

export async function getIdToken(): Promise<string> {
  const auth = await ensureSignedIn();
  if (auth.currentUser === null) throw new Error("Firebase has no signed-in user");
  return auth.currentUser.getIdToken();
}

export type AuthUser = { uid: string; isAnonymous: boolean; displayName: string | null };

function toAuthUser(user: User | null): AuthUser | null {
  if (user === null) return null;
  return { uid: user.uid, isAnonymous: user.isAnonymous, displayName: user.displayName };
}

export async function signInWithGoogle(): Promise<AuthUser> {
  const auth = await ensureSignedIn();
  const { GoogleAuthProvider, signInWithPopup } = await import("firebase/auth");
  const result = await signInWithPopup(auth, new GoogleAuthProvider());
  const user = toAuthUser(result.user);
  if (user === null) throw new Error("Google sign-in returned no user");
  return user;
}

export async function refreshIdToken(): Promise<string> {
  const auth = await ensureSignedIn();
  if (auth.currentUser === null) throw new Error("Firebase has no signed-in user");
  return auth.currentUser.getIdToken(true);
}

export function subscribeAuthUser(
  onUser: (user: AuthUser | null) => void,
  onFailure: (error: Error) => void,
): () => void {
  let cancelled = false;
  let unsubscribe = () => {};
  async function start() {
    const auth = await ensureSignedIn();
    const { onAuthStateChanged } = await import("firebase/auth");
    if (cancelled) return;
    unsubscribe = onAuthStateChanged(auth, (user) => onUser(toAuthUser(user)));
  }
  start().catch((error: unknown) => {
    if (!cancelled) onFailure(error instanceof Error ? error : new Error("Sign-in failed"));
  });
  return () => {
    cancelled = true;
    unsubscribe();
  };
}
