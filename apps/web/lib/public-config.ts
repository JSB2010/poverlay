type PublicWebConfig = {
  siteUrl: string;
  apiBase: string;
  firebaseAuthEnabled: boolean;
  firebase: {
    apiKey: string;
    authDomain: string;
    projectId: string;
    appId: string;
    messagingSenderId: string;
    storageBucket: string;
  } | null;
};

const BOOL_TRUE = new Set(["1", "true", "yes", "on"]);
const BOOL_FALSE = new Set(["0", "false", "no", "off"]);

function parseBool(name: string, fallback: boolean): boolean {
  const raw = process.env[name];
  if (raw === undefined) {
    return fallback;
  }
  const normalized = raw.trim().toLowerCase();
  if (BOOL_TRUE.has(normalized)) {
    return true;
  }
  if (BOOL_FALSE.has(normalized)) {
    return false;
  }
  throw new Error(`[config] Invalid boolean for ${name}: ${JSON.stringify(raw)}.`);
}

function trimmed(name: string): string {
  return (process.env[name] ?? "").trim();
}

function requiredWhenEnabled(name: string, value: string, errors: string[]): void {
  if (!value) {
    errors.push(`${name} is required when NEXT_PUBLIC_FIREBASE_AUTH_ENABLED=true.`);
  }
}

function loadPublicWebConfig(): PublicWebConfig {
  const firebaseAuthEnabled = parseBool("NEXT_PUBLIC_FIREBASE_AUTH_ENABLED", false);
  const siteUrl = trimmed("NEXT_PUBLIC_SITE_URL") || "https://poverlay.com";
  const apiBase = trimmed("NEXT_PUBLIC_API_BASE").replace(/\/+$/, "");

  const firebaseApiKey = trimmed("NEXT_PUBLIC_FIREBASE_API_KEY");
  const firebaseAuthDomain = trimmed("NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN");
  const firebaseProjectId = trimmed("NEXT_PUBLIC_FIREBASE_PROJECT_ID");
  const firebaseAppId = trimmed("NEXT_PUBLIC_FIREBASE_APP_ID");
  const firebaseMessagingSenderId = trimmed("NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID");
  const firebaseStorageBucket = trimmed("NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET");

  const errors: string[] = [];
  if (firebaseAuthEnabled) {
    requiredWhenEnabled("NEXT_PUBLIC_FIREBASE_API_KEY", firebaseApiKey, errors);
    requiredWhenEnabled("NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN", firebaseAuthDomain, errors);
    requiredWhenEnabled("NEXT_PUBLIC_FIREBASE_PROJECT_ID", firebaseProjectId, errors);
    requiredWhenEnabled("NEXT_PUBLIC_FIREBASE_APP_ID", firebaseAppId, errors);
    requiredWhenEnabled("NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID", firebaseMessagingSenderId, errors);
    requiredWhenEnabled("NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET", firebaseStorageBucket, errors);
  }

  if (errors.length > 0) {
    throw new Error(
      `[config] Invalid web environment configuration:\n${errors.map((entry) => `- ${entry}`).join("\n")}\n` +
        "Copy root .env.example to .env and set required values."
    );
  }

  return {
    siteUrl,
    apiBase,
    firebaseAuthEnabled,
    firebase: firebaseAuthEnabled
      ? {
          apiKey: firebaseApiKey,
          authDomain: firebaseAuthDomain,
          projectId: firebaseProjectId,
          appId: firebaseAppId,
          messagingSenderId: firebaseMessagingSenderId,
          storageBucket: firebaseStorageBucket,
        }
      : null,
  };
}

export const PUBLIC_WEB_CONFIG = loadPublicWebConfig();
