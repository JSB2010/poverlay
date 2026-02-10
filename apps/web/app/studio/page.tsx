"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

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

type VideoState = {
  input_name: string;
  status: string;
  progress: number;
  detail?: string | null;
  error?: string | null;
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

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

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
  const [formState, setFormState] = useState<FormState>(DEFAULT_FORM_STATE);
  const [themes, setThemes] = useState<ThemeOption[]>(FALLBACK_THEMES);
  const [layoutStyles, setLayoutStyles] = useState<LayoutStyle[]>(FALLBACK_LAYOUTS);
  const [componentOptions, setComponentOptions] = useState<ComponentOption[]>(FALLBACK_COMPONENTS);
  const [componentVisibility, setComponentVisibility] = useState<Record<string, boolean>>(FALLBACK_COMPONENT_VISIBILITY);
  const [mapStyles, setMapStyles] = useState<string[]>(FALLBACK_MAP_STYLES);
  const [renderProfiles, setRenderProfiles] = useState<RenderProfile[]>(FALLBACK_RENDER_PROFILES);

  const [gpxFile, setGpxFile] = useState<File | null>(null);
  const [videoFiles, setVideoFiles] = useState<File[]>([]);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    async function loadMeta() {
      try {
        const response = await fetch(`${API_BASE}/api/meta`);
        if (!response.ok) {
          throw new Error("Could not load server metadata");
        }

        const meta = (await response.json()) as MetaResponse;
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
  }, []);

  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
      }
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

  async function pollJob(jobId: string): Promise<void> {
    try {
      const response = await fetch(`${API_BASE}/api/jobs/${jobId}`);
      if (!response.ok) {
        throw new Error(`Could not fetch job ${jobId}`);
      }

      const payload = (await response.json()) as JobStatus;
      setJob(payload);
      setStatusError(null);

      if (TERMINAL_STATES.has(payload.status)) {
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
    setJob(null);

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
      const response = await fetch(`${API_BASE}/api/jobs`, {
        method: "POST",
        body: payload,
      });

      if (!response.ok) {
        const errorPayload = (await response.json()) as { detail?: string };
        throw new Error(errorPayload.detail ?? "Failed to create render job");
      }

      const created = (await response.json()) as { job_id: string };
      setActiveJobId(created.job_id);
      await pollJob(created.job_id);

      pollRef.current = setInterval(() => {
        void pollJob(created.job_id);
      }, 2000);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to create render job";
      setFormError(message);
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
      <header className="border-b border-[var(--color-border)] bg-[var(--color-card)]/60 backdrop-blur-sm">
        <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="mb-2 text-sm font-medium text-[var(--color-primary)]">POVerlay Studio</p>
              <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">GoPro Telemetry Overlay Studio</h1>
              <p className="mt-2 max-w-2xl text-base text-[var(--color-muted-foreground)]">
                Professional render pipeline for GPX-aligned overlays. Upload one ride track and one or more clips,
                preview themes/layouts, and export timeline-ready videos.
              </p>
            </div>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-8 sm:px-6 lg:grid-cols-[1fr_400px] lg:px-8">
        <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-6 shadow-sm">
          <form onSubmit={handleSubmit} className="space-y-8">
            <div>
              <h2 className="text-xl font-semibold">Upload</h2>
              <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">Start with one GPX file and one or more clips.</p>
            </div>

            <div className="grid gap-6 sm:grid-cols-2">
              <label className="block" htmlFor="gpx">
                <span className="mb-2 block text-sm font-medium">GPX file (Slopes export)</span>
                <input
                  id="gpx"
                  type="file"
                  accept=".gpx"
                  required
                  onChange={(event) => setGpxFile(event.target.files?.[0] ?? null)}
                  className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm file:mr-4 file:rounded-md file:border-0 file:bg-[var(--color-primary)] file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-[var(--color-primary)]/90"
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
                  className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm file:mr-4 file:rounded-md file:border-0 file:bg-[var(--color-primary)] file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-[var(--color-primary)]/90"
                />
              </label>
            </div>

            <div>
              <h2 className="text-xl font-semibold">Render Settings</h2>
              <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">Main controls for look, layout, and export behavior.</p>
            </div>

            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              <label className="block" htmlFor="overlay_theme">
                <span className="mb-2 block text-sm font-medium">Overlay theme</span>
                <select
                  id="overlay_theme"
                  value={formState.overlay_theme}
                  onChange={(event) => setFormState((prev) => ({ ...prev, overlay_theme: event.target.value }))}
                  className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20"
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
                  className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20"
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
                  className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20"
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
                  className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20"
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
                  className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20"
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
                  className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 disabled:cursor-not-allowed disabled:opacity-50"
                />
              </label>

              <label className="block" htmlFor="gpx_offset_seconds">
                <span className="mb-2 block text-sm font-medium">GPX time offset (seconds)</span>
                <input
                  id="gpx_offset_seconds"
                  type="number"
                  step="0.1"
                  value={formState.gpx_offset_seconds}
                  onChange={(event) => setFormState((prev) => ({ ...prev, gpx_offset_seconds: event.target.value }))}
                  className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20"
                />
              </label>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <article className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-6">
                <h3 className="mb-4 text-lg font-semibold">Theme Preview</h3>
                <div className="mb-4 flex flex-wrap gap-2">
                  <span style={{ background: panelColor }} className="rounded-md px-3 py-1.5 text-xs font-medium text-white">Panel</span>
                  <span style={{ background: panelAltColor }} className="rounded-md px-3 py-1.5 text-xs font-medium text-white">Panel Alt</span>
                  <span style={{ background: speedColor }} className="rounded-md px-3 py-1.5 text-xs font-medium text-white">Speed</span>
                  <span style={{ background: accentColor }} className="rounded-md px-3 py-1.5 text-xs font-medium text-white">Accent</span>
                  <span style={{ background: textColor, color: "#102742" }} className="rounded-md px-3 py-1.5 text-xs font-medium">Text</span>
                </div>

                <div
                  className="rounded-xl border p-4"
                  style={{
                    background: `linear-gradient(138deg, ${panelColor}, ${panelAltColor})`,
                    borderColor: "rgba(168, 213, 255, 0.35)",
                  }}
                >
                  <div className="mb-3">
                    <small style={{ color: accentColor }} className="block text-xs font-medium uppercase tracking-wide">SPEED</small>
                    <strong style={{ color: speedColor }} className="text-4xl font-bold">62</strong>
                  </div>
                  <div style={{ color: textColor }} className="flex gap-4 text-xs font-medium">
                    <span>ALT 2100</span>
                    <span>GRADE 8.2%</span>
                    <span>DIST 4.6</span>
                  </div>
                </div>
              </article>

              <article className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-6">
                <h3 className="mb-4 text-lg font-semibold">Layout Previews</h3>
                <div className="grid grid-cols-2 gap-3">
                  {layoutStyles.map((layoutStyle) => (
                    <button
                      key={layoutStyle.id}
                      type="button"
                      className={`group rounded-lg border p-3 text-left transition-all hover:border-[var(--color-primary)] hover:shadow-md ${
                        layoutStyle.id === formState.layout_style
                          ? "border-[var(--color-primary)] bg-[var(--color-primary)]/5 shadow-sm"
                          : "border-[var(--color-border)] bg-[var(--color-background)]"
                      }`}
                      onClick={() => setFormState((prev) => ({ ...prev, layout_style: layoutStyle.id }))}
                    >
                      <div
                        className="mb-2 overflow-hidden rounded"
                        dangerouslySetInnerHTML={{ __html: getLayoutPreviewSvg(layoutStyle.id) }}
                      />
                      <div>
                        <strong className="block text-xs font-semibold">{layoutStyle.label}</strong>
                        <small className="block text-[10px] text-[var(--color-muted-foreground)]">{layoutStyle.description}</small>
                      </div>
                    </button>
                  ))}
                </div>
              </article>
            </div>

            <div>
              <h2 className="text-xl font-semibold">Overlay Components</h2>
              <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">Choose exactly what appears in the rendered overlay.</p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {componentOptions.map((option) => {
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
                    className={`flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition-all ${
                      isDisabled
                        ? "cursor-not-allowed opacity-50"
                        : checked
                          ? "border-[var(--color-primary)] bg-[var(--color-primary)]/5"
                          : "border-[var(--color-border)] hover:border-[var(--color-primary)]/50"
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

            <details className="group rounded-xl border border-[var(--color-border)] bg-[var(--color-card)]">
              <summary className="cursor-pointer px-6 py-4 font-semibold transition-colors hover:bg-[var(--color-muted)]/30">
                Advanced Settings
              </summary>
              <div className="border-t border-[var(--color-border)] p-6">
                <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                  <label className="block" htmlFor="map_style">
                    <span className="mb-2 block text-sm font-medium">Map style</span>
                    <select
                      id="map_style"
                      value={formState.map_style}
                      disabled={!mapsEnabled}
                      onChange={(event) => setFormState((prev) => ({ ...prev, map_style: event.target.value }))}
                      className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 disabled:cursor-not-allowed disabled:opacity-50"
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
                      className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 disabled:cursor-not-allowed disabled:opacity-50"
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
                      className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20"
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
                      className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 disabled:cursor-not-allowed disabled:opacity-50"
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
                      className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 disabled:cursor-not-allowed disabled:opacity-50"
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
                      className="block w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <option value="degC">degC</option>
                      <option value="degF">degF</option>
                      <option value="kelvin">kelvin</option>
                    </select>
                  </label>
                </div>
              </div>
            </details>

            {formError && (
              <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-4 text-sm text-red-600 dark:text-red-400">
                {formError}
              </div>
            )}

            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <button
                type="submit"
                disabled={isSubmitting}
                className="rounded-xl bg-[var(--color-primary)] px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-[var(--color-primary)]/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isSubmitting ? "Rendering..." : "Render overlays"}
              </button>
              <p className="text-sm text-[var(--color-muted-foreground)]">
                {gpxFile ? `GPX: ${gpxFile.name}` : "No GPX selected"} • {videoFiles.length} video
                {videoFiles.length === 1 ? "" : "s"}
              </p>
            </div>
          </form>
        </section>

        <aside className="space-y-6">
          <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-6 shadow-sm">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold">Render Status</h2>
                <p className="mt-1 text-sm text-[var(--color-muted-foreground)]">
                  {job?.message ?? (activeJobId ? "Waiting for updates..." : "Run a render to view progress.")}
                </p>
              </div>
              {job?.status && (
                <span className="rounded-full bg-[var(--color-primary)]/10 px-3 py-1 text-xs font-medium text-[var(--color-primary)]">
                  {job.status.replaceAll("_", " ")}
                </span>
              )}
            </div>

            <div className="mb-4 overflow-hidden rounded-full bg-[var(--color-muted)]">
              <div
                className="h-2 rounded-full bg-[var(--color-primary)] transition-all duration-300"
                style={{ width: `${Math.max(0, Math.min(100, job?.progress ?? 0))}%` }}
              />
            </div>

            {statusError && (
              <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-3 text-sm text-red-600 dark:text-red-400">
                {statusError}
              </div>
            )}

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
                      <span className="rounded-full bg-[var(--color-primary)]/10 px-2 py-0.5 text-xs font-medium text-[var(--color-primary)]">
                        {video.status} {video.progress ?? 0}%
                      </span>
                    </div>

                    {clipDetails.length > 0 && (
                      <p className="mb-3 text-xs text-[var(--color-muted-foreground)]">{clipDetails.join(" • ")}</p>
                    )}

                    <div className="flex flex-wrap gap-2">
                      {video.download_url && (
                        <a
                          href={`${API_BASE}${video.download_url}`}
                          className="rounded-md bg-[var(--color-primary)] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[var(--color-primary)]/90"
                        >
                          Download video
                        </a>
                      )}

                      {video.log_name && job?.id && (
                        <a
                          href={`${API_BASE}/api/jobs/${job.id}/log/${video.log_name}`}
                          className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-xs font-medium transition-colors hover:bg-[var(--color-muted)]/30"
                        >
                          Renderer log
                        </a>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>

            {job?.download_all_url && (
              <a
                className="block rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] px-4 py-3 text-center text-sm font-semibold transition-colors hover:bg-[var(--color-muted)]/30"
                href={`${API_BASE}${job.download_all_url}`}
              >
                Download all outputs (.zip)
              </a>
            )}
          </section>
        </aside>
      </div>

      {/* Footer */}
      <footer className="border-t border-[var(--color-border)]/60 py-8 mt-12">
        <div className="mx-auto flex max-w-7xl items-center justify-center px-4 sm:px-6">
          <jb-credit data-variant="prominent"></jb-credit>
        </div>
      </footer>
    </main>
  );
}
