import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { getCurrent, onOpenUrl } from "@tauri-apps/plugin-deep-link";
import { open } from "@tauri-apps/plugin-shell";
import { useEffect, useMemo, useState } from "react";

type WorkerStatus = "idle" | "connected" | "rendering" | "error";

type WorkerHealth = {
  name?: string;
  version?: string;
  status?: string;
  paired?: boolean;
  worker_session_id?: string | null;
  current_job_id?: string | null;
};

type DesktopPaths = {
  output_dir?: string | null;
};

const LOCAL_WORKER_BASE = "http://127.0.0.1:47981";
const STUDIO_URL = (import.meta.env.VITE_POVERLAY_STUDIO_URL as string | undefined) || "https://poverlay.com/studio";

function statusText(value: WorkerStatus): string {
  if (value === "connected") {
    return "Connected";
  }
  if (value === "rendering") {
    return "Rendering";
  }
  if (value === "error") {
    return "Needs attention";
  }
  return "Starting";
}

function compactId(value: string | null | undefined): string {
  if (!value) {
    return "None";
  }
  return value.length > 12 ? `${value.slice(0, 12)}...` : value;
}

function formatSeenAt(value: number | null): string {
  if (!value) {
    return "Not yet";
  }
  return new Date(value).toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
}

export function App() {
  const [status, setStatus] = useState<WorkerStatus>("idle");
  const [detail, setDetail] = useState("Starting local worker");
  const [health, setHealth] = useState<WorkerHealth | null>(null);
  const [lastSeenAt, setLastSeenAt] = useState<number | null>(null);
  const [lastDeepLink, setLastDeepLink] = useState<string | null>(null);
  const [outputDir, setOutputDir] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const stateLabel = statusText(status);

  const activeJobLabel = useMemo(() => compactId(health?.current_job_id), [health?.current_job_id]);
  const sessionLabel = useMemo(() => compactId(health?.worker_session_id), [health?.worker_session_id]);

  function recordDeepLink(url: string) {
    setLastDeepLink(url);
    if (url.startsWith("poverlay://connect")) {
      setDetail("Pairing link received. Return to Studio to start the render.");
    }
  }

  async function openStudio() {
    setActionError(null);
    try {
      await open(STUDIO_URL);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not open Studio");
    }
  }

  async function openOutputFolder() {
    if (!outputDir) {
      setActionError("Output folder is not available yet.");
      return;
    }
    setActionError(null);
    try {
      await open(outputDir);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not open output folder");
    }
  }

  useEffect(() => {
    let disposed = false;

    async function loadDesktopPaths() {
      try {
        const paths = await invoke<DesktopPaths>("desktop_paths");
        if (!disposed) {
          setOutputDir(paths.output_dir ?? null);
        }
      } catch {
        if (!disposed) {
          setOutputDir(null);
        }
      }
    }

    void loadDesktopPaths();

    return () => {
      disposed = true;
    };
  }, []);

  useEffect(() => {
    let disposed = false;
    let attempts = 0;

    async function pollWorker() {
      attempts += 1;
      try {
        const response = await fetch(`${LOCAL_WORKER_BASE}/health`, { cache: "no-store" });
        if (!response.ok) {
          throw new Error(`Local worker returned ${response.status}`);
        }
        const payload = (await response.json()) as WorkerHealth;
        if (disposed) {
          return;
        }
        setHealth(payload);
        setLastSeenAt(Date.now());
        if (payload.status === "rendering") {
          setStatus("rendering");
          setDetail(payload.current_job_id ? `Rendering job ${payload.current_job_id}` : "Rendering locally");
          return;
        }
        setStatus("connected");
        setDetail(payload.paired ? "Paired with Studio" : "Listening on 127.0.0.1:47981");
      } catch (error) {
        if (disposed) {
          return;
        }
        setStatus(attempts < 10 ? "idle" : "error");
        setDetail(attempts < 10 ? "Starting local worker" : error instanceof Error ? error.message : "Could not reach local worker");
      }
    }

    void pollWorker();
    const interval = window.setInterval(() => {
      void pollWorker();
    }, 1500);

    return () => {
      disposed = true;
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    let disposed = false;
    const cleanups: Array<() => void> = [];

    async function subscribeToDeepLinks() {
      try {
        cleanups.push(
          await listen<string>("worker-started", () => {
            setStatus("connected");
            setDetail("Listening on 127.0.0.1:47981");
          }),
        );

        cleanups.push(
          await listen<string>("worker-error", (event) => {
            setStatus("error");
            setDetail(event.payload);
          }),
        );

        const currentUrls = await getCurrent();
        if (!disposed && currentUrls?.length) {
          recordDeepLink(currentUrls[currentUrls.length - 1]);
        }

        cleanups.push(
          await onOpenUrl((urls) => {
            const latestUrl = urls[urls.length - 1];
            if (latestUrl) {
              recordDeepLink(latestUrl);
            }
          }),
        );

        cleanups.push(
          await listen<string>("deep-link", (event) => {
            recordDeepLink(event.payload);
          }),
        );
      } catch (error) {
        setDetail(error instanceof Error ? error.message : "Could not subscribe to desktop links");
      }
    }

    void subscribeToDeepLinks();

    return () => {
      disposed = true;
      for (const cleanup of cleanups) {
        cleanup();
      }
    };
  }, []);

  return (
    <main className="shell">
      <section className="status-panel">
        <div>
          <p className="eyebrow">POVerlay Desktop</p>
          <h1>{stateLabel}</h1>
          <p className="status-detail">{detail}</p>
        </div>
        <div className={`status-dot status-dot-${status}`} aria-label={stateLabel} />
      </section>

      <section className="actions" aria-label="Desktop actions">
        <button type="button" onClick={() => void openStudio()}>
          Open Studio
        </button>
        <button type="button" onClick={() => void openOutputFolder()} disabled={!outputDir}>
          Output Folder
        </button>
      </section>

      {actionError ? <p className="action-error">{actionError}</p> : null}

      <section className="details">
        <div>
          <span>Local service</span>
          <strong>{LOCAL_WORKER_BASE}</strong>
        </div>
        <div>
          <span>Worker version</span>
          <strong>{health?.version ?? "Unknown"}</strong>
        </div>
        <div>
          <span>Pairing</span>
          <strong>{health?.paired ? "Paired" : "Waiting"}</strong>
        </div>
        <div>
          <span>Worker session</span>
          <strong>{sessionLabel}</strong>
        </div>
        <div>
          <span>Active render</span>
          <strong>{activeJobLabel}</strong>
        </div>
        <div>
          <span>Last Studio link</span>
          <strong>{lastDeepLink ? "Received" : "None"}</strong>
        </div>
        <div>
          <span>Last worker check</span>
          <strong>{formatSeenAt(lastSeenAt)}</strong>
        </div>
        <div>
          <span>Output folder</span>
          <strong>{outputDir ?? "Unavailable"}</strong>
        </div>
      </section>
    </main>
  );
}
