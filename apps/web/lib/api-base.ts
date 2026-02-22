const LOCAL_DEV_API_BASE = "http://127.0.0.1:8787";
const LOCAL_DEV_WEB_BASES = new Set(["http://localhost:3000", "http://127.0.0.1:3000"]);

function trimTrailingSlashes(value: string): string {
  return value.replace(/\/+$/, "");
}

export function resolveApiBase(configuredApiBase: string): string {
  const normalizedConfigured = trimTrailingSlashes(configuredApiBase);
  if (process.env.NODE_ENV !== "development") {
    return normalizedConfigured;
  }
  if (typeof window === "undefined") {
    return normalizedConfigured;
  }

  const host = window.location.hostname;
  const isLocalHost = host === "localhost" || host === "127.0.0.1";
  if (!isLocalHost) {
    return normalizedConfigured;
  }

  if (!normalizedConfigured || LOCAL_DEV_WEB_BASES.has(normalizedConfigured)) {
    return LOCAL_DEV_API_BASE;
  }

  return normalizedConfigured;
}

export function apiUrl(path: string, configuredApiBase: string): string {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }

  const base = resolveApiBase(configuredApiBase);
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return base ? `${base}${normalizedPath}` : normalizedPath;
}
