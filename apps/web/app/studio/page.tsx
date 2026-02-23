"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/components/auth-provider";
import { apiUrl } from "@/lib/api-base";
import { PUBLIC_WEB_CONFIG } from "@/lib/public-config";

type ThemeOption = {
  id: string;
  label: string;
  panel_bg: string;
  panel_bg_alt: string;
  speed_rgb: string;
  accent_rgb: string;
  text_rgb: string;
};

type LayoutStyle = {
  id: string;
  label: string;
  description: string;
};

type ComponentOption = {
  id: string;
  label: string;
  description: string;
  default_enabled: boolean;
};

type RenderProfile = {
  id: string;
  label: string;
  summary: string;
  best_for?: string;
  compatibility?: string;
  is_default?: boolean;
};

type MetaResponse = {
  theme_options?: ThemeOption[];
  layout_styles?: LayoutStyle[];
  default_layout_style?: string;
  component_options?: ComponentOption[];
  default_component_visibility?: Record<string, boolean>;
  map_styles?: string[];
  render_profiles?: RenderProfile[];
  default_render_profile?: string;
};

type LayoutPreviewManifest = {
  images?: Record<string, string>;
};

type VideoState = {
  input_name: string;
  status: string;
  progress: number;
  detail?: string | null;
  error?: string | null;
  output_name?: string | null;
  output_size_bytes?: number | null;
  render_profile_label?: string | null;
  source_resolution?: string | null;
  source_fps?: string | null;
  download_url?: string | null;
  log_name?: string | null;
};

type JobStatus = {
  id: string;
  status: string;
  message: string;
  progress: number;
  videos: VideoState[];
  download_all_url?: string | null;
};

type UploadProgressState = {
  loadedBytes: number;
  totalBytes: number;
  percent: number;
  rateBytesPerSecond: number;
  etaSeconds: number | null;
};

type LocalVideoProbe = {
  key: string;
  name: string;
  size: number;
  lastModified: number;
  width: number | null;
  height: number | null;
  durationSeconds: number | null;
  fps: number | null;
};

type RenderEtaEstimate = {
  totalSeconds: number;
  remainingSeconds: number;
  totalDurationSeconds: number;
  clipCount: number;
  profileUsage: Record<string, number>;
  fallbackAssumptions: string[];
};

type SubmissionStage = "idle" | "uploading" | "queued" | "rendering" | "completed" | "failed";

type PipelineStepState = "pending" | "active" | "done" | "error";
type PipelineStepMetric = { label: string; value: string };

type FormState = {
  overlay_theme: string;
  layout_style: string;
  render_profile: string;
  units_preset: "imperial" | "metric" | "custom";
  speed_units: string;
  gpx_speed_unit: string;
  distance_units: string;
  altitude_units: string;
  temperature_units: string;
  map_style: string;
  gpx_offset_seconds: string;
  fps_mode: "source_exact" | "source_rounded" | "fixed";
  fixed_fps: string;
};

const CONFIGURED_API_BASE = PUBLIC_WEB_CONFIG.apiBase;

const TERMINAL_STATES = new Set(["completed", "completed_with_errors", "failed"]);

const FALLBACK_THEMES: ThemeOption[] = [
  {
    id: "powder-neon",
    label: "Powder Neon",
    panel_bg: "8,18,36,210",
    panel_bg_alt: "16,34,58,195",
    speed_rgb: "66,238,255",
    accent_rgb: "255,171,95",
    text_rgb: "240,247,255",
  },
  {
    id: "summit-ember",
    label: "Summit Ember",
    panel_bg: "25,18,23,210",
    panel_bg_alt: "42,26,28,190",
    speed_rgb: "255,126,86",
    accent_rgb: "255,203,130",
    text_rgb: "255,244,233",
  },
  {
    id: "glacier-steel",
    label: "Glacier Steel",
    panel_bg: "12,24,34,210",
    panel_bg_alt: "19,37,50,194",
    speed_rgb: "128,228,255",
    accent_rgb: "154,199,245",
    text_rgb: "234,244,255",
  },
  {
    id: "forest-sprint",
    label: "Forest Sprint",
    panel_bg: "15,34,30,208",
    panel_bg_alt: "27,52,43,194",
    speed_rgb: "124,255,181",
    accent_rgb: "199,255,152",
    text_rgb: "234,255,244",
  },
  {
    id: "night-sprint",
    label: "Night Sprint",
    panel_bg: "17,12,31,210",
    panel_bg_alt: "32,23,54,194",
    speed_rgb: "214,164,255",
    accent_rgb: "129,223,255",
    text_rgb: "243,236,255",
  },
  {
    id: "sunset-drive",
    label: "Sunset Drive",
    panel_bg: "36,20,14,212",
    panel_bg_alt: "54,31,22,194",
    speed_rgb: "255,176,116",
    accent_rgb: "255,228,146",
    text_rgb: "255,245,234",
  },
];

const FALLBACK_LAYOUTS: LayoutStyle[] = [
  {
    id: "summit-grid",
    label: "Summit Grid",
    description: "Balanced dashboard with maps on the right and stats anchored along the bottom.",
  },
  {
    id: "velocity-rail",
    label: "Velocity Rail",
    description: "Tall left rail for telemetry, leaving a clean right side for terrain and map context.",
  },
  {
    id: "cinematic-lower-third",
    label: "Cinematic Lower Third",
    description: "Film-style lower-third telemetry with layered map modules in the upper corner.",
  },
  {
    id: "apex-split",
    label: "Apex Split",
    description: "Center-focused speed cluster with mirrored top and bottom information zones.",
  },
  {
    id: "moto-dial-bars",
    label: "Moto Dial Bars",
    description: "Gauge-driven speed dial with zone bars and load bars for a motorsport-style cluster.",
  },
  {
    id: "telemetry-hud",
    label: "Telemetry HUD",
    description: "Heads-up telemetry strip with live speed chart and performance zone meters.",
  },
  {
    id: "race-cluster",
    label: "Race Cluster",
    description: "Dual-indicator race dashboard with compass heading and stacked performance bars.",
  },
];

const FALLBACK_COMPONENTS: ComponentOption[] = [
  { id: "time_panel", label: "Time Panel", description: "Date and clock display.", default_enabled: true },
  { id: "speed_panel", label: "Speed Panel", description: "Primary speed readout.", default_enabled: true },
  {
    id: "stats_panel",
    label: "Stats Panel",
    description: "Compact panel for altitude, grade, and distance.",
    default_enabled: true,
  },
  {
    id: "altitude_metric",
    label: "Altitude",
    description: "Altitude metric inside Stats panel.",
    default_enabled: true,
  },
  { id: "grade_metric", label: "Grade", description: "Slope/grade metric inside Stats panel.", default_enabled: true },
  {
    id: "distance_metric",
    label: "Distance",
    description: "Distance traveled metric inside Stats panel.",
    default_enabled: true,
  },
  { id: "gps_panel", label: "GPS Panel", description: "GPS lock panel with status icon.", default_enabled: true },
  {
    id: "gps_coordinates",
    label: "GPS Coordinates",
    description: "Latitude/longitude text lines inside GPS panel.",
    default_enabled: true,
  },
  {
    id: "route_maps",
    label: "Route Maps",
    description: "Moving and full-route map components.",
    default_enabled: true,
  },
];

const FALLBACK_RENDER_PROFILES: RenderProfile[] = [
  {
    id: "auto",
    label: "Auto (Recommended)",
    summary: "Automatically selects the best export codec per clip based on resolution and platform.",
    is_default: true,
  },
  {
    id: "h264-fast",
    label: "H.264 (Fast Draft)",
    summary: "Fastest export profile for quick previews.",
  },
];

const FALLBACK_COMPONENT_VISIBILITY: Record<string, boolean> = {
  time_panel: true,
  speed_panel: true,
  stats_panel: true,
  altitude_metric: true,
  grade_metric: true,
  distance_metric: true,
  gps_panel: true,
  gps_coordinates: true,
  route_maps: true,
};

const FALLBACK_MAP_STYLES = ["osm", "geo-dark-matter", "geo-positron", "geo-positron-blue", "geo-toner"];

const DEFAULT_FORM_STATE: FormState = {
  overlay_theme: "powder-neon",
  layout_style: "summit-grid",
  render_profile: "auto",
  units_preset: "imperial",
  speed_units: "mph",
  gpx_speed_unit: "auto",
  distance_units: "mile",
  altitude_units: "feet",
  temperature_units: "degF",
  map_style: "osm",
  gpx_offset_seconds: "0",
  fps_mode: "source_exact",
  fixed_fps: "30",
};

const ETA_REFERENCE_FPS = 30;
const ETA_DEFAULT_WIDTH = 1920;
const ETA_DEFAULT_HEIGHT = 1080;
const ETA_DEFAULT_DURATION_SECONDS = 30;
const ETA_JOB_OVERHEAD_SECONDS = 14;
const ETA_CLIP_OVERHEAD_SECONDS = 4;
const ETA_MAPS_ENABLED_MULTIPLIER = 1.05;

const ETA_PROFILE_REALTIME_POINTS: Record<string, Array<{ megaPixels: number; xRealtime: number }>> = {
  "h264-fast": [
    { megaPixels: 0.92, xRealtime: 0.839 },
    { megaPixels: 2.07, xRealtime: 1.182 },
    { megaPixels: 4.11, xRealtime: 2.14 },
    { megaPixels: 8.29, xRealtime: 3.518 },
    { megaPixels: 15.87, xRealtime: 10.776 },
  ],
  "h264-source": [
    { megaPixels: 0.92, xRealtime: 0.933 },
    { megaPixels: 2.07, xRealtime: 1.231 },
    { megaPixels: 4.11, xRealtime: 2.241 },
    { megaPixels: 8.29, xRealtime: 3.79 },
    { megaPixels: 15.87, xRealtime: 11.402 },
  ],
  "h264-4k-compat": [
    { megaPixels: 0.92, xRealtime: 0.867 },
    { megaPixels: 2.07, xRealtime: 1.272 },
    { megaPixels: 4.11, xRealtime: 2.516 },
    { megaPixels: 8.29, xRealtime: 3.698 },
    { megaPixels: 15.87, xRealtime: 11.209 },
  ],
  "qt-hevc-balanced": [
    { megaPixels: 0.9, xRealtime: 0.75 },
    { megaPixels: 2.1, xRealtime: 1.25 },
    { megaPixels: 4.1, xRealtime: 2.3 },
    { megaPixels: 8.3, xRealtime: 4.4 },
    { megaPixels: 15.9, xRealtime: 8.1 },
  ],
  "qt-hevc-high": [
    { megaPixels: 0.9, xRealtime: 0.95 },
    { megaPixels: 2.1, xRealtime: 1.6 },
    { megaPixels: 4.1, xRealtime: 3.0 },
    { megaPixels: 8.3, xRealtime: 5.8 },
    { megaPixels: 15.9, xRealtime: 10.6 },
  ],
};

function buildApiUrl(path: string): string {
  return apiUrl(path, CONFIGURED_API_BASE);
}

function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isRecordOfStrings(value: unknown): value is Record<string, string> {
  if (!isObjectRecord(value)) {
    return false;
  }

  for (const entry of Object.values(value)) {
    if (typeof entry !== "string") {
      return false;
    }
  }

  return true;
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

function contentDispositionFilename(value: string | null): string | null {
  if (!value) {
    return null;
  }

  const utf8Match = value.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1].trim().replace(/^"|"$/g, ""));
    } catch {
      return utf8Match[1].trim().replace(/^"|"$/g, "");
    }
  }

  const basicMatch = value.match(/filename=([^;]+)/i);
  if (!basicMatch?.[1]) {
    return null;
  }
  return basicMatch[1].trim().replace(/^"|"$/g, "");
}

function rgbStringToCss(value: string, fallback: string): string {
  const parts = value
    .split(",")
    .map((part) => Number(part.trim()))
    .filter((part) => Number.isFinite(part));

  if (parts.length < 3) {
    return fallback;
  }

  const [r, g, b, alphaRaw] = parts;
  if (!Number.isFinite(alphaRaw)) {
    return `rgb(${r}, ${g}, ${b})`;
  }

  const alpha = Math.max(0, Math.min(1, alphaRaw > 1 ? alphaRaw / 255 : alphaRaw));
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
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

function clampPercent(value?: number | null): number {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(value)));
}

function formatEta(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) {
    return "Calculating...";
  }

  const rounded = Math.round(seconds);
  const hours = Math.floor(rounded / 3600);
  const minutes = Math.floor((rounded % 3600) / 60);
  const secs = rounded % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  }
  return `${secs}s`;
}

function formatRate(bytesPerSecond: number): string {
  if (!Number.isFinite(bytesPerSecond) || bytesPerSecond <= 0) {
    return "--";
  }
  return `${formatBytes(bytesPerSecond)}/s`;
}

function localVideoProbeKey(file: File): string {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

function parseFpsValue(value: string | number | null | undefined): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) && value > 0 ? value : null;
  }

  if (typeof value !== "string") {
    return null;
  }

  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  if (trimmed.includes("/")) {
    const [left, right] = trimmed.split("/", 2);
    const numerator = Number(left);
    const denominator = Number(right);
    if (!Number.isFinite(numerator) || !Number.isFinite(denominator) || denominator === 0) {
      return null;
    }
    const fps = numerator / denominator;
    return Number.isFinite(fps) && fps > 0 ? fps : null;
  }

  const fps = Number(trimmed);
  return Number.isFinite(fps) && fps > 0 ? fps : null;
}

function parseResolutionValue(value: string | null | undefined): { width: number; height: number } | null {
  if (!value) {
    return null;
  }

  const match = value.match(/(\d+)\s*x\s*(\d+)/i);
  if (!match) {
    return null;
  }

  const width = Number(match[1]);
  const height = Number(match[2]);
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return null;
  }

  return { width, height };
}

function estimateAutoProfileForClip(
  width: number,
  height: number,
  availableProfiles: Set<string>,
): string {
  const highResolution = width > 3840 || height > 2160;
  const highResolutionOrder = ["qt-hevc-balanced", "h264-4k-compat", "h264-source", "h264-fast"];
  const standardOrder = ["h264-source", "qt-hevc-balanced", "h264-fast"];
  const candidates = highResolution ? highResolutionOrder : standardOrder;

  for (const profileId of candidates) {
    if (availableProfiles.has(profileId)) {
      return profileId;
    }
  }

  return "h264-source";
}

function interpolateRealtimeFactor(points: Array<{ megaPixels: number; xRealtime: number }>, megaPixels: number): number {
  if (points.length === 0) {
    return 1;
  }
  if (megaPixels <= points[0].megaPixels) {
    return points[0].xRealtime;
  }

  for (let index = 1; index < points.length; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    if (megaPixels <= current.megaPixels) {
      const span = current.megaPixels - previous.megaPixels;
      if (span <= 0) {
        return current.xRealtime;
      }
      const ratio = (megaPixels - previous.megaPixels) / span;
      return previous.xRealtime + ratio * (current.xRealtime - previous.xRealtime);
    }
  }

  const tail = points[points.length - 1];
  const beforeTail = points[points.length - 2] ?? tail;
  const span = Math.max(tail.megaPixels - beforeTail.megaPixels, 0.0001);
  const slope = (tail.xRealtime - beforeTail.xRealtime) / span;
  return Math.max(0.25, tail.xRealtime + (megaPixels - tail.megaPixels) * slope);
}

type ClipEstimateInput = {
  width: number;
  height: number;
  durationSeconds: number;
  sourceFps: number | null;
  profileId: string;
  fixedFps: number | null;
  fpsMode: FormState["fps_mode"];
  mapsEnabled: boolean;
};

function estimateClipRenderSeconds(input: ClipEstimateInput): number {
  const sourceMegaPixels = Math.max((input.width * input.height) / 1_000_000, 0.25);
  const points =
    ETA_PROFILE_REALTIME_POINTS[input.profileId] ??
    ETA_PROFILE_REALTIME_POINTS["h264-source"] ??
    [{ megaPixels: 2.1, xRealtime: 1.3 }];
  const baseXRealtime = interpolateRealtimeFactor(points, sourceMegaPixels);

  const sourceFps = input.sourceFps && input.sourceFps > 0 ? input.sourceFps : ETA_REFERENCE_FPS;
  const targetFps =
    input.fpsMode === "fixed"
      ? Math.max(input.fixedFps && Number.isFinite(input.fixedFps) ? input.fixedFps : ETA_REFERENCE_FPS, 1)
      : input.fpsMode === "source_rounded"
        ? Math.max(Math.round(sourceFps), 1)
        : sourceFps;
  let fpsMultiplier = 1;
  if (input.fpsMode === "source_rounded") {
    fpsMultiplier = 0.91;
  } else if (input.fpsMode === "fixed") {
    if (targetFps <= 30) {
      fpsMultiplier = Math.max(0.45, 0.32 + 0.02 * targetFps);
    } else {
      fpsMultiplier = 0.92 + (targetFps - 30) * 0.028;
    }
  }
  const mapsMultiplier = input.mapsEnabled ? ETA_MAPS_ENABLED_MULTIPLIER : 1;

  return input.durationSeconds * baseXRealtime * fpsMultiplier * mapsMultiplier + ETA_CLIP_OVERHEAD_SECONDS;
}

async function probeLocalVideo(file: File): Promise<LocalVideoProbe> {
  const fallback: LocalVideoProbe = {
    key: localVideoProbeKey(file),
    name: file.name,
    size: file.size,
    lastModified: file.lastModified,
    width: null,
    height: null,
    durationSeconds: null,
    fps: null,
  };

  const objectUrl = URL.createObjectURL(file);
  const element = document.createElement("video");
  element.preload = "metadata";
  element.muted = true;
  element.playsInline = true;
  element.src = objectUrl;

  try {
    await new Promise<void>((resolve, reject) => {
      const onLoaded = () => resolve();
      const onError = () => reject(new Error("Failed to load local video metadata"));
      element.addEventListener("loadedmetadata", onLoaded, { once: true });
      element.addEventListener("error", onError, { once: true });
    });

    const width = element.videoWidth > 0 ? element.videoWidth : null;
    const height = element.videoHeight > 0 ? element.videoHeight : null;
    const durationSeconds = Number.isFinite(element.duration) && element.duration > 0 ? element.duration : null;

    return {
      ...fallback,
      width,
      height,
      durationSeconds,
      fps: null,
    };
  } catch {
    return fallback;
  } finally {
    element.src = "";
    URL.revokeObjectURL(objectUrl);
  }
}

function pipelineStepTone(state: PipelineStepState): string {
  if (state === "done") {
    return "border-emerald-400/60 bg-emerald-500/10 text-emerald-700";
  }
  if (state === "active") {
    return "border-[var(--color-primary)]/60 bg-[var(--color-primary)]/15 text-[var(--color-primary)]";
  }
  if (state === "error") {
    return "border-red-500/50 bg-red-500/10 text-red-700";
  }
  return "border-[var(--color-border)] bg-[var(--color-muted)]/20 text-[var(--color-muted-foreground)]";
}

function pipelineStepStateLabel(state: PipelineStepState): string {
  if (state === "done") {
    return "Done";
  }
  if (state === "active") {
    return "Active";
  }
  if (state === "error") {
    return "Error";
  }
  return "Pending";
}

function clipStatusTone(status: string): string {
  if (status === "completed") {
    return "bg-emerald-500/10 text-emerald-700";
  }
  if (status === "failed") {
    return "bg-red-500/10 text-red-700";
  }
  if (status === "running") {
    return "bg-amber-500/15 text-amber-700";
  }
  return "bg-[var(--color-muted)]/40 text-[var(--color-muted-foreground)]";
}

function pipelineStepProgressTone(state: PipelineStepState): string {
  if (state === "done") {
    return "bg-emerald-500";
  }
  if (state === "active") {
    return "bg-[var(--color-primary)]";
  }
  if (state === "error") {
    return "bg-red-500";
  }
  return "bg-[var(--color-border)]";
}

function mapStyleLabel(value: string): string {
  const presetLabels: Record<string, string> = {
    osm: "OpenStreetMap",
    "geo-dark-matter": "Dark Matter",
    "geo-positron": "Positron",
    "geo-positron-blue": "Positron Blue",
    "geo-toner": "Toner",
  };

  return presetLabels[value] ?? value.replaceAll("-", " ");
}

function getLayoutPreviewSvg(styleId: string): string {
  if (styleId === "velocity-rail") {
    return '<svg viewBox="0 0 220 128" aria-hidden="true"><rect x="4" y="4" width="52" height="120" rx="8" fill="#1f5f8f"/><rect x="66" y="82" width="76" height="42" rx="8" fill="#34b6dd"/><rect x="148" y="8" width="68" height="54" rx="8" fill="#2f8bc8"/><rect x="148" y="70" width="68" height="54" rx="8" fill="#1f5a91"/></svg>';
  }
  if (styleId === "cinematic-lower-third") {
    return '<svg viewBox="0 0 220 128" aria-hidden="true"><rect x="4" y="78" width="212" height="46" rx="8" fill="#2f709f"/><rect x="148" y="8" width="68" height="68" rx="8" fill="#3ca6d4"/><rect x="172" y="34" width="38" height="38" rx="8" fill="#0f3f67"/></svg>';
  }
  if (styleId === "apex-split") {
    return '<svg viewBox="0 0 220 128" aria-hidden="true"><rect x="56" y="6" width="108" height="30" rx="8" fill="#2c7cb3"/><rect x="63" y="76" width="94" height="46" rx="8" fill="#3fb3dd"/><rect x="4" y="8" width="46" height="46" rx="8" fill="#1f5b88"/><rect x="170" y="8" width="46" height="46" rx="8" fill="#1f5b88"/></svg>';
  }
  if (styleId === "moto-dial-bars") {
    return '<svg viewBox="0 0 220 128" aria-hidden="true"><circle cx="62" cy="78" r="42" fill="#2f709f"/><circle cx="62" cy="78" r="27" fill="#113f67"/><rect x="112" y="78" width="104" height="20" rx="6" fill="#3eb3dd"/><rect x="112" y="102" width="104" height="16" rx="6" fill="#2a85be"/><rect x="124" y="8" width="92" height="32" rx="8" fill="#1f5b88"/></svg>';
  }
  if (styleId === "telemetry-hud") {
    return '<svg viewBox="0 0 220 128" aria-hidden="true"><rect x="4" y="74" width="212" height="50" rx="9" fill="#2f709f"/><rect x="82" y="84" width="66" height="22" rx="5" fill="#0f3e64"/><path d="M88 104 L98 92 L108 98 L118 88 L128 96 L138 86" stroke="#58d3ff" stroke-width="3" fill="none"/><rect x="154" y="84" width="56" height="12" rx="5" fill="#40b4dc"/></svg>';
  }
  if (styleId === "race-cluster") {
    return '<svg viewBox="0 0 220 128" aria-hidden="true"><circle cx="110" cy="82" r="38" fill="#2f709f"/><circle cx="110" cy="82" r="22" fill="#113f67"/><rect x="6" y="52" width="52" height="38" rx="8" fill="#1f5b88"/><rect x="162" y="52" width="52" height="38" rx="8" fill="#1f5b88"/><rect x="76" y="6" width="68" height="24" rx="8" fill="#3eb4dd"/></svg>';
  }
  if (styleId === "summit-grid") {
    return '<svg viewBox="0 0 220 128" aria-hidden="true"><rect x="4" y="8" width="70" height="30" rx="8" fill="#1f5b88"/><rect x="4" y="66" width="70" height="58" rx="8" fill="#3eb3dd"/><rect x="80" y="84" width="90" height="40" rx="8" fill="#2a84be"/><rect x="176" y="8" width="40" height="54" rx="8" fill="#2d7cb4"/><rect x="176" y="68" width="40" height="54" rx="8" fill="#1f5e93"/></svg>';
  }

  return '<svg viewBox="0 0 220 128" aria-hidden="true"><rect x="10" y="10" width="200" height="108" rx="10" fill="#2f709f"/></svg>';
}

function makeDefaultVisibility(
  componentOptions: ComponentOption[],
  fromApi?: Record<string, boolean>,
): Record<string, boolean> {
  if (fromApi && Object.keys(fromApi).length > 0) {
    return { ...fromApi };
  }

  const result: Record<string, boolean> = {};
  for (const option of componentOptions) {
    result[option.id] = option.default_enabled;
  }
  return Object.keys(result).length > 0 ? result : { ...FALLBACK_COMPONENT_VISIBILITY };
}

export default function HomePage() {
  const { isEnabled: isAuthEnabled, getIdToken } = useAuth();
  const [formState, setFormState] = useState<FormState>(DEFAULT_FORM_STATE);
  const [themes, setThemes] = useState<ThemeOption[]>(FALLBACK_THEMES);
  const [layoutStyles, setLayoutStyles] = useState<LayoutStyle[]>(FALLBACK_LAYOUTS);
  const [componentOptions, setComponentOptions] = useState<ComponentOption[]>(FALLBACK_COMPONENTS);
  const [componentVisibility, setComponentVisibility] = useState<Record<string, boolean>>(FALLBACK_COMPONENT_VISIBILITY);
  const [mapStyles, setMapStyles] = useState<string[]>(FALLBACK_MAP_STYLES);
  const [renderProfiles, setRenderProfiles] = useState<RenderProfile[]>(FALLBACK_RENDER_PROFILES);

  const [gpxFile, setGpxFile] = useState<File | null>(null);
  const [videoFiles, setVideoFiles] = useState<File[]>([]);
  const [localVideoProbesByKey, setLocalVideoProbesByKey] = useState<Record<string, LocalVideoProbe>>({});
  const [job, setJob] = useState<JobStatus | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submissionStage, setSubmissionStage] = useState<SubmissionStage>("idle");
  const [formError, setFormError] = useState<string | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<UploadProgressState>({
    loadedBytes: 0,
    totalBytes: 0,
    percent: 0,
    rateBytesPerSecond: 0,
    etaSeconds: null,
  });
  const [lastStatusUpdateAt, setLastStatusUpdateAt] = useState<number | null>(null);
  const [layoutPreviewById, setLayoutPreviewById] = useState<Record<string, string>>({});
  const [brokenLayoutPreviews, setBrokenLayoutPreviews] = useState<Record<string, true>>({});

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const uploadRequestRef = useRef<XMLHttpRequest | null>(null);

  async function authHeaders(): Promise<Headers> {
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
  }

  useEffect(() => {
    async function loadMeta() {
      try {
        const response = await fetch(buildApiUrl("/api/meta"), { headers: await authHeaders() });
        if (!response.ok) {
          const errorPayload = await readApiPayload(response);
          throw new Error(extractErrorMessage(errorPayload, "Could not load server metadata"));
        }

        const metaPayload = await readApiPayload(response);
        if (!isObjectRecord(metaPayload)) {
          throw new Error("Could not load server metadata");
        }
        const meta = metaPayload as MetaResponse;
        const nextThemes = meta.theme_options?.length ? meta.theme_options : FALLBACK_THEMES;
        const nextLayouts = meta.layout_styles?.length ? meta.layout_styles : FALLBACK_LAYOUTS;
        const nextComponents = meta.component_options?.length ? meta.component_options : FALLBACK_COMPONENTS;
        const nextProfiles = meta.render_profiles?.length ? meta.render_profiles : FALLBACK_RENDER_PROFILES;
        const nextMapStyles = meta.map_styles?.length ? meta.map_styles : FALLBACK_MAP_STYLES;

        setThemes(nextThemes);
        setLayoutStyles(nextLayouts);
        setComponentOptions(nextComponents);
        setMapStyles(nextMapStyles);
        setRenderProfiles(nextProfiles);

        const defaults = makeDefaultVisibility(nextComponents, meta.default_component_visibility);
        setComponentVisibility(defaults);

        setFormState((prev) => {
          const themeValue = nextThemes.some((item) => item.id === prev.overlay_theme)
            ? prev.overlay_theme
            : nextThemes[0]?.id ?? "powder-neon";
          const layoutValue = nextLayouts.some((item) => item.id === prev.layout_style)
            ? prev.layout_style
            : meta.default_layout_style ?? nextLayouts[0]?.id ?? "summit-grid";
          const profileValue = nextProfiles.some((item) => item.id === prev.render_profile)
            ? prev.render_profile
            : meta.default_render_profile ?? nextProfiles[0]?.id ?? "auto";
          const mapValue = nextMapStyles.includes(prev.map_style) ? prev.map_style : nextMapStyles[0] ?? "osm";

          return {
            ...prev,
            overlay_theme: themeValue,
            layout_style: layoutValue,
            render_profile: profileValue,
            map_style: mapValue,
          };
        });
      } catch {
        setThemes(FALLBACK_THEMES);
        setLayoutStyles(FALLBACK_LAYOUTS);
        setComponentOptions(FALLBACK_COMPONENTS);
        setComponentVisibility(FALLBACK_COMPONENT_VISIBILITY);
        setMapStyles(FALLBACK_MAP_STYLES);
        setRenderProfiles(FALLBACK_RENDER_PROFILES);
      }
    }

    void loadMeta();
  }, [getIdToken, isAuthEnabled]);

  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
      }
      if (uploadRequestRef.current) {
        uploadRequestRef.current.abort();
      }
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    if (videoFiles.length === 0) {
      setLocalVideoProbesByKey({});
      return () => {
        cancelled = true;
      };
    }

    async function loadLocalVideoProbes() {
      const probes = await Promise.all(videoFiles.map((file) => probeLocalVideo(file)));
      if (cancelled) {
        return;
      }
      const byKey: Record<string, LocalVideoProbe> = {};
      for (const probe of probes) {
        byKey[probe.key] = probe;
      }
      setLocalVideoProbesByKey(byKey);
    }

    void loadLocalVideoProbes();

    return () => {
      cancelled = true;
    };
  }, [videoFiles]);

  useEffect(() => {
    let ignore = false;

    async function loadLayoutPreviewManifest() {
      try {
        const response = await fetch("/layout-previews/manifest.json");
        const payload = await readApiPayload(response);
        if (!response.ok || !isObjectRecord(payload)) {
          throw new Error("Could not load layout preview manifest");
        }

        const manifest = payload as LayoutPreviewManifest;
        if (!isRecordOfStrings(manifest.images)) {
          throw new Error("Invalid layout preview manifest");
        }

        if (!ignore) {
          setLayoutPreviewById(manifest.images);
          setBrokenLayoutPreviews({});
        }
      } catch {
        if (!ignore) {
          setLayoutPreviewById({});
          setBrokenLayoutPreviews({});
        }
      }
    }

    void loadLayoutPreviewManifest();

    return () => {
      ignore = true;
    };
  }, []);

  const selectedTheme = useMemo(() => {
    return themes.find((theme) => theme.id === formState.overlay_theme) ?? themes[0];
  }, [formState.overlay_theme, themes]);

  const selectedProfile = useMemo(() => {
    return renderProfiles.find((profile) => profile.id === formState.render_profile) ?? null;
  }, [formState.render_profile, renderProfiles]);

  const selectedLayout = useMemo(() => {
    return layoutStyles.find((layout) => layout.id === formState.layout_style) ?? null;
  }, [formState.layout_style, layoutStyles]);

  const statsPanelEnabled = componentVisibility.stats_panel ?? true;
  const gpsPanelEnabled = componentVisibility.gps_panel ?? true;
  const mapsEnabled = componentVisibility.route_maps ?? true;
  const componentGroups = useMemo(() => {
    const coreIds = new Set(["time_panel", "speed_panel", "stats_panel", "gps_panel", "route_maps"]);
    const metricIds = new Set(["altitude_metric", "grade_metric", "distance_metric", "gps_coordinates"]);
    const core: ComponentOption[] = [];
    const metrics: ComponentOption[] = [];
    const advanced: ComponentOption[] = [];

    for (const option of componentOptions) {
      if (coreIds.has(option.id)) {
        core.push(option);
      } else if (metricIds.has(option.id)) {
        metrics.push(option);
      } else {
        advanced.push(option);
      }
    }

    return { core, metrics, advanced };
  }, [componentOptions]);
  const selectedUploadBytes = useMemo(
    () => (gpxFile?.size ?? 0) + videoFiles.reduce((sum, video) => sum + video.size, 0),
    [gpxFile, videoFiles],
  );
  const renderEtaEstimate = useMemo((): RenderEtaEstimate | null => {
    if (videoFiles.length === 0) {
      return null;
    }

    const availableProfiles = new Set(renderProfiles.map((profile) => profile.id));
    const fixedFpsValue = parseFpsValue(formState.fixed_fps);
    const localProbeByName = new Map<string, LocalVideoProbe>();
    for (const file of videoFiles) {
      const probe = localVideoProbesByKey[localVideoProbeKey(file)];
      if (probe) {
        localProbeByName.set(file.name, probe);
      }
    }

    const clipNames = (job?.videos ?? []).length > 0 ? (job?.videos ?? []).map((video) => video.input_name) : videoFiles.map((file) => file.name);
    const fallbackAssumptions: string[] = [];
    let totalDurationSeconds = 0;
    let totalRenderSeconds = ETA_JOB_OVERHEAD_SECONDS;
    const profileUsage: Record<string, number> = {};

    for (const clipName of clipNames) {
      const jobVideo = (job?.videos ?? []).find((video) => video.input_name === clipName);
      const probe = localProbeByName.get(clipName);

      const parsedResolution = parseResolutionValue(jobVideo?.source_resolution ?? null);
      const width = parsedResolution?.width ?? probe?.width ?? ETA_DEFAULT_WIDTH;
      const height = parsedResolution?.height ?? probe?.height ?? ETA_DEFAULT_HEIGHT;
      if (!parsedResolution && !probe?.width) {
        fallbackAssumptions.push("resolution");
      }

      const durationSeconds = Math.max(probe?.durationSeconds ?? ETA_DEFAULT_DURATION_SECONDS, 1);
      if (!probe?.durationSeconds) {
        fallbackAssumptions.push("duration");
      }

      const sourceFps = parseFpsValue(jobVideo?.source_fps ?? null) ?? probe?.fps ?? null;
      if (sourceFps === null && formState.fps_mode !== "fixed") {
        fallbackAssumptions.push("fps");
      }

      const selectedProfileId =
        formState.render_profile === "auto"
          ? estimateAutoProfileForClip(width, height, availableProfiles)
          : formState.render_profile;
      profileUsage[selectedProfileId] = (profileUsage[selectedProfileId] ?? 0) + 1;

      totalDurationSeconds += durationSeconds;
      totalRenderSeconds += estimateClipRenderSeconds({
        width,
        height,
        durationSeconds,
        sourceFps,
        profileId: selectedProfileId,
        fixedFps: fixedFpsValue,
        fpsMode: formState.fps_mode,
        mapsEnabled,
      });
    }

    const currentProgress = submissionStage === "rendering" ? clampPercent(job?.progress ?? 0) / 100 : submissionStage === "completed" ? 1 : 0;
    const remainingSeconds = Math.max(totalRenderSeconds * (1 - currentProgress), 0);

    return {
      totalSeconds: totalRenderSeconds,
      remainingSeconds,
      totalDurationSeconds,
      clipCount: clipNames.length,
      profileUsage,
      fallbackAssumptions: Array.from(new Set(fallbackAssumptions)),
    };
  }, [
    formState.fixed_fps,
    formState.fps_mode,
    formState.render_profile,
    job?.progress,
    job?.videos,
    localVideoProbesByKey,
    mapsEnabled,
    renderProfiles,
    submissionStage,
    videoFiles,
  ]);
  const videoStatusSummary = useMemo(() => {
    const summary = {
      total: job?.videos.length ?? 0,
      queued: 0,
      running: 0,
      completed: 0,
      failed: 0,
    };

    for (const video of job?.videos ?? []) {
      if (video.status === "queued") {
        summary.queued += 1;
      } else if (video.status === "running") {
        summary.running += 1;
      } else if (video.status === "completed") {
        summary.completed += 1;
      } else if (video.status === "failed") {
        summary.failed += 1;
      }
    }

    return summary;
  }, [job?.videos]);
  const overallProgressPercent = useMemo(() => {
    if (submissionStage === "uploading") {
      return clampPercent(uploadProgress.percent);
    }
    return clampPercent(job?.progress ?? 0);
  }, [job?.progress, submissionStage, uploadProgress.percent]);
  const runningClipNames = useMemo(
    () => (job?.videos ?? []).filter((video) => video.status === "running").map((video) => video.input_name),
    [job?.videos],
  );
  const totalOutputBytes = useMemo(
    () => (job?.videos ?? []).reduce((sum, video) => sum + (video.output_size_bytes ?? 0), 0),
    [job?.videos],
  );
  const stepCards = useMemo(() => {
    const uploadState: PipelineStepState =
      submissionStage === "failed" ? "error" : submissionStage === "uploading" ? "active" : activeJobId ? "done" : "pending";
    const queueState: PipelineStepState =
      submissionStage === "failed"
        ? "error"
        : submissionStage === "queued"
          ? "active"
          : submissionStage === "rendering" || submissionStage === "completed"
            ? "done"
            : "pending";
    const renderState: PipelineStepState =
      submissionStage === "failed"
        ? "error"
        : submissionStage === "rendering"
          ? "active"
          : submissionStage === "completed"
            ? "done"
            : "pending";
    const finalizeState: PipelineStepState =
      submissionStage === "failed" ? "error" : submissionStage === "completed" ? "done" : "pending";

    return [
      {
        key: "upload",
        label: "Upload",
        shortLabel: "1. Upload",
        detail:
          submissionStage === "uploading"
            ? `Uploading ${formatBytes(uploadProgress.loadedBytes)} of ${formatBytes(uploadProgress.totalBytes || selectedUploadBytes)}`
            : activeJobId
              ? "Payload accepted by API"
              : "Waiting for files",
        state: uploadState,
        progress:
          uploadState === "done" ? 100 : uploadState === "active" ? clampPercent(uploadProgress.percent) : uploadState === "error" ? 100 : 0,
        metrics: [
          { label: "Files", value: `${videoFiles.length + (gpxFile ? 1 : 0)}` },
          { label: "Payload", value: formatBytes(selectedUploadBytes) || "0 B" },
          {
            label: "Transferred",
            value: `${formatBytes(uploadProgress.loadedBytes)} / ${formatBytes(uploadProgress.totalBytes || selectedUploadBytes)}`,
          },
          { label: "Speed", value: formatRate(uploadProgress.rateBytesPerSecond) },
          { label: "ETA", value: submissionStage === "uploading" ? formatEta(uploadProgress.etaSeconds) : "--" },
        ] satisfies PipelineStepMetric[],
      },
      {
        key: "queue",
        label: "Queue",
        shortLabel: "2. Queue",
        detail: activeJobId ? `Job ${activeJobId.slice(0, 8)}... submitted` : "Job not submitted",
        state: queueState,
        progress: queueState === "done" ? 100 : queueState === "active" ? 45 : queueState === "error" ? 100 : 0,
        metrics: [
          { label: "Job ID", value: activeJobId ? `${activeJobId.slice(0, 8)}...` : "--" },
          { label: "Queue state", value: job?.status ?? "waiting" },
          { label: "Queued clips", value: `${videoStatusSummary.queued}` },
          { label: "Polling", value: activeJobId ? "Every 2s" : "--" },
        ] satisfies PipelineStepMetric[],
      },
      {
        key: "render",
        label: "Render",
        shortLabel: "3. Render",
        detail:
          submissionStage === "rendering"
            ? `${videoStatusSummary.running} clip${videoStatusSummary.running === 1 ? "" : "s"} processing`
            : "Waiting for renderer",
        state: renderState,
        progress:
          renderState === "done"
            ? 100
            : renderState === "active"
              ? clampPercent(job?.progress ?? 0)
              : renderState === "error"
                ? 100
                : 0,
        metrics: [
          { label: "Overall", value: `${clampPercent(job?.progress ?? 0)}%` },
          { label: "Running", value: `${videoStatusSummary.running}` },
          { label: "Completed", value: `${videoStatusSummary.completed}` },
          { label: "Failed", value: `${videoStatusSummary.failed}` },
          { label: "Est. total", value: renderEtaEstimate ? `~${formatEta(renderEtaEstimate.totalSeconds)}` : "--" },
          {
            label: "Est. remaining",
            value:
              submissionStage === "rendering" && renderEtaEstimate
                ? `~${formatEta(renderEtaEstimate.remainingSeconds)}`
                : renderEtaEstimate
                  ? `~${formatEta(renderEtaEstimate.totalSeconds)}`
                  : "--",
          },
          { label: "Active clip", value: runningClipNames[0] ?? "--" },
        ] satisfies PipelineStepMetric[],
      },
      {
        key: "finalize",
        label: "Finalize",
        shortLabel: "4. Finalize",
        detail:
          submissionStage === "completed"
            ? "Outputs ready for download"
            : submissionStage === "failed"
              ? "Pipeline reported an error"
              : "Pending completion",
        state: finalizeState,
        progress: finalizeState === "done" ? 100 : finalizeState === "error" ? 100 : 0,
        metrics: [
          {
            label: "Downloadable clips",
            value: `${(job?.videos ?? []).filter((video) => Boolean(video.download_url)).length}`,
          },
          { label: "Archive", value: job?.download_all_url ? "Ready" : "Pending" },
          { label: "Output size", value: totalOutputBytes > 0 ? formatBytes(totalOutputBytes) : "--" },
          { label: "Last update", value: lastStatusUpdateAt ? new Date(lastStatusUpdateAt).toLocaleTimeString() : "--" },
        ] satisfies PipelineStepMetric[],
      },
    ] as const;
  }, [
    activeJobId,
    gpxFile,
    job?.download_all_url,
    job?.progress,
    job?.status,
    job?.videos,
    lastStatusUpdateAt,
    renderEtaEstimate,
    runningClipNames,
    selectedUploadBytes,
    submissionStage,
    totalOutputBytes,
    uploadProgress.etaSeconds,
    uploadProgress.loadedBytes,
    uploadProgress.percent,
    uploadProgress.rateBytesPerSecond,
    uploadProgress.totalBytes,
    videoFiles.length,
    videoStatusSummary.completed,
    videoStatusSummary.failed,
    videoStatusSummary.queued,
    videoStatusSummary.running,
  ]);
  const activeStep = useMemo(() => {
    return stepCards.find((step) => step.state === "active") ?? stepCards.find((step) => step.state === "error") ?? stepCards[0];
  }, [stepCards]);
  const primaryStatusLabel = useMemo(() => {
    if (submissionStage === "uploading") {
      return "Uploading files";
    }
    if (submissionStage === "queued") {
      return "Queued for rendering";
    }
    if (submissionStage === "rendering") {
      return "Rendering in progress";
    }
    if (submissionStage === "completed") {
      return "Render complete";
    }
    if (submissionStage === "failed") {
      return "Render failed";
    }
    return "Ready to start";
  }, [submissionStage]);
  const submitButtonLabel = useMemo(() => {
    if (!isSubmitting) {
      return "Render overlays";
    }
    if (submissionStage === "uploading") {
      return `Uploading ${overallProgressPercent}%`;
    }
    if (submissionStage === "queued") {
      return "Queued...";
    }
    if (submissionStage === "rendering") {
      return "Rendering...";
    }
    return "Processing...";
  }, [isSubmitting, overallProgressPercent, submissionStage]);

  async function pollJob(jobId: string): Promise<void> {
    try {
      const response = await fetch(buildApiUrl(`/api/jobs/${jobId}`), { headers: await authHeaders() });
      const payload = await readApiPayload(response);
      if (!response.ok) {
        throw new Error(extractErrorMessage(payload, `Could not fetch job ${jobId}`));
      }

      if (!isObjectRecord(payload)) {
        throw new Error(`Unexpected response while fetching job ${jobId}`);
      }

      const jobPayload = payload as JobStatus;
      setJob(jobPayload);
      setStatusError(null);
      setLastStatusUpdateAt(Date.now());

      if (jobPayload.status === "queued") {
        setSubmissionStage("queued");
      } else if (jobPayload.status === "running") {
        setSubmissionStage("rendering");
      } else if (jobPayload.status === "failed") {
        setSubmissionStage("failed");
      } else if (jobPayload.status === "completed" || jobPayload.status === "completed_with_errors") {
        setSubmissionStage("completed");
      }

      if (TERMINAL_STATES.has(jobPayload.status)) {
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
        setIsSubmitting(false);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Polling failed";
      setStatusError(message);
      setIsSubmitting(false);

      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }
  }

  async function createJobWithProgress(payload: FormData): Promise<string> {
    const headers = await authHeaders();

    return await new Promise<string>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      uploadRequestRef.current = xhr;
      const startedAt = performance.now();
      let latestLoadedBytes = 0;
      let latestTotalBytes = 0;
      let latestRateBytesPerSecond = 0;

      xhr.open("POST", buildApiUrl("/api/jobs"));
      headers.forEach((value, key) => {
        xhr.setRequestHeader(key, value);
      });

      xhr.upload.onprogress = (event) => {
        const elapsedSeconds = Math.max((performance.now() - startedAt) / 1000, 0.001);
        const loadedBytes = Number(event.loaded) || 0;
        const totalBytes = event.lengthComputable && Number(event.total) > 0 ? Number(event.total) : Math.max(latestTotalBytes, loadedBytes);
        const percent = totalBytes > 0 ? (loadedBytes / totalBytes) * 100 : 0;
        const rateBytesPerSecond = loadedBytes / elapsedSeconds;
        const etaSeconds =
          totalBytes > loadedBytes && rateBytesPerSecond > 0 ? (totalBytes - loadedBytes) / rateBytesPerSecond : null;

        latestLoadedBytes = loadedBytes;
        latestTotalBytes = totalBytes;
        latestRateBytesPerSecond = rateBytesPerSecond;

        setUploadProgress({
          loadedBytes,
          totalBytes,
          percent: clampPercent(percent),
          rateBytesPerSecond,
          etaSeconds,
        });
      };

      xhr.onerror = () => {
        uploadRequestRef.current = null;
        reject(new Error("Upload failed due to a network error."));
      };

      xhr.onabort = () => {
        uploadRequestRef.current = null;
        reject(new Error("Upload was canceled before completion."));
      };

      xhr.onload = () => {
        uploadRequestRef.current = null;
        const raw = xhr.responseText ?? "";
        let payloadFromServer: unknown = null;
        if (raw) {
          try {
            payloadFromServer = JSON.parse(raw) as unknown;
          } catch {
            payloadFromServer = raw;
          }
        }

        if (xhr.status < 200 || xhr.status >= 300) {
          reject(new Error(extractErrorMessage(payloadFromServer, "Failed to create render job")));
          return;
        }

        if (!isObjectRecord(payloadFromServer) || typeof payloadFromServer.job_id !== "string" || !payloadFromServer.job_id) {
          reject(new Error("Invalid response from API while creating job"));
          return;
        }

        const resolvedTotal = Math.max(latestTotalBytes, latestLoadedBytes);
        setUploadProgress({
          loadedBytes: resolvedTotal,
          totalBytes: resolvedTotal,
          percent: 100,
          rateBytesPerSecond: latestRateBytesPerSecond,
          etaSeconds: 0,
        });
        resolve(payloadFromServer.job_id);
      };

      xhr.send(payload);
    });
  }

  async function downloadAuthenticated(path: string, fallbackFilename: string): Promise<void> {
    try {
      setStatusError(null);
      const response = await fetch(buildApiUrl(path), { headers: await authHeaders() });
      if (!response.ok) {
        const errorPayload = await readApiPayload(response);
        throw new Error(extractErrorMessage(errorPayload, "Download failed"));
      }

      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const headerName = contentDispositionFilename(response.headers.get("content-disposition"));

      link.href = objectUrl;
      link.download = headerName || fallbackFilename;
      document.body.appendChild(link);
      link.click();
      link.remove();

      URL.revokeObjectURL(objectUrl);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Download failed";
      setStatusError(message);
    }
  }

  function applyUnitsPreset(preset: FormState["units_preset"]) {
    if (preset === "metric") {
      setFormState((prev) => ({
        ...prev,
        units_preset: preset,
        speed_units: "kph",
        distance_units: "km",
        altitude_units: "metre",
        temperature_units: "degC",
      }));
      return;
    }

    if (preset === "imperial") {
      setFormState((prev) => ({
        ...prev,
        units_preset: preset,
        speed_units: "mph",
        distance_units: "mile",
        altitude_units: "feet",
        temperature_units: "degF",
      }));
      return;
    }

    setFormState((prev) => ({ ...prev, units_preset: "custom" }));
  }

  function toggleComponentVisibility(componentId: string): void {
    setComponentVisibility((prev) => ({
      ...prev,
      [componentId]: !prev[componentId],
    }));
  }

  function handleUnitChange(field: "speed_units" | "distance_units" | "altitude_units" | "temperature_units", value: string) {
    setFormState((prev) => ({
      ...prev,
      units_preset: "custom",
      [field]: value,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!gpxFile) {
      setFormError("Select a GPX file to continue.");
      return;
    }

    if (videoFiles.length === 0) {
      setFormError("Select at least one video file to continue.");
      return;
    }

    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }

    setFormError(null);
    setStatusError(null);
    setIsSubmitting(true);
    setSubmissionStage("uploading");
    setJob(null);
    setActiveJobId(null);
    setLastStatusUpdateAt(null);

    const estimatedUploadBytes = (gpxFile?.size ?? 0) + videoFiles.reduce((sum, video) => sum + video.size, 0);
    setUploadProgress({
      loadedBytes: 0,
      totalBytes: estimatedUploadBytes,
      percent: 0,
      rateBytesPerSecond: 0,
      etaSeconds: null,
    });

    const payload = new FormData();
    payload.append("gpx", gpxFile);
    for (const video of videoFiles) {
      payload.append("videos", video);
    }

    payload.append("overlay_theme", formState.overlay_theme);
    payload.append("layout_style", formState.layout_style);
    payload.append("render_profile", formState.render_profile);
    payload.append("map_style", formState.map_style);
    payload.append("speed_units", formState.speed_units);
    payload.append("gpx_speed_unit", formState.gpx_speed_unit);
    payload.append("distance_units", formState.distance_units);
    payload.append("altitude_units", formState.altitude_units);
    payload.append("temperature_units", formState.temperature_units);
    payload.append("gpx_offset_seconds", formState.gpx_offset_seconds);
    payload.append("fps_mode", formState.fps_mode);
    payload.append("fixed_fps", formState.fixed_fps);

    payload.append("component_visibility", JSON.stringify(componentVisibility));
    payload.append("include_maps", mapsEnabled ? "true" : "false");

    try {
      const createdJobId = await createJobWithProgress(payload);
      setActiveJobId(createdJobId);
      setSubmissionStage("queued");
      await pollJob(createdJobId);

      pollRef.current = setInterval(() => {
        void pollJob(createdJobId);
      }, 2000);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to create render job";
      setFormError(message);
      setSubmissionStage("failed");
      setIsSubmitting(false);
    }
  }

  const panelColor = selectedTheme ? rgbStringToCss(selectedTheme.panel_bg, "rgba(18, 33, 56, 0.85)") : "rgba(18, 33, 56, 0.85)";
  const panelAltColor = selectedTheme
    ? rgbStringToCss(selectedTheme.panel_bg_alt, "rgba(30, 54, 86, 0.76)")
    : "rgba(30, 54, 86, 0.76)";
  const speedColor = selectedTheme ? rgbStringToCss(selectedTheme.speed_rgb, "rgb(67, 231, 255)") : "rgb(67, 231, 255)";
  const accentColor = selectedTheme ? rgbStringToCss(selectedTheme.accent_rgb, "rgb(255, 179, 112)") : "rgb(255, 179, 112)";
  const textColor = selectedTheme ? rgbStringToCss(selectedTheme.text_rgb, "rgb(238, 248, 255)") : "rgb(238, 248, 255)";

  return (
    <main className="min-h-screen pb-12">
      <header className="border-b border-[var(--color-border)] bg-[var(--color-card)]/70 backdrop-blur-sm">
        <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-primary)]">POVerlay Studio</p>
          <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">GoPro telemetry pipeline</h1>
              <p className="mt-2 max-w-3xl text-sm text-[var(--color-muted-foreground)] sm:text-base">
                Upload one GPX track plus one or more clips, choose your look, and render timeline-ready overlays.
              </p>
            </div>
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-background)]/80 px-4 py-3 text-sm">
              {gpxFile ? `GPX: ${gpxFile.name}` : "No GPX selected"} • {videoFiles.length} clip
              {videoFiles.length === 1 ? "" : "s"} • {selectedUploadBytes > 0 ? formatBytes(selectedUploadBytes) : "0 B"}
            </div>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-8 sm:px-6 lg:grid-cols-[minmax(0,1fr)_390px] lg:px-8">
        <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5 shadow-sm sm:p-6">
          <form onSubmit={handleSubmit} className="space-y-6">
            <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-background)]/55 p-5">
              <h2 className="text-lg font-semibold">1. Upload assets</h2>
              <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">Use one GPX file and one or more clips.</p>
              <div className="mt-4 grid gap-5 sm:grid-cols-2">
                <label className="block" htmlFor="gpx">
                  <span className="mb-2 block text-sm font-medium">GPX file (Slopes export)</span>
                  <input
                    id="gpx"
                    type="file"
                    accept=".gpx"
                    required
                    onChange={(event) => setGpxFile(event.target.files?.[0] ?? null)}
                    className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm file:mr-4 file:rounded-md file:border-0 file:bg-[var(--color-primary)] file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-[var(--color-primary)]/90"
                  />
                </label>

                <label className="block" htmlFor="videos">
                  <span className="mb-2 block text-sm font-medium">GoPro clips</span>
                  <input
                    id="videos"
                    type="file"
                    accept="video/*,.mp4,.mov"
                    multiple
                    required
                    onChange={(event) => setVideoFiles(Array.from(event.target.files ?? []))}
                    className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm file:mr-4 file:rounded-md file:border-0 file:bg-[var(--color-primary)] file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-[var(--color-primary)]/90"
                  />
                </label>
              </div>
              <div className="mt-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] px-4 py-3">
                <p className="text-sm font-medium">
                  Payload estimate:{" "}
                  <span className="text-[var(--color-primary)]">
                    {selectedUploadBytes > 0 ? formatBytes(selectedUploadBytes) : "No files selected"}
                  </span>
                </p>
                <p className="mt-1 text-sm font-medium">
                  Render ETA:{" "}
                  <span className="text-[var(--color-primary)]">
                    {renderEtaEstimate ? `~${formatEta(renderEtaEstimate.totalSeconds)}` : "Select clips to estimate"}
                  </span>
                </p>
                {renderEtaEstimate && renderEtaEstimate.fallbackAssumptions.length > 0 && (
                  <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">
                    Using fallback assumptions for {renderEtaEstimate.fallbackAssumptions.join(", ")}.
                  </p>
                )}
                <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">
                  Keep this tab open through upload completion. Rendering continues server-side after upload.
                </p>
              </div>
            </section>

            <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-background)]/55 p-5">
              <h2 className="text-lg font-semibold">2. Look and output</h2>
              <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">Set style, layout, and render profile.</p>

              <div className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                <label className="block" htmlFor="overlay_theme">
                  <span className="mb-2 block text-sm font-medium">Overlay theme</span>
                  <select
                    id="overlay_theme"
                    value={formState.overlay_theme}
                    onChange={(event) => setFormState((prev) => ({ ...prev, overlay_theme: event.target.value }))}
                    className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20"
                  >
                    {themes.map((theme) => (
                      <option key={theme.id} value={theme.id}>
                        {theme.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="block" htmlFor="layout_style">
                  <span className="mb-2 block text-sm font-medium">Layout style</span>
                  <select
                    id="layout_style"
                    value={formState.layout_style}
                    onChange={(event) => setFormState((prev) => ({ ...prev, layout_style: event.target.value }))}
                    className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20"
                  >
                    {layoutStyles.map((layoutStyle) => (
                      <option key={layoutStyle.id} value={layoutStyle.id}>
                        {layoutStyle.label}
                      </option>
                    ))}
                  </select>
                  {selectedLayout?.description && (
                    <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">{selectedLayout.description}</p>
                  )}
                </label>

                <label className="block" htmlFor="render_profile">
                  <span className="mb-2 block text-sm font-medium">Export codec</span>
                  <select
                    id="render_profile"
                    value={formState.render_profile}
                    onChange={(event) => setFormState((prev) => ({ ...prev, render_profile: event.target.value }))}
                    className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20"
                  >
                    {renderProfiles.map((profile) => (
                      <option key={profile.id} value={profile.id}>
                        {profile.label}
                      </option>
                    ))}
                  </select>
                  {selectedProfile && (
                    <p className="mt-1 text-xs text-[var(--color-muted-foreground)]">
                      {selectedProfile.summary}
                      {selectedProfile.best_for ? ` Best for: ${selectedProfile.best_for}` : ""}
                    </p>
                  )}
                </label>

                <label className="block" htmlFor="units_preset">
                  <span className="mb-2 block text-sm font-medium">Units preset</span>
                  <select
                    id="units_preset"
                    value={formState.units_preset}
                    onChange={(event) => applyUnitsPreset(event.target.value as FormState["units_preset"])}
                    className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20"
                  >
                    <option value="imperial">Imperial (mph / mile / feet / degF)</option>
                    <option value="metric">Metric (kph / km / metre / degC)</option>
                    <option value="custom">Custom</option>
                  </select>
                </label>

                <label className="block" htmlFor="fps_mode">
                  <span className="mb-2 block text-sm font-medium">FPS strategy</span>
                  <select
                    id="fps_mode"
                    value={formState.fps_mode}
                    onChange={(event) =>
                      setFormState((prev) => ({ ...prev, fps_mode: event.target.value as FormState["fps_mode"] }))
                    }
                    className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20"
                  >
                    <option value="source_exact">Match source (exact)</option>
                    <option value="source_rounded">Match source (rounded int)</option>
                    <option value="fixed">Fixed FPS</option>
                  </select>
                </label>

                <label className="block" htmlFor="fixed_fps">
                  <span className="mb-2 block text-sm font-medium">Fixed FPS value</span>
                  <input
                    id="fixed_fps"
                    type="number"
                    min="1"
                    step="0.01"
                    value={formState.fixed_fps}
                    disabled={formState.fps_mode !== "fixed"}
                    onChange={(event) => setFormState((prev) => ({ ...prev, fixed_fps: event.target.value }))}
                    className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 disabled:cursor-not-allowed disabled:opacity-50"
                  />
                </label>
              </div>

              <div className="mt-5 grid gap-5 xl:grid-cols-[340px_minmax(0,1fr)]">
                <article className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
                  <h3 className="mb-3 text-sm font-semibold">Theme preview</h3>
                  <div className="mb-3 flex flex-wrap gap-2">
                    <span style={{ background: panelColor }} className="rounded-md px-2.5 py-1 text-[10px] font-semibold text-white">Panel</span>
                    <span style={{ background: panelAltColor }} className="rounded-md px-2.5 py-1 text-[10px] font-semibold text-white">Panel Alt</span>
                    <span style={{ background: speedColor }} className="rounded-md px-2.5 py-1 text-[10px] font-semibold text-white">Speed</span>
                    <span style={{ background: accentColor }} className="rounded-md px-2.5 py-1 text-[10px] font-semibold text-white">Accent</span>
                  </div>
                  <div
                    className="rounded-xl border p-4"
                    style={{
                      background: `linear-gradient(138deg, ${panelColor}, ${panelAltColor})`,
                      borderColor: "rgba(168, 213, 255, 0.35)",
                    }}
                  >
                    <div className="mb-3">
                      <small style={{ color: accentColor }} className="block text-[10px] font-semibold uppercase tracking-wide">SPEED</small>
                      <strong style={{ color: speedColor }} className="text-4xl font-bold">62</strong>
                    </div>
                    <div style={{ color: textColor }} className="flex gap-3 text-[10px] font-medium">
                      <span>ALT 2100</span>
                      <span>GRADE 8.2%</span>
                      <span>DIST 4.6</span>
                    </div>
                  </div>
                </article>

                <article className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
                  <h3 className="mb-3 text-sm font-semibold">Layout previews</h3>
                  <div className="grid grid-cols-2 gap-2 lg:grid-cols-3">
                    {layoutStyles.map((layoutStyle) => {
                      const previewSource = layoutPreviewById[layoutStyle.id];
                      const normalizedSource = previewSource
                        ? previewSource.startsWith("/")
                          ? previewSource
                          : `/${previewSource}`
                        : null;
                      const shouldUseImage = Boolean(normalizedSource && !brokenLayoutPreviews[layoutStyle.id]);

                      return (
                        <button
                          key={layoutStyle.id}
                          type="button"
                          className={`rounded-lg border p-2 text-left transition-all hover:border-[var(--color-primary)] ${
                            layoutStyle.id === formState.layout_style
                              ? "border-[var(--color-primary)] bg-[var(--color-primary)]/5"
                              : "border-[var(--color-border)] bg-[var(--color-background)]"
                          }`}
                          onClick={() => setFormState((prev) => ({ ...prev, layout_style: layoutStyle.id }))}
                        >
                          {shouldUseImage ? (
                            <div className="mb-2 overflow-hidden rounded">
                              <img
                                src={normalizedSource ?? ""}
                                alt={`${layoutStyle.label} preview`}
                                loading="lazy"
                                className="h-auto w-full"
                                onError={() =>
                                  setBrokenLayoutPreviews((prev) => (
                                    prev[layoutStyle.id]
                                      ? prev
                                      : {
                                          ...prev,
                                          [layoutStyle.id]: true,
                                        }
                                  ))
                                }
                              />
                            </div>
                          ) : (
                            <div
                              className="mb-2 overflow-hidden rounded"
                              dangerouslySetInnerHTML={{ __html: getLayoutPreviewSvg(layoutStyle.id) }}
                            />
                          )}
                          <strong className="block text-[11px] font-semibold">{layoutStyle.label}</strong>
                        </button>
                      );
                    })}
                  </div>
                </article>
              </div>
            </section>

            <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-background)]/55 p-5">
              <h2 className="text-lg font-semibold">3. Overlay components</h2>
              <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">
                Core controls stay visible here. Less-used controls are tucked into advanced options.
              </p>

              <div className="mt-4 grid gap-5 lg:grid-cols-2">
                <div>
                  <h3 className="mb-2 text-sm font-semibold">Core panels</h3>
                  <div className="space-y-2.5">
                    {componentGroups.core.map((option) => {
                      const checked = componentVisibility[option.id] ?? option.default_enabled;
                      return (
                        <label
                          key={option.id}
                          className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-all ${
                            checked
                              ? "border-[var(--color-primary)] bg-[var(--color-primary)]/5"
                              : "border-[var(--color-border)] bg-[var(--color-card)] hover:border-[var(--color-primary)]/50"
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleComponentVisibility(option.id)}
                            className="mt-0.5 h-4 w-4 rounded border-[var(--color-border)] text-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary)]/20"
                          />
                          <div className="flex-1">
                            <span className="block text-sm font-medium">{option.label}</span>
                            <small className="block text-xs text-[var(--color-muted-foreground)]">{option.description}</small>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <h3 className="mb-2 text-sm font-semibold">Metric details</h3>
                  <div className="space-y-2.5">
                    {componentGroups.metrics.map((option) => {
                      const checked = componentVisibility[option.id] ?? option.default_enabled;
                      const isDisabled =
                        (option.id === "altitude_metric" || option.id === "grade_metric" || option.id === "distance_metric")
                          ? !statsPanelEnabled
                          : option.id === "gps_coordinates"
                            ? !gpsPanelEnabled
                            : false;
                      return (
                        <label
                          key={option.id}
                          className={`flex items-start gap-3 rounded-lg border p-3 transition-all ${
                            isDisabled
                              ? "cursor-not-allowed border-[var(--color-border)] bg-[var(--color-card)] opacity-55"
                              : checked
                                ? "cursor-pointer border-[var(--color-primary)] bg-[var(--color-primary)]/5"
                                : "cursor-pointer border-[var(--color-border)] bg-[var(--color-card)] hover:border-[var(--color-primary)]/50"
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={isDisabled}
                            onChange={() => toggleComponentVisibility(option.id)}
                            className="mt-0.5 h-4 w-4 rounded border-[var(--color-border)] text-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary)]/20 disabled:cursor-not-allowed"
                          />
                          <div className="flex-1">
                            <span className="block text-sm font-medium">{option.label}</span>
                            <small className="block text-xs text-[var(--color-muted-foreground)]">{option.description}</small>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                </div>
              </div>

              {componentGroups.advanced.length > 0 && (
                <details className="mt-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)]">
                  <summary className="cursor-pointer px-4 py-3 text-sm font-semibold">More component options</summary>
                  <div className="grid gap-3 border-t border-[var(--color-border)] p-4 sm:grid-cols-2">
                    {componentGroups.advanced.map((option) => {
                      const checked = componentVisibility[option.id] ?? option.default_enabled;
                      return (
                        <label
                          key={option.id}
                          className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-all ${
                            checked
                              ? "border-[var(--color-primary)] bg-[var(--color-primary)]/5"
                              : "border-[var(--color-border)] bg-[var(--color-background)]"
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleComponentVisibility(option.id)}
                            className="mt-0.5 h-4 w-4 rounded border-[var(--color-border)] text-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary)]/20"
                          />
                          <div className="flex-1">
                            <span className="block text-sm font-medium">{option.label}</span>
                            <small className="block text-xs text-[var(--color-muted-foreground)]">{option.description}</small>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                </details>
              )}
            </section>

            <details className="group rounded-2xl border border-[var(--color-border)] bg-[var(--color-background)]/55">
              <summary className="cursor-pointer px-5 py-4 text-sm font-semibold">Advanced render controls</summary>
              <div className="grid gap-5 border-t border-[var(--color-border)] p-5 sm:grid-cols-2 lg:grid-cols-3">
                <label className="block" htmlFor="map_style">
                  <span className="mb-2 block text-sm font-medium">Map style</span>
                  <select
                    id="map_style"
                    value={formState.map_style}
                    disabled={!mapsEnabled}
                    onChange={(event) => setFormState((prev) => ({ ...prev, map_style: event.target.value }))}
                    className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {mapStyles.map((style) => (
                      <option key={style} value={style}>
                        {mapStyleLabel(style)}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="block" htmlFor="speed_units">
                  <span className="mb-2 block text-sm font-medium">Speed units</span>
                  <select
                    id="speed_units"
                    value={formState.speed_units}
                    disabled={formState.units_preset !== "custom"}
                    onChange={(event) => handleUnitChange("speed_units", event.target.value)}
                    className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <option value="kph">kph</option>
                    <option value="mph">mph</option>
                    <option value="mps">m/s</option>
                    <option value="knots">knots</option>
                  </select>
                </label>

                <label className="block" htmlFor="gpx_speed_unit">
                  <span className="mb-2 block text-sm font-medium">GPX speed source units</span>
                  <select
                    id="gpx_speed_unit"
                    value={formState.gpx_speed_unit}
                    onChange={(event) => setFormState((prev) => ({ ...prev, gpx_speed_unit: event.target.value }))}
                    className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20"
                  >
                    <option value="auto">Auto-detect (recommended)</option>
                    <option value="mph">mph</option>
                    <option value="kph">kph</option>
                    <option value="mps">m/s</option>
                    <option value="knots">knots</option>
                  </select>
                </label>

                <label className="block" htmlFor="distance_units">
                  <span className="mb-2 block text-sm font-medium">Distance units</span>
                  <select
                    id="distance_units"
                    value={formState.distance_units}
                    disabled={formState.units_preset !== "custom"}
                    onChange={(event) => handleUnitChange("distance_units", event.target.value)}
                    className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <option value="km">km</option>
                    <option value="mile">mile</option>
                    <option value="nmi">nautical mile</option>
                    <option value="meter">meter</option>
                  </select>
                </label>

                <label className="block" htmlFor="altitude_units">
                  <span className="mb-2 block text-sm font-medium">Altitude units</span>
                  <select
                    id="altitude_units"
                    value={formState.altitude_units}
                    disabled={formState.units_preset !== "custom"}
                    onChange={(event) => handleUnitChange("altitude_units", event.target.value)}
                    className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <option value="metre">metre</option>
                    <option value="meter">meter</option>
                    <option value="feet">feet</option>
                  </select>
                </label>

                <label className="block" htmlFor="temperature_units">
                  <span className="mb-2 block text-sm font-medium">Temperature units</span>
                  <select
                    id="temperature_units"
                    value={formState.temperature_units}
                    disabled={formState.units_preset !== "custom"}
                    onChange={(event) => handleUnitChange("temperature_units", event.target.value)}
                    className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <option value="degC">degC</option>
                    <option value="degF">degF</option>
                    <option value="kelvin">kelvin</option>
                  </select>
                </label>

                <label className="block" htmlFor="gpx_offset_seconds">
                  <span className="mb-2 block text-sm font-medium">GPX time offset (seconds)</span>
                  <input
                    id="gpx_offset_seconds"
                    type="number"
                    step="0.1"
                    value={formState.gpx_offset_seconds}
                    onChange={(event) => setFormState((prev) => ({ ...prev, gpx_offset_seconds: event.target.value }))}
                    className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20"
                  />
                </label>
              </div>
            </details>

            {formError && (
              <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-4 text-sm text-red-600 dark:text-red-400">
                {formError}
              </div>
            )}

            <div className="flex flex-col gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-background)]/70 p-4 sm:flex-row sm:items-center sm:justify-between">
              <button
                type="submit"
                disabled={isSubmitting}
                className="rounded-xl bg-[var(--color-primary)] px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-[var(--color-primary)]/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submitButtonLabel}
              </button>
              <p className="text-sm text-[var(--color-muted-foreground)]">
                Preset {formState.units_preset} • {mapStyleLabel(formState.map_style)} •{" "}
                {formState.fps_mode === "fixed" ? `Fixed ${formState.fixed_fps} fps` : "Source FPS"}
              </p>
            </div>
          </form>
        </section>

        <aside className="space-y-6 lg:sticky lg:top-20 lg:self-start">
          <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-6 shadow-sm">
            <div className="mb-5 rounded-2xl border border-[var(--color-border)] bg-gradient-to-br from-[var(--color-primary)]/12 via-[var(--color-card)] to-cyan-500/10 p-4">
              <div className="mb-3 flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-xl font-semibold">Pipeline status</h2>
                  <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">
                    {job?.message ??
                      (submissionStage === "uploading"
                        ? "Uploading files to server..."
                        : activeJobId
                          ? "Waiting for server updates..."
                          : "Run a render to start the pipeline.")}
                  </p>
                </div>
                <span className="rounded-full bg-[var(--color-primary)]/15 px-3 py-1 text-xs font-semibold text-[var(--color-primary)]">
                  {primaryStatusLabel}
                </span>
              </div>

              <div className="mb-3 overflow-hidden rounded-full bg-[var(--color-muted)]/70">
                <div
                  className={`h-2 rounded-full transition-all duration-300 ${
                    submissionStage === "failed"
                      ? "bg-red-500"
                      : submissionStage === "completed"
                        ? "bg-emerald-500"
                        : "bg-gradient-to-r from-cyan-500 to-blue-500"
                  }`}
                  style={{ width: `${overallProgressPercent}%` }}
                />
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)]/70 px-3 py-2">
                  <p className="text-[var(--color-muted-foreground)]">Overall progress</p>
                  <p className="text-sm font-semibold">{overallProgressPercent}%</p>
                </div>
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)]/70 px-3 py-2">
                  <p className="text-[var(--color-muted-foreground)]">Current focus</p>
                  <p className="text-sm font-semibold">{activeStep.shortLabel}</p>
                </div>
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)]/70 px-3 py-2">
                  <p className="text-[var(--color-muted-foreground)]">Job</p>
                  <p className="text-sm font-semibold">{activeJobId ? `${activeJobId.slice(0, 8)}...` : "--"}</p>
                </div>
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)]/70 px-3 py-2">
                  <p className="text-[var(--color-muted-foreground)]">Clips</p>
                  <p className="text-sm font-semibold">
                    {videoStatusSummary.completed}/{videoStatusSummary.total} complete
                  </p>
                </div>
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)]/70 px-3 py-2">
                  <p className="text-[var(--color-muted-foreground)]">Est. render time</p>
                  <p className="text-sm font-semibold">
                    {renderEtaEstimate
                      ? submissionStage === "rendering"
                        ? `~${formatEta(renderEtaEstimate.remainingSeconds)} left`
                        : `~${formatEta(renderEtaEstimate.totalSeconds)}`
                      : "--"}
                  </p>
                </div>
              </div>
            </div>

            <div className="mb-5 grid gap-3">
              {stepCards.map((step) => (
                <article key={step.key} className={`rounded-xl border p-4 transition-colors ${pipelineStepTone(step.state)}`}>
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <h3 className="text-sm font-semibold">{step.shortLabel}</h3>
                    <span className="rounded-full border border-current px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
                      {pipelineStepStateLabel(step.state)}
                    </span>
                  </div>

                  <p className="mb-3 text-xs">{step.detail}</p>

                  <div className="mb-3 overflow-hidden rounded-full bg-[var(--color-background)]/70">
                    <div
                      className={`h-1.5 rounded-full transition-all duration-300 ${pipelineStepProgressTone(step.state)}`}
                      style={{ width: `${clampPercent(step.progress)}%` }}
                    />
                  </div>

                  <dl className="grid grid-cols-2 gap-2 text-xs">
                    {step.metrics.map((metric) => (
                      <div key={`${step.key}-${metric.label}`} className="rounded-md border border-current/20 bg-[var(--color-background)]/60 px-2 py-1.5">
                        <dt className="text-[10px] uppercase tracking-wide opacity-80">{metric.label}</dt>
                        <dd className="mt-0.5 font-semibold">{metric.value}</dd>
                      </div>
                    ))}
                  </dl>
                </article>
              ))}
            </div>

            {statusError && (
              <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-3 text-sm text-red-600 dark:text-red-400">
                {statusError}
              </div>
            )}

            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold">Clip breakdown</h3>
              <p className="text-xs text-[var(--color-muted-foreground)]">
                Running {videoStatusSummary.running} • Failed {videoStatusSummary.failed}
              </p>
            </div>

            <ul className="space-y-3">
              {(job?.videos ?? []).map((video) => {
                const clipDetails: string[] = [];
                if (video.error) {
                  clipDetails.push(video.error);
                } else if (video.detail) {
                  clipDetails.push(video.detail);
                }

                if (video.source_resolution || video.source_fps) {
                  clipDetails.push(
                    [video.source_resolution, video.source_fps ? `${video.source_fps} fps` : ""].filter(Boolean).join(" | "),
                  );
                }

                if (video.render_profile_label) {
                  clipDetails.push(`Export: ${video.render_profile_label}`);
                }

                if (video.output_size_bytes) {
                  clipDetails.push(formatBytes(video.output_size_bytes));
                }

                return (
                  <li key={video.input_name} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-4">
                    <div className="mb-2 flex items-start justify-between gap-2">
                      <strong className="text-sm font-semibold">{video.input_name}</strong>
                      <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${clipStatusTone(video.status)}`}>
                        {video.status} {clampPercent(video.progress)}%
                      </span>
                    </div>

                    <div className="mb-3 overflow-hidden rounded-full bg-[var(--color-muted)]">
                      <div
                        className={`h-1.5 rounded-full transition-all duration-300 ${
                          video.status === "failed"
                            ? "bg-red-500"
                            : video.status === "completed"
                              ? "bg-emerald-500"
                              : "bg-[var(--color-primary)]"
                        }`}
                        style={{ width: `${clampPercent(video.progress)}%` }}
                      />
                    </div>

                    {clipDetails.length > 0 && (
                      <p className="mb-3 text-xs text-[var(--color-muted-foreground)]">{clipDetails.join(" • ")}</p>
                    )}

                    <div className="flex flex-wrap gap-2">
                      {video.download_url && (
                        <button
                          type="button"
                          onClick={() =>
                            void downloadAuthenticated(
                              video.download_url ?? "",
                              video.output_name ?? `${video.input_name.replace(/\.[^.]+$/, "")}-overlay.mp4`,
                            )
                          }
                          className="rounded-md bg-[var(--color-primary)] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[var(--color-primary)]/90"
                        >
                          Download video
                        </button>
                      )}

                      {video.log_name && job?.id && (
                        <button
                          type="button"
                          onClick={() =>
                            void downloadAuthenticated(
                              `/api/jobs/${job.id}/log/${video.log_name}`,
                              `${video.log_name}`,
                            )
                          }
                          className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-xs font-medium transition-colors hover:bg-[var(--color-muted)]/30"
                        >
                          Renderer log
                        </button>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>

            {job && (job.videos?.length ?? 0) === 0 && (
              <p className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-xs text-[var(--color-muted-foreground)]">
                Job created. Clip-level status will appear once processing starts.
              </p>
            )}

            {job?.download_all_url && (
              <button
                type="button"
                className="mt-4 block w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] px-4 py-3 text-center text-sm font-semibold transition-colors hover:bg-[var(--color-muted)]/30"
                onClick={() => void downloadAuthenticated(job.download_all_url ?? "", `overlay-renders-${job.id}.zip`)}
              >
                Download all outputs (.zip)
              </button>
            )}
          </section>
        </aside>
      </div>

      <footer className="mt-12 border-t border-[var(--color-border)]/60 py-8">
        <div className="mx-auto flex max-w-7xl items-center justify-center px-4 sm:px-6">
          <jb-credit data-variant="prominent"></jb-credit>
        </div>
      </footer>
    </main>
  );
}
