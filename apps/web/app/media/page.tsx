"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/components/auth-provider";
import { apiUrl } from "@/lib/api-base";
import { PUBLIC_WEB_CONFIG } from "@/lib/public-config";

type MediaItem = {
  id: string;
  job_id: string;
  status: string;
  job_status: string;
  job_message?: string | null;
  title: string;
  input_name: string;
  output_name?: string | null;
  size_bytes?: number | null;
  render_profile_label?: string | null;
  source_resolution?: string | null;
  source_fps?: string | null;
  progress?: number | null;
  detail?: string | null;
  error?: string | null;
  log_name?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  can_download: boolean;
};

type MediaListResponse = {
  items?: MediaItem[];
  page?: number;
  total_pages?: number;
};

const CONFIGURED_API_BASE = PUBLIC_WEB_CONFIG.apiBase;
const PAGE_SIZE = 12;
const SORT_FIELDS = ["created_at", "updated_at", "status", "title"] as const;
const SORT_ORDERS = ["desc", "asc"] as const;

function buildApiUrl(path: string): string {
  return apiUrl(path, CONFIGURED_API_BASE);
}

function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (typeof payload === "string") {
    const message = payload.trim();
    return message || fallback;
  }

  if (isObjectRecord(payload)) {
    for (const key of ["detail", "message", "error"]) {
      const value = payload[key];
      if (typeof value === "string" && value.trim()) {
        return value;
      }
    }
  }

  return fallback;
}

async function readApiPayload(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

function formatBytes(value?: number | null): string {
  if (value === undefined || value === null) {
    return "";
  }

  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`;
}

function statusBadgeClasses(status: string): string {
  if (status === "completed") {
    return "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400";
  }
  if (status === "failed" || status === "completed_with_errors") {
    return "bg-red-500/10 text-red-600 dark:text-red-400";
  }
  if (status === "running") {
    return "bg-amber-500/10 text-amber-600 dark:text-amber-400";
  }
  return "bg-blue-500/10 text-blue-600 dark:text-blue-400";
}

function clampProgress(value?: number | null): number {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(value)));
}

function cleanConsoleText(value?: string | null): string {
  if (!value) {
    return "";
  }
  return value.replace(/\x1B\[[0-?]*[ -/]*[@-~]/g, "").trim();
}

export default function MediaPage() {
  const { isEnabled: isAuthEnabled, getIdToken } = useAuth();
  const [items, setItems] = useState<MediaItem[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [sortBy, setSortBy] = useState<(typeof SORT_FIELDS)[number]>("created_at");
  const [sortOrder, setSortOrder] = useState<(typeof SORT_ORDERS)[number]>("desc");
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const authHeaders = useCallback(async (): Promise<Headers> => {
    const headers = new Headers();
    if (!isAuthEnabled) {
      return headers;
    }

    const token = await getIdToken();
    if (!token) {
      throw new Error("Your session expired. Please sign in again.");
    }

    headers.set("Authorization", `Bearer ${token}`);
    return headers;
  }, [getIdToken, isAuthEnabled]);

  const loadMedia = useCallback(async (options?: { silent?: boolean }) => {
    const silent = options?.silent === true;
    if (!silent) {
      setIsLoading(true);
    }
    setErrorMessage(null);

    try {
      const response = await fetch(
        buildApiUrl(`/api/media?page=${page}&page_size=${PAGE_SIZE}&sort_by=${sortBy}&sort_order=${sortOrder}`),
        { headers: await authHeaders() },
      );
      const payload = await readApiPayload(response);
      if (!response.ok) {
        throw new Error(extractErrorMessage(payload, "Failed to load media library."));
      }
      if (!isObjectRecord(payload)) {
        throw new Error("Invalid media response.");
      }

      const media = payload as MediaListResponse;
      setItems(Array.isArray(media.items) ? media.items : []);
      setTotalPages(typeof media.total_pages === "number" ? Math.max(1, media.total_pages) : 1);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load media library.";
      setErrorMessage(message);
      setItems([]);
      setTotalPages(1);
    } finally {
      if (!silent) {
        setIsLoading(false);
      }
    }
  }, [authHeaders, page, sortBy, sortOrder]);

  useEffect(() => {
    void loadMedia();
  }, [loadMedia]);

  const activeRenderCount = useMemo(
    () => items.filter((item) => item.status === "queued" || item.status === "running").length,
    [items]
  );

  useEffect(() => {
    if (activeRenderCount === 0) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void loadMedia({ silent: true });
    }, 2000);

    return () => window.clearInterval(intervalId);
  }, [activeRenderCount, loadMedia]);

  const itemCountLabel = useMemo(() => `${items.length} item${items.length === 1 ? "" : "s"} on this page`, [items.length]);

  async function renameMedia(item: MediaItem): Promise<void> {
    const nextTitle = window.prompt("Rename media title", item.title);
    if (!nextTitle || nextTitle.trim() === item.title.trim()) {
      return;
    }

    const key = `${item.job_id}:${item.id}:rename`;
    setBusyKey(key);
    setErrorMessage(null);
    try {
      const headers = await authHeaders();
      headers.set("Content-Type", "application/json");
      const response = await fetch(buildApiUrl(`/api/media/${item.job_id}/${item.id}`), {
        method: "PATCH",
        headers,
        body: JSON.stringify({ title: nextTitle.trim() }),
      });
      const payload = await readApiPayload(response);
      if (!response.ok) {
        throw new Error(extractErrorMessage(payload, "Rename failed."));
      }
      await loadMedia();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Rename failed.");
    } finally {
      setBusyKey(null);
    }
  }

  async function deleteMedia(item: MediaItem): Promise<void> {
    const confirmed = window.confirm(`Delete "${item.title}"? This cannot be undone.`);
    if (!confirmed) {
      return;
    }

    const key = `${item.job_id}:${item.id}:delete`;
    setBusyKey(key);
    setErrorMessage(null);
    try {
      const response = await fetch(buildApiUrl(`/api/media/${item.job_id}/${item.id}`), {
        method: "DELETE",
        headers: await authHeaders(),
      });
      const payload = await readApiPayload(response);
      if (!response.ok) {
        throw new Error(extractErrorMessage(payload, "Delete failed."));
      }
      await loadMedia();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Delete failed.");
    } finally {
      setBusyKey(null);
    }
  }

  async function downloadMedia(item: MediaItem): Promise<void> {
    const key = `${item.job_id}:${item.id}:download`;
    setBusyKey(key);
    setErrorMessage(null);
    try {
      const response = await fetch(buildApiUrl(`/api/media/${item.job_id}/${item.id}/download-link`), {
        method: "POST",
        headers: await authHeaders(),
      });
      const payload = await readApiPayload(response);
      if (!response.ok) {
        throw new Error(extractErrorMessage(payload, "Download link request failed."));
      }
      if (!isObjectRecord(payload) || typeof payload.url !== "string" || !payload.url) {
        throw new Error("Invalid download link response.");
      }

      window.open(payload.url, "_blank", "noopener,noreferrer");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Download link request failed.");
    } finally {
      setBusyKey(null);
    }
  }

  async function downloadRenderLog(item: MediaItem): Promise<void> {
    if (!item.log_name) {
      return;
    }

    const key = `${item.job_id}:${item.id}:log`;
    setBusyKey(key);
    setErrorMessage(null);
    try {
      const response = await fetch(buildApiUrl(`/api/jobs/${item.job_id}/log/${encodeURIComponent(item.log_name)}`), {
        headers: await authHeaders(),
      });
      if (!response.ok) {
        const payload = await readApiPayload(response);
        throw new Error(extractErrorMessage(payload, "Failed to download renderer log."));
      }

      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = item.log_name;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to download renderer log.");
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-8 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--color-primary)]">Media</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight">Render Library</h1>
            <p className="mt-3 max-w-2xl text-sm text-[var(--color-muted-foreground)]">
              View your own queued, running, completed, and failed renders. Rename, delete, or request a fresh
              download link for completed media.
            </p>
          </div>
          <div className="flex gap-2">
            <Link
              href="/studio"
              className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white no-underline"
            >
              Open Studio
            </Link>
            <Link
              href="/settings"
              className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-medium text-foreground no-underline"
            >
              Account settings
            </Link>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <label className="text-xs font-medium text-[var(--color-muted-foreground)]">
            Sort by
            <select
              value={sortBy}
              onChange={(event) => {
                setPage(1);
                setSortBy(event.target.value as (typeof SORT_FIELDS)[number]);
              }}
              className="ml-2 rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-2 py-1 text-sm"
            >
              <option value="created_at">Created</option>
              <option value="updated_at">Updated</option>
              <option value="status">Status</option>
              <option value="title">Title</option>
            </select>
          </label>

          <label className="text-xs font-medium text-[var(--color-muted-foreground)]">
            Order
            <select
              value={sortOrder}
              onChange={(event) => {
                setPage(1);
                setSortOrder(event.target.value as (typeof SORT_ORDERS)[number]);
              }}
              className="ml-2 rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-2 py-1 text-sm"
            >
              <option value="desc">Descending</option>
              <option value="asc">Ascending</option>
            </select>
          </label>

          <span className="text-xs text-[var(--color-muted-foreground)]">{itemCountLabel}</span>
          {activeRenderCount > 0 && (
            <span className="text-xs text-[var(--color-muted-foreground)]">
              {activeRenderCount} active render{activeRenderCount === 1 ? "" : "s"} (auto-refreshing)
            </span>
          )}
        </div>

        {errorMessage && (
          <div className="mt-4 rounded-lg border border-red-500/50 bg-red-500/10 px-4 py-3 text-sm text-red-600 dark:text-red-400">
            {errorMessage}
          </div>
        )}

        {isLoading ? (
          <div className="mt-6 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-6 text-sm text-[var(--color-muted-foreground)]">
            Loading media library...
          </div>
        ) : items.length === 0 ? (
          <div className="mt-6 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-6 text-sm text-[var(--color-muted-foreground)]">
            No media found yet. Start a render in Studio to populate your library.
          </div>
        ) : (
          <ul className="mt-6 grid gap-4 sm:grid-cols-2">
            {items.map((item) => {
              const cardKey = `${item.job_id}:${item.id}`;
              const isBusy = busyKey !== null && busyKey.startsWith(cardKey);
              const canDelete = item.status !== "queued" && item.status !== "running";
              const progress = clampProgress(item.progress);
              const statusLabel = item.status.replaceAll("_", " ");
              const failureReason = cleanConsoleText(item.error || item.job_message);
              const detail = cleanConsoleText(item.detail);
              const isActive = item.status === "queued" || item.status === "running";
              const isFailure = item.status === "failed" || item.status === "completed_with_errors";

              return (
                <li key={cardKey} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold">{item.title}</p>
                      <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">
                        Job {item.job_id} • {item.input_name}
                      </p>
                    </div>
                    <span className={`rounded-full px-2 py-1 text-xs font-medium ${statusBadgeClasses(item.status)}`}>
                      {isActive ? `${statusLabel} ${progress}%` : statusLabel}
                    </span>
                  </div>

                  {isActive && (
                    <div className="mt-3">
                      <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--color-muted)]/50">
                        <div
                          className="h-full rounded-full bg-[var(--color-primary)] transition-[width] duration-300"
                          style={{ width: `${progress}%` }}
                        />
                      </div>
                      <p className="mt-2 text-xs text-[var(--color-muted-foreground)]">
                        {detail || "Render queued"}
                      </p>
                    </div>
                  )}

                  {!isActive && isFailure && failureReason && (
                    <p className="mt-3 rounded-md border border-red-500/30 bg-red-500/10 px-2.5 py-2 text-xs text-red-700 dark:text-red-300">
                      {failureReason}
                    </p>
                  )}

                  {!isActive && detail && (!isFailure || detail !== failureReason) && (
                    <p className="mt-2 text-xs text-[var(--color-muted-foreground)]">{detail}</p>
                  )}

                  <p className="mt-3 text-xs text-[var(--color-muted-foreground)]">
                    {[
                      item.render_profile_label,
                      item.source_resolution,
                      item.source_fps ? `${item.source_fps} fps` : "",
                      formatBytes(item.size_bytes),
                    ]
                      .filter(Boolean)
                      .join(" • ") || "No output metadata yet"}
                  </p>

                  <div className="mt-4 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => void renameMedia(item)}
                      disabled={isBusy}
                      className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-xs font-medium transition-colors hover:bg-[var(--color-muted)]/30 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Rename
                    </button>
                    <button
                      type="button"
                      onClick={() => void deleteMedia(item)}
                      disabled={isBusy || !canDelete}
                      className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-xs font-medium transition-colors hover:bg-[var(--color-muted)]/30 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Delete
                    </button>
                    <button
                      type="button"
                      onClick={() => void downloadMedia(item)}
                      disabled={isBusy || !item.can_download}
                      className="rounded-md bg-[var(--color-primary)] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[var(--color-primary)]/90 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Download
                    </button>
                    <button
                      type="button"
                      onClick={() => void downloadRenderLog(item)}
                      disabled={isBusy || !item.log_name}
                      className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-xs font-medium transition-colors hover:bg-[var(--color-muted)]/30 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Download log
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}

        <div className="mt-6 flex items-center justify-between">
          <button
            type="button"
            onClick={() => setPage((current) => Math.max(1, current - 1))}
            disabled={page <= 1 || isLoading}
            className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
          >
            Previous
          </button>
          <p className="text-xs text-[var(--color-muted-foreground)]">
            Page {page} of {totalPages}
          </p>
          <button
            type="button"
            onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
            disabled={page >= totalPages || isLoading}
            className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </section>
    </main>
  );
}
