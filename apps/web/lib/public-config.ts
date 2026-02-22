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

// Next.js only inlines client env vars for static property access.
const PUBLIC_ENV = {
  NEXT_PUBLIC_SITE_URL: process.env.NEXT_PUBLIC_SITE_URL,
  NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE,
  NEXT_PUBLIC_FIREBASE_AUTH_ENABLED: process.env.NEXT_PUBLIC_FIREBASE_AUTH_ENABLED,
  NEXT_PUBLIC_FIREBASE_API_KEY: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  NEXT_PUBLIC_FIREBASE_PROJECT_ID: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  NEXT_PUBLIC_FIREBASE_APP_ID: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
} as const;

function parseBool(name: string, raw: string | undefined, fallback: boolean): boolean {
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

function trimmed(raw: string | undefined): string {
  return (raw ?? "").trim();
}

function requiredWhenEnabled(name: string, value: string, errors: string[]): void {
  if (!value) {
    errors.push(`${name} is required when NEXT_PUBLIC_FIREBASE_AUTH_ENABLED=true.`);
  }
}

function loadPublicWebConfig(): PublicWebConfig {
  const firebaseAuthEnabled = parseBool(
    "NEXT_PUBLIC_FIREBASE_AUTH_ENABLED",
    PUBLIC_ENV.NEXT_PUBLIC_FIREBASE_AUTH_ENABLED,
    false
  );
  const siteUrl = trimmed(PUBLIC_ENV.NEXT_PUBLIC_SITE_URL) || "https://poverlay.com";
  const apiBase = trimmed(PUBLIC_ENV.NEXT_PUBLIC_API_BASE).replace(/\/+$/, "");

  const firebaseApiKey = trimmed(PUBLIC_ENV.NEXT_PUBLIC_FIREBASE_API_KEY);
  const firebaseAuthDomain = trimmed(PUBLIC_ENV.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN);
  const firebaseProjectId = trimmed(PUBLIC_ENV.NEXT_PUBLIC_FIREBASE_PROJECT_ID);
  const firebaseAppId = trimmed(PUBLIC_ENV.NEXT_PUBLIC_FIREBASE_APP_ID);
  const firebaseMessagingSenderId = trimmed(PUBLIC_ENV.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID);
  const firebaseStorageBucket = trimmed(PUBLIC_ENV.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET);

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
