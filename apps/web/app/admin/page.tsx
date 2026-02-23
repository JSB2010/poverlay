"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/components/auth-provider";
import { apiUrl } from "@/lib/api-base";
import { PUBLIC_WEB_CONFIG } from "@/lib/public-config";

const CONFIGURED_API_BASE = PUBLIC_WEB_CONFIG.apiBase;

type OpsOverview = {
  now?: string;
  queue?: {
    configured_workers?: number;
    active_jobs_count?: number;
    enqueued_jobs_count?: number;
    queue_depth?: number;
  };
  ops?: Record<string, unknown>;
  disk?: {
    job_dirs?: number;
    files?: number;
    bytes_human?: string;
  };
  firestore?: {
    enabled?: boolean;
    summary?: {
      total_jobs?: number;
      terminal_jobs?: number;
      users_with_jobs?: number;
      status_counts?: Record<string, number>;
      oldest_terminal_at?: string | null;
      newest_terminal_at?: string | null;
    } | null;
  };
  runtime?: {
    job_cleanup_enabled?: boolean;
    job_cleanup_interval_seconds?: number;
    job_recovery_interval_seconds?: number;
    job_queue_worker_count?: number;
    job_output_retention_hours?: number;
    job_database_cleanup_enabled?: boolean;
    job_database_cleanup_interval_seconds?: number;
    job_database_retention_days?: number;
    ffmpeg_threads_per_render?: number;
  };
  pending_jobs?: Array<{
    id?: string;
    uid?: string;
    status?: string;
    progress?: number;
    message?: string;
    updated_at?: string;
    videos?: {
      total?: number;
      queued?: number;
      running?: number;
      completed?: number;
      failed?: number;
    };
  }>;
};

function buildApiUrl(path: string): string {
  return apiUrl(path, CONFIGURED_API_BASE);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

async function readApiPayload(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }
  return null;
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (isRecord(payload) && typeof payload.detail === "string" && payload.detail.trim()) {
    return payload.detail;
  }
  return fallback;
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "--";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

export default function AdminPage() {
  const { account, adminConfigured, getIdToken, isAdmin, isAccessLoading, refreshAccess } = useAuth();
  const [overview, setOverview] = useState<OpsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [runningAction, setRunningAction] = useState<string | null>(null);
  const [requeueJobId, setRequeueJobId] = useState("");
  const [cancelJobId, setCancelJobId] = useState("");

  const loadOverview = useCallback(async (): Promise<void> => {
    if (!account?.uid || !isAdmin) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const token = await getIdToken();
      if (!token) {
        throw new Error("Authentication token unavailable.");
      }

      const response = await fetch(buildApiUrl("/api/admin/ops/overview"), {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      const payload = (await readApiPayload(response)) as OpsOverview | null;
      if (!response.ok) {
        throw new Error(extractErrorMessage(payload, "Could not load admin overview."));
      }
      setOverview(payload);
    } catch (actionError) {
      const message = actionError instanceof Error ? actionError.message : "Could not load admin overview.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [account?.uid, getIdToken, isAdmin]);

  useEffect(() => {
    if (!account?.uid || isAccessLoading || !isAdmin) {
      setLoading(false);
      setOverview(null);
      return;
    }
    void loadOverview();
  }, [account?.uid, isAccessLoading, isAdmin, loadOverview]);

  async function runAction(actionId: string, request: () => Promise<void>): Promise<void> {
    setRunningAction(actionId);
    setActionMessage(null);
    setError(null);
    try {
      await request();
      await loadOverview();
    } catch (actionError) {
      const message = actionError instanceof Error ? actionError.message : "Action failed.";
      setError(message);
    } finally {
      setRunningAction(null);
    }
  }

  async function callAdminPost(path: string, body: Record<string, unknown> = {}): Promise<unknown> {
    if (!isAdmin) {
      throw new Error("Admin access required.");
    }
    const token = await getIdToken();
    if (!token) {
      throw new Error("Authentication token unavailable.");
    }

    const response = await fetch(buildApiUrl(path), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
    });
    const payload = await readApiPayload(response);
    if (!response.ok) {
      throw new Error(extractErrorMessage(payload, "Operation failed."));
    }
    return payload;
  }

  async function handleManualReconcile(): Promise<void> {
    await runAction("reconcile", async () => {
      const payload = await callAdminPost("/api/admin/ops/reconcile");
      if (isRecord(payload) && isRecord(payload.summary)) {
        const requeued = Number(payload.summary.requeued ?? 0);
        const failedMissingDir = Number(payload.summary.failed_missing_dir ?? 0);
        const failedMissingInputs = Number(payload.summary.failed_missing_inputs ?? 0);
        setActionMessage(
          `Reconcile complete. Requeued ${requeued}, failed missing-dir ${failedMissingDir}, failed missing-inputs ${failedMissingInputs}.`,
        );
      } else {
        setActionMessage("Reconcile complete.");
      }
    });
  }

  async function handleManualCleanup(): Promise<void> {
    await runAction("cleanup", async () => {
      const payload = await callAdminPost("/api/admin/ops/cleanup", {
        include_database: true,
        force_database: true,
      });
      if (isRecord(payload) && isRecord(payload.summary) && isRecord(payload.summary.disk)) {
        const deletedDirs = Number(payload.summary.disk.deleted_dirs ?? 0);
        setActionMessage(`Cleanup complete. Deleted ${deletedDirs} expired job directories.`);
      } else {
        setActionMessage("Cleanup complete.");
      }
    });
  }

  async function handleRequeue(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const jobId = requeueJobId.trim();
    if (!jobId) {
      setError("Enter a job ID to requeue.");
      return;
    }

    await runAction("requeue", async () => {
      await callAdminPost(`/api/admin/jobs/${encodeURIComponent(jobId)}/requeue`, { reset_failed_videos: true });
      setActionMessage(`Job ${jobId} requeued.`);
      setRequeueJobId("");
    });
  }

  async function handleCancel(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const jobId = cancelJobId.trim();
    if (!jobId) {
      setError("Enter a job ID to cancel.");
      return;
    }

    await runAction("cancel", async () => {
      await callAdminPost(`/api/admin/jobs/${encodeURIComponent(jobId)}/cancel`, { reason: "Admin queue maintenance" });
      setActionMessage(`Job ${jobId} cancelled.`);
      setCancelJobId("");
    });
  }

  async function quickRequeue(jobId: string): Promise<void> {
    await runAction(`requeue-${jobId}`, async () => {
      await callAdminPost(`/api/admin/jobs/${encodeURIComponent(jobId)}/requeue`, { reset_failed_videos: true });
      setActionMessage(`Job ${jobId} requeued.`);
    });
  }

  async function quickCancel(jobId: string): Promise<void> {
    await runAction(`cancel-${jobId}`, async () => {
      await callAdminPost(`/api/admin/jobs/${encodeURIComponent(jobId)}/cancel`, { reason: "Admin dashboard quick action" });
      setActionMessage(`Job ${jobId} cancelled.`);
    });
  }

  const statusRows = useMemo(() => {
    const counts = overview?.firestore?.summary?.status_counts ?? {};
    return Object.entries(counts).sort(([a], [b]) => a.localeCompare(b));
  }, [overview?.firestore?.summary?.status_counts]);

  if (isAccessLoading) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6 sm:py-12">
        <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-card)] p-8 text-center shadow-sm">
          <p className="text-sm font-medium text-[var(--color-primary)]">Checking admin access</p>
          <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">Validating your role before loading operations.</p>
        </section>
      </main>
    );
  }

  if (!isAdmin) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6 sm:py-12">
        <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-card)] p-8 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-primary)]">Admin Ops</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight">Unauthorized</h1>
          <p className="mt-3 text-sm text-[var(--color-muted-foreground)]">
            {adminConfigured
              ? "Your account is authenticated but not in the admin allow-list."
              : "Admin access is not configured on the API. Set ADMIN_UIDS and restart the API."}
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void refreshAccess()}
              className="rounded-xl border border-[var(--color-border)] px-4 py-2.5 text-sm font-medium transition-colors hover:bg-[var(--color-muted)]/20"
            >
              Re-check access
            </button>
            <a
              href="/studio"
              className="rounded-xl bg-[var(--color-primary)] px-4 py-2.5 text-sm font-medium text-white no-underline transition-colors hover:bg-[var(--color-primary)]/90"
            >
              Back to Studio
            </a>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-12">
      <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-card)] p-6 shadow-sm sm:p-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-primary)]">Admin Ops</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight">Queue and cleanup control</h1>
            <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
              Monitor queue health, disk usage, Firestore job retention, and trigger recovery actions.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void loadOverview()}
            disabled={loading || runningAction !== null}
            className="rounded-xl border border-[var(--color-border)] px-4 py-2.5 text-sm font-medium transition-colors hover:bg-[var(--color-muted)]/20 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {(error || actionMessage) && (
          <div className="mt-5 space-y-2">
            {error && <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-600">{error}</p>}
            {actionMessage && (
              <p className="rounded-lg border border-green-500/30 bg-green-500/10 px-3 py-2 text-sm text-green-700">{actionMessage}</p>
            )}
          </div>
        )}

        <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted-foreground)]">Queue depth</p>
            <p className="mt-2 text-2xl font-semibold">{overview?.queue?.queue_depth ?? "--"}</p>
          </div>
          <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted-foreground)]">Active jobs</p>
            <p className="mt-2 text-2xl font-semibold">{overview?.queue?.active_jobs_count ?? "--"}</p>
          </div>
          <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted-foreground)]">Disk usage</p>
            <p className="mt-2 text-2xl font-semibold">{overview?.disk?.bytes_human ?? "--"}</p>
          </div>
          <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted-foreground)]">Firestore jobs</p>
            <p className="mt-2 text-2xl font-semibold">{overview?.firestore?.summary?.total_jobs ?? "--"}</p>
          </div>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.3fr_1fr]">
          <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-lg font-semibold">Lifecycle metrics</h2>
            <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">Rolling counters since API process start.</p>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-[var(--color-border)] px-3 py-2">
                <p className="text-xs text-[var(--color-muted-foreground)]">Enqueued</p>
                <p className="text-lg font-semibold">{String(overview?.ops?.queue_enqueued_total ?? "--")}</p>
              </div>
              <div className="rounded-xl border border-[var(--color-border)] px-3 py-2">
                <p className="text-xs text-[var(--color-muted-foreground)]">Dequeued</p>
                <p className="text-lg font-semibold">{String(overview?.ops?.queue_dequeued_total ?? "--")}</p>
              </div>
              <div className="rounded-xl border border-[var(--color-border)] px-3 py-2">
                <p className="text-xs text-[var(--color-muted-foreground)]">Reconcile runs</p>
                <p className="text-lg font-semibold">{String(overview?.ops?.reconcile_runs_total ?? "--")}</p>
              </div>
              <div className="rounded-xl border border-[var(--color-border)] px-3 py-2">
                <p className="text-xs text-[var(--color-muted-foreground)]">Cleanup runs</p>
                <p className="text-lg font-semibold">{String(overview?.ops?.cleanup_runs_total ?? "--")}</p>
              </div>
              <div className="rounded-xl border border-[var(--color-border)] px-3 py-2">
                <p className="text-xs text-[var(--color-muted-foreground)]">Queue worker crashes</p>
                <p className="text-lg font-semibold">{String(overview?.ops?.queue_worker_crash_total ?? "--")}</p>
              </div>
              <div className="rounded-xl border border-[var(--color-border)] px-3 py-2">
                <p className="text-xs text-[var(--color-muted-foreground)]">Deleted Firestore jobs</p>
                <p className="text-lg font-semibold">{String(overview?.ops?.cleanup_deleted_firestore_jobs_total ?? "--")}</p>
              </div>
            </div>
          </section>

          <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
            <h2 className="text-lg font-semibold">Actions</h2>
            <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">Use for manual recovery and queue intervention.</p>

            <div className="mt-4 grid gap-3">
              <button
                type="button"
                onClick={() => void handleManualReconcile()}
                disabled={runningAction !== null}
                className="rounded-xl bg-[var(--color-primary)] px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[var(--color-primary)]/90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {runningAction === "reconcile" ? "Reconciling..." : "Run reconcile now"}
              </button>
              <button
                type="button"
                onClick={() => void handleManualCleanup()}
                disabled={runningAction !== null}
                className="rounded-xl border border-[var(--color-border)] px-4 py-2.5 text-sm font-medium transition-colors hover:bg-[var(--color-muted)]/20 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {runningAction === "cleanup" ? "Cleaning..." : "Run cleanup now"}
              </button>
            </div>

            <form onSubmit={(event) => void handleRequeue(event)} className="mt-5 space-y-3">
              <label className="block">
                <span className="mb-1 block text-sm font-medium">Requeue job ID</span>
                <input
                  type="text"
                  value={requeueJobId}
                  onChange={(event) => setRequeueJobId(event.target.value)}
                  className="block w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2.5 text-sm outline-none transition-shadow focus:border-[var(--color-primary)] focus:ring-4 focus:ring-[var(--color-primary)]/15"
                  placeholder="e.g. 72d7fc9edd8147419e3d2680dd000be2"
                />
              </label>
              <button
                type="submit"
                disabled={runningAction !== null}
                className="w-full rounded-xl border border-[var(--color-border)] px-4 py-2.5 text-sm font-medium transition-colors hover:bg-[var(--color-muted)]/20 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {runningAction === "requeue" ? "Requeuing..." : "Requeue job"}
              </button>
            </form>

            <form onSubmit={(event) => void handleCancel(event)} className="mt-4 space-y-3">
              <label className="block">
                <span className="mb-1 block text-sm font-medium">Cancel job ID</span>
                <input
                  type="text"
                  value={cancelJobId}
                  onChange={(event) => setCancelJobId(event.target.value)}
                  className="block w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2.5 text-sm outline-none transition-shadow focus:border-[var(--color-primary)] focus:ring-4 focus:ring-[var(--color-primary)]/15"
                  placeholder="e.g. 72d7fc9edd8147419e3d2680dd000be2"
                />
              </label>
              <button
                type="submit"
                disabled={runningAction !== null}
                className="w-full rounded-xl border border-red-500/40 px-4 py-2.5 text-sm font-medium text-red-700 transition-colors hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {runningAction === "cancel" ? "Cancelling..." : "Cancel queued job"}
              </button>
            </form>
          </section>
        </div>

        <section className="mt-6 rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
          <h2 className="text-lg font-semibold">Status distribution</h2>
          <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">
            Oldest terminal: {formatDateTime(overview?.firestore?.summary?.oldest_terminal_at)}. Newest terminal:{" "}
            {formatDateTime(overview?.firestore?.summary?.newest_terminal_at)}.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {statusRows.length > 0 ? (
              statusRows.map(([status, count]) => (
                <div key={status} className="rounded-xl border border-[var(--color-border)] px-3 py-2">
                  <p className="text-xs uppercase tracking-wide text-[var(--color-muted-foreground)]">{status}</p>
                  <p className="text-lg font-semibold">{count}</p>
                </div>
              ))
            ) : (
              <p className="text-sm text-[var(--color-muted-foreground)]">No status data available.</p>
            )}
          </div>
        </section>

        <section className="mt-6 rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
          <h2 className="text-lg font-semibold">Pending jobs</h2>
          <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">
            Most recently updated queued/running jobs. Use quick actions for backlog management.
          </p>
          <div className="mt-4 space-y-3">
            {(overview?.pending_jobs ?? []).length > 0 ? (
              (overview?.pending_jobs ?? []).map((job) => {
                const jobId = String(job.id ?? "");
                const actionBusy = runningAction !== null;
                return (
                  <div key={jobId} className="rounded-xl border border-[var(--color-border)] px-3 py-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold">{jobId || "(unknown job)"}</p>
                        <p className="text-xs text-[var(--color-muted-foreground)]">
                          User: {job.uid ?? "--"} • {job.status ?? "--"} • {job.progress ?? 0}% • Updated {formatDateTime(job.updated_at)}
                        </p>
                        <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">
                          Clips: {job.videos?.completed ?? 0} done / {job.videos?.running ?? 0} running / {job.videos?.queued ?? 0} queued /{" "}
                          {job.videos?.failed ?? 0} failed (total {job.videos?.total ?? 0})
                        </p>
                        {job.message && <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">{job.message}</p>}
                      </div>
                      <div className="flex shrink-0 gap-2">
                        <button
                          type="button"
                          onClick={() => void quickRequeue(jobId)}
                          disabled={!jobId || actionBusy}
                          className="rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-xs font-medium transition-colors hover:bg-[var(--color-muted)]/20 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          Requeue
                        </button>
                        <button
                          type="button"
                          onClick={() => void quickCancel(jobId)}
                          disabled={!jobId || actionBusy}
                          className="rounded-lg border border-red-500/40 px-3 py-1.5 text-xs font-medium text-red-700 transition-colors hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })
            ) : (
              <p className="text-sm text-[var(--color-muted-foreground)]">No queued or running jobs.</p>
            )}
          </div>
        </section>

        <section className="mt-6 rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
          <h2 className="text-lg font-semibold">Runtime controls</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div className="rounded-xl border border-[var(--color-border)] px-3 py-2">
              <p className="text-xs text-[var(--color-muted-foreground)]">Queue workers</p>
              <p className="text-sm font-semibold">{overview?.runtime?.job_queue_worker_count ?? "--"}</p>
            </div>
            <div className="rounded-xl border border-[var(--color-border)] px-3 py-2">
              <p className="text-xs text-[var(--color-muted-foreground)]">Recovery interval</p>
              <p className="text-sm font-semibold">{overview?.runtime?.job_recovery_interval_seconds ?? "--"}s</p>
            </div>
            <div className="rounded-xl border border-[var(--color-border)] px-3 py-2">
              <p className="text-xs text-[var(--color-muted-foreground)]">Cleanup interval</p>
              <p className="text-sm font-semibold">{overview?.runtime?.job_cleanup_interval_seconds ?? "--"}s</p>
            </div>
            <div className="rounded-xl border border-[var(--color-border)] px-3 py-2">
              <p className="text-xs text-[var(--color-muted-foreground)]">Output retention</p>
              <p className="text-sm font-semibold">{overview?.runtime?.job_output_retention_hours ?? "--"}h</p>
            </div>
            <div className="rounded-xl border border-[var(--color-border)] px-3 py-2">
              <p className="text-xs text-[var(--color-muted-foreground)]">DB retention</p>
              <p className="text-sm font-semibold">{overview?.runtime?.job_database_retention_days ?? "--"}d</p>
            </div>
            <div className="rounded-xl border border-[var(--color-border)] px-3 py-2">
              <p className="text-xs text-[var(--color-muted-foreground)]">FFmpeg threads/render</p>
              <p className="text-sm font-semibold">{overview?.runtime?.ffmpeg_threads_per_render ?? "--"}</p>
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}
