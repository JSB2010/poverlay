const form = document.getElementById("render-form");
const submitBtn = document.getElementById("submit-btn");
const jobPanel = document.getElementById("job-panel");
const jobMessage = document.getElementById("job-message");
const progressBar = document.getElementById("progress-bar");
const videoList = document.getElementById("video-status-list");
const downloadActions = document.getElementById("download-actions");
const fpsModeSelect = document.getElementById("fps_mode");
const fixedFpsField = document.getElementById("fixed-fps-field");
const renderProfileSelect = document.getElementById("render_profile");
const renderProfileHelp = document.getElementById("render-profile-help");
const overlayThemeSelect = document.getElementById("overlay_theme");
const layoutStyleSelect = document.getElementById("layout_style");
const layoutStyleHelp = document.getElementById("layout-style-help");
const themePreviewRoot = document.getElementById("theme-preview");
const layoutPreviewGrid = document.getElementById("layout-preview-grid");
const componentOptionsRoot = document.getElementById("component-options");
const mapStyleSelect = document.getElementById("map_style");
const unitsPresetSelect = document.getElementById("units_preset");
const speedUnitsSelect = document.getElementById("speed_units");
const distanceUnitsSelect = document.getElementById("distance_units");
const altitudeUnitsSelect = document.getElementById("altitude_units");
const temperatureUnitsSelect = document.getElementById("temperature_units");

let activeJobId = null;
let pollHandle = null;
const renderProfilesById = new Map();
const layoutStylesById = new Map();
const themesById = new Map();

const terminalStates = new Set(["completed", "completed_with_errors", "failed"]);

const fallbackThemes = [
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

const fallbackLayoutStyles = [
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

const fallbackComponents = [
  { id: "time_panel", label: "Time Panel", description: "Date and clock display.", default_enabled: true },
  { id: "speed_panel", label: "Speed Panel", description: "Primary speed readout.", default_enabled: true },
  {
    id: "stats_panel",
    label: "Stats Panel",
    description: "Compact panel for altitude, grade, and distance.",
    default_enabled: true,
  },
  { id: "altitude_metric", label: "Altitude", description: "Altitude metric inside Stats panel.", default_enabled: true },
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

function rgbStringToCss(value, fallback = "rgba(39, 67, 92, 0.3)") {
  if (typeof value !== "string") return fallback;

  const parts = value
    .split(",")
    .map((part) => Number(part.trim()))
    .filter((part) => Number.isFinite(part));

  if (parts.length < 3) return fallback;

  const [r, g, b, alphaRaw] = parts;
  if (!Number.isFinite(alphaRaw)) {
    return `rgb(${r}, ${g}, ${b})`;
  }
  const alpha = Math.max(0, Math.min(1, alphaRaw > 1 ? alphaRaw / 255 : alphaRaw));
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function updateRenderProfileHelp() {
  const profile = renderProfilesById.get(renderProfileSelect.value);
  if (!profile) {
    renderProfileHelp.textContent = "";
    return;
  }

  const parts = [profile.summary];
  if (profile.best_for) parts.push(`Best for: ${profile.best_for}`);
  if (profile.compatibility) parts.push(`Compatibility: ${profile.compatibility}`);
  renderProfileHelp.textContent = parts.join(" ");
}

function syncLayoutPreviewSelection() {
  const selectedStyle = layoutStyleSelect.value;
  layoutPreviewGrid.querySelectorAll(".layout-preview-card").forEach((card) => {
    card.classList.toggle("selected", card.dataset.layoutStyleId === selectedStyle);
  });
}

function updateLayoutStyleHelp() {
  const style = layoutStylesById.get(layoutStyleSelect.value);
  layoutStyleHelp.textContent = style?.description || "";
  syncLayoutPreviewSelection();
}

function updateThemePreview() {
  if (!themePreviewRoot) return;

  const theme = themesById.get(overlayThemeSelect.value);
  if (!theme) {
    themePreviewRoot.innerHTML = "";
    return;
  }

  const panel = rgbStringToCss(theme.panel_bg, "rgba(26, 52, 76, 0.85)");
  const panelAlt = rgbStringToCss(theme.panel_bg_alt, "rgba(34, 64, 91, 0.75)");
  const speed = rgbStringToCss(theme.speed_rgb, "rgb(94, 223, 255)");
  const accent = rgbStringToCss(theme.accent_rgb, "rgb(255, 197, 132)");
  const text = rgbStringToCss(theme.text_rgb, "rgb(238, 246, 255)");

  themePreviewRoot.innerHTML = `
    <div class="theme-preview-card">
      <div class="theme-preview-swatches">
        <span style="background:${panel}">Panel</span>
        <span style="background:${panelAlt}">Panel Alt</span>
        <span style="background:${speed}">Speed</span>
        <span style="background:${accent}">Accent</span>
        <span style="background:${text}; color:#11253a;">Text</span>
      </div>
      <div class="theme-preview-mini" style="--tp-bg:${panel}; --tp-bg-alt:${panelAlt}; --tp-speed:${speed}; --tp-accent:${accent}; --tp-text:${text};">
        <div class="mini-speed">
          <small>SPEED</small>
          <strong>62</strong>
        </div>
        <div class="mini-stats">
          <span>ALT 2100</span>
          <span>GRADE 8.2%</span>
          <span>DIST 4.6</span>
        </div>
      </div>
    </div>
  `;
}

function getLayoutPreviewSvg(styleId) {
  if (styleId === "velocity-rail") {
    return `<svg viewBox="0 0 220 128" aria-hidden="true"><rect x="4" y="4" width="52" height="120" rx="8" fill="#295f8f"/><rect x="66" y="82" width="76" height="42" rx="8" fill="#41b1df"/><rect x="148" y="8" width="68" height="54" rx="8" fill="#2d89c6"/><rect x="148" y="70" width="68" height="54" rx="8" fill="#1e5f93"/></svg>`;
  }
  if (styleId === "cinematic-lower-third") {
    return `<svg viewBox="0 0 220 128" aria-hidden="true"><rect x="4" y="78" width="212" height="46" rx="8" fill="#2f6f9f"/><rect x="148" y="8" width="68" height="68" rx="8" fill="#42a3d4"/><rect x="172" y="34" width="38" height="38" rx="8" fill="#113f67"/></svg>`;
  }
  if (styleId === "apex-split") {
    return `<svg viewBox="0 0 220 128" aria-hidden="true"><rect x="56" y="6" width="108" height="30" rx="8" fill="#2d7db4"/><rect x="63" y="76" width="94" height="46" rx="8" fill="#43b2dd"/><rect x="4" y="8" width="46" height="46" rx="8" fill="#1f5b88"/><rect x="170" y="8" width="46" height="46" rx="8" fill="#1f5b88"/></svg>`;
  }
  if (styleId === "moto-dial-bars") {
    return `<svg viewBox="0 0 220 128" aria-hidden="true"><circle cx="62" cy="78" r="42" fill="#2f6f9f"/><circle cx="62" cy="78" r="27" fill="#113f67"/><rect x="112" y="78" width="104" height="20" rx="6" fill="#43b2dd"/><rect x="112" y="102" width="104" height="16" rx="6" fill="#2a84be"/><rect x="124" y="8" width="92" height="32" rx="8" fill="#1f5b88"/></svg>`;
  }
  if (styleId === "telemetry-hud") {
    return `<svg viewBox="0 0 220 128" aria-hidden="true"><rect x="4" y="74" width="212" height="50" rx="9" fill="#2f6f9f"/><rect x="82" y="84" width="66" height="22" rx="5" fill="#0f3e64"/><path d="M88 104 L98 92 L108 98 L118 88 L128 96 L138 86" stroke="#59d3ff" stroke-width="3" fill="none"/><rect x="154" y="84" width="56" height="12" rx="5" fill="#43b2dd"/></svg>`;
  }
  if (styleId === "race-cluster") {
    return `<svg viewBox="0 0 220 128" aria-hidden="true"><circle cx="110" cy="82" r="38" fill="#2f6f9f"/><circle cx="110" cy="82" r="22" fill="#113f67"/><rect x="6" y="52" width="52" height="38" rx="8" fill="#1f5b88"/><rect x="162" y="52" width="52" height="38" rx="8" fill="#1f5b88"/><rect x="76" y="6" width="68" height="24" rx="8" fill="#43b2dd"/></svg>`;
  }
  if (styleId === "summit-grid") {
    return `<svg viewBox="0 0 220 128" aria-hidden="true"><rect x="4" y="8" width="70" height="30" rx="8" fill="#1f5b88"/><rect x="4" y="66" width="70" height="58" rx="8" fill="#43b2dd"/><rect x="80" y="84" width="90" height="40" rx="8" fill="#2a84be"/><rect x="176" y="8" width="40" height="54" rx="8" fill="#2d7db4"/><rect x="176" y="68" width="40" height="54" rx="8" fill="#1e5f93"/></svg>`;
  }
  return `<svg viewBox="0 0 220 128" aria-hidden="true"><rect x="10" y="10" width="200" height="108" rx="10" fill="#2f6f9f"/></svg>`;
}

function renderLayoutPreviewCards(styles) {
  layoutPreviewGrid.innerHTML = "";

  styles.forEach((style) => {
    const styleId = typeof style === "string" ? style : style.id;
    if (!styleId) return;

    const styleLabel = typeof style === "string" ? style : style.label || style.id;
    const styleDescription = typeof style === "string" ? "" : style.description || "";

    const card = document.createElement("button");
    card.type = "button";
    card.className = "layout-preview-card";
    card.dataset.layoutStyleId = styleId;
    card.innerHTML = `
      <div class="layout-preview-visual">${getLayoutPreviewSvg(styleId)}</div>
      <div class="layout-preview-meta">
        <strong>${styleLabel}</strong>
        <small>${styleDescription}</small>
      </div>
    `;

    card.addEventListener("click", () => {
      layoutStyleSelect.value = styleId;
      updateLayoutStyleHelp();
    });

    layoutPreviewGrid.append(card);
  });

  syncLayoutPreviewSelection();
}

function setThemes(themes) {
  overlayThemeSelect.innerHTML = "";
  themesById.clear();

  themes.forEach((theme) => {
    const themeId = typeof theme === "string" ? theme : theme.id;
    if (!themeId) return;

    const themeLabel = typeof theme === "string" ? theme : theme.label || theme.id;
    const option = document.createElement("option");
    option.value = themeId;
    option.textContent = themeLabel;
    overlayThemeSelect.append(option);

    if (typeof theme === "string") {
      themesById.set(themeId, { id: themeId, label: themeLabel });
    } else {
      themesById.set(themeId, theme);
    }
  });

  if (!overlayThemeSelect.value && overlayThemeSelect.options.length > 0) {
    overlayThemeSelect.value = overlayThemeSelect.options[0].value;
  }

  updateThemePreview();
}

function setLayoutStyles(styles, defaultLayout = "summit-grid") {
  layoutStyleSelect.innerHTML = "";
  layoutStylesById.clear();

  styles.forEach((style) => {
    const styleId = typeof style === "string" ? style : style.id;
    if (!styleId) return;

    const styleLabel = typeof style === "string" ? style : style.label || style.id;

    const option = document.createElement("option");
    option.value = styleId;
    option.textContent = styleLabel;
    layoutStyleSelect.append(option);

    if (typeof style === "string") {
      layoutStylesById.set(styleId, { id: styleId, description: "" });
    } else {
      layoutStylesById.set(styleId, style);
    }
  });

  if (layoutStyleSelect.options.length > 0) {
    const selected = Array.from(layoutStyleSelect.options).some((opt) => opt.value === defaultLayout)
      ? defaultLayout
      : layoutStyleSelect.options[0].value;
    layoutStyleSelect.value = selected;
  }

  renderLayoutPreviewCards(styles);
  updateLayoutStyleHelp();
}

function getComponentNode(id) {
  return componentOptionsRoot.querySelector(`input[data-component-id="${id}"]`);
}

function getComponentVisibility() {
  const state = {};
  componentOptionsRoot.querySelectorAll("input[data-component-id]").forEach((node) => {
    state[node.dataset.componentId] = node.checked;
  });
  return state;
}

function syncComponentDependencies() {
  const statsEnabled = getComponentNode("stats_panel")?.checked ?? true;
  ["altitude_metric", "grade_metric", "distance_metric"].forEach((id) => {
    const node = getComponentNode(id);
    if (node) {
      node.disabled = !statsEnabled;
      node.closest("label")?.classList.toggle("disabled", !statsEnabled);
    }
  });

  const gpsEnabled = getComponentNode("gps_panel")?.checked ?? true;
  const coords = getComponentNode("gps_coordinates");
  if (coords) {
    coords.disabled = !gpsEnabled;
    coords.closest("label")?.classList.toggle("disabled", !gpsEnabled);
  }

  const mapsEnabled = getComponentNode("route_maps")?.checked ?? true;
  if (mapStyleSelect) {
    mapStyleSelect.disabled = !mapsEnabled;
  }
}

function renderComponentOptions(options, defaults = {}) {
  componentOptionsRoot.innerHTML = "";
  options.forEach((option) => {
    const id = typeof option === "string" ? option : option.id;
    if (!id) return;

    const labelText = typeof option === "string" ? option : option.label || option.id;
    const description = typeof option === "string" ? "" : option.description || "";
    const defaultEnabled =
      Object.prototype.hasOwnProperty.call(defaults, id)
        ? Boolean(defaults[id])
        : Boolean(typeof option === "object" ? option.default_enabled : true);

    const label = document.createElement("label");
    label.className = "component-toggle";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = defaultEnabled;
    input.dataset.componentId = id;
    input.id = `component_${id}`;

    const title = document.createElement("span");
    title.className = "component-toggle-title";
    title.textContent = labelText;

    const meta = document.createElement("small");
    meta.className = "component-toggle-meta";
    meta.textContent = description;

    label.append(input, title, meta);
    componentOptionsRoot.append(label);
  });

  syncComponentDependencies();
}

function applyUnitsPreset(preset) {
  if (preset === "metric") {
    speedUnitsSelect.value = "kph";
    distanceUnitsSelect.value = "km";
    altitudeUnitsSelect.value = "metre";
    temperatureUnitsSelect.value = "degC";
  } else if (preset === "imperial") {
    speedUnitsSelect.value = "mph";
    distanceUnitsSelect.value = "mile";
    altitudeUnitsSelect.value = "feet";
    temperatureUnitsSelect.value = "degF";
  }

  const isCustom = preset === "custom";
  [speedUnitsSelect, distanceUnitsSelect, altitudeUnitsSelect, temperatureUnitsSelect].forEach((node) => {
    node.disabled = !isCustom;
  });
}

function syncUnitsPreset(preset) {
  applyUnitsPreset(preset || unitsPresetSelect.value);
}

async function loadMeta() {
  try {
    const response = await fetch("/api/meta");
    if (!response.ok) {
      throw new Error("Meta unavailable");
    }
    const meta = await response.json();

    setThemes(meta.theme_options || fallbackThemes);
    setLayoutStyles(meta.layout_styles || fallbackLayoutStyles, meta.default_layout_style || "summit-grid");

    renderComponentOptions(
      meta.component_options || fallbackComponents,
      meta.default_component_visibility || undefined,
    );

    const profiles = meta.render_profiles || [];
    renderProfileSelect.innerHTML = "";
    renderProfilesById.clear();

    profiles.forEach((profile) => {
      const profileId = typeof profile === "string" ? profile : profile.id;
      const profileLabel = typeof profile === "string" ? profile : profile.label || profile.id;

      if (!profileId) return;

      const option = document.createElement("option");
      option.value = profileId;
      option.textContent = profileLabel;
      renderProfileSelect.append(option);

      if (typeof profile === "string") {
        renderProfilesById.set(profileId, { id: profileId, summary: "" });
      } else {
        renderProfilesById.set(profileId, profile);
      }
    });

    if (meta.default_render_profile) {
      renderProfileSelect.value = meta.default_render_profile;
    }
    updateRenderProfileHelp();
  } catch (_error) {
    if (renderProfileSelect.options.length === 0) {
      const option = document.createElement("option");
      option.value = "h264-fast";
      option.textContent = "H.264 (Fast Draft)";
      renderProfileSelect.append(option);
      renderProfilesById.set("h264-fast", { id: "h264-fast", summary: "Fast fallback profile." });
      updateRenderProfileHelp();
    }

    if (overlayThemeSelect.options.length === 0) {
      setThemes(fallbackThemes);
    }

    if (layoutStyleSelect.options.length === 0) {
      setLayoutStyles(fallbackLayoutStyles, "summit-grid");
    }

    if (componentOptionsRoot.childElementCount === 0) {
      renderComponentOptions(fallbackComponents);
    }
  }
}

function syncFpsFieldVisibility() {
  const isFixed = fpsModeSelect.value === "fixed";
  fixedFpsField.style.display = isFixed ? "grid" : "none";
}

syncFpsFieldVisibility();
fpsModeSelect.addEventListener("change", syncFpsFieldVisibility);
renderProfileSelect.addEventListener("change", updateRenderProfileHelp);
overlayThemeSelect.addEventListener("change", updateThemePreview);
layoutStyleSelect.addEventListener("change", updateLayoutStyleHelp);
componentOptionsRoot.addEventListener("change", (event) => {
  const target = event.target;
  if (target instanceof HTMLInputElement && target.dataset.componentId) {
    syncComponentDependencies();
  }
});
unitsPresetSelect.addEventListener("change", () => {
  syncUnitsPreset(unitsPresetSelect.value);
});

["change", "input"].forEach((eventName) => {
  speedUnitsSelect.addEventListener(eventName, () => {
    unitsPresetSelect.value = "custom";
    syncUnitsPreset("custom");
  });
  distanceUnitsSelect.addEventListener(eventName, () => {
    unitsPresetSelect.value = "custom";
    syncUnitsPreset("custom");
  });
  altitudeUnitsSelect.addEventListener(eventName, () => {
    unitsPresetSelect.value = "custom";
    syncUnitsPreset("custom");
  });
  temperatureUnitsSelect.addEventListener(eventName, () => {
    unitsPresetSelect.value = "custom";
    syncUnitsPreset("custom");
  });
});

syncUnitsPreset(unitsPresetSelect.value);
setThemes(fallbackThemes);
setLayoutStyles(fallbackLayoutStyles, "summit-grid");
renderComponentOptions(fallbackComponents);
loadMeta();

function formatBytes(value) {
  if (!value && value !== 0) return "";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`;
}

function isFinalState(state) {
  return terminalStates.has(state);
}

function setSubmitState(isBusy) {
  submitBtn.disabled = isBusy;
  submitBtn.textContent = isBusy ? "Rendering..." : "Render overlays";
}

function renderVideoRows(videos, jobId) {
  videoList.innerHTML = "";

  videos.forEach((video) => {
    const item = document.createElement("li");

    const rowTop = document.createElement("div");
    rowTop.className = "row-top";

    const name = document.createElement("span");
    name.textContent = video.input_name;

    const right = document.createElement("span");
    right.className = `badge ${video.status}`;
    right.textContent = `${video.status} ${video.progress || 0}%`;

    rowTop.append(name, right);

    const detail = document.createElement("div");
    detail.className = "row-detail";

    const detailParts = [];
    if (video.error) {
      detailParts.push(video.error);
    } else if (video.detail) {
      detailParts.push(video.detail);
    }

    if (video.source_resolution || video.source_fps) {
      const clipInfo = [video.source_resolution, video.source_fps ? `${video.source_fps} fps` : null]
        .filter(Boolean)
        .join(" | ");
      if (clipInfo) {
        detailParts.push(`Source: ${clipInfo}`);
      }
    }

    if (video.render_profile_label) {
      detailParts.push(`Export: ${video.render_profile_label}`);
    }

    if (video.output_size_bytes) {
      detailParts.push(formatBytes(video.output_size_bytes));
    }

    detail.textContent = detailParts.join(" | ") || "";

    const links = document.createElement("div");
    links.className = "actions";

    if (video.download_url) {
      const anchor = document.createElement("a");
      anchor.href = video.download_url;
      anchor.textContent = "Download video";
      links.append(anchor);
    }

    if (video.log_name) {
      const log = document.createElement("a");
      log.href = `/api/jobs/${jobId}/log/${video.log_name}`;
      log.textContent = "Renderer log";
      links.append(log);
    }

    item.append(rowTop, detail);
    if (links.children.length > 0) {
      item.append(links);
    }

    videoList.append(item);
  });
}

function renderDownloads(job) {
  downloadActions.innerHTML = "";

  if (job.download_all_url) {
    const zipLink = document.createElement("a");
    zipLink.href = job.download_all_url;
    zipLink.textContent = "Download all (.zip)";
    downloadActions.append(zipLink);
  }
}

async function pollJob(jobId) {
  try {
    const response = await fetch(`/api/jobs/${jobId}`);
    if (!response.ok) {
      throw new Error(`Could not fetch job ${jobId}`);
    }

    const job = await response.json();
    jobMessage.textContent = job.message || job.status;
    progressBar.style.width = `${Math.max(0, Math.min(100, job.progress || 0))}%`;

    renderVideoRows(job.videos || [], job.id);
    renderDownloads(job);

    if (isFinalState(job.status)) {
      clearInterval(pollHandle);
      pollHandle = null;
      setSubmitState(false);
    }
  } catch (error) {
    jobMessage.textContent = `Polling error: ${error.message}`;
    clearInterval(pollHandle);
    pollHandle = null;
    setSubmitState(false);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const gpxInput = document.getElementById("gpx");
  const videosInput = document.getElementById("videos");
  if (!gpxInput.files.length || !videosInput.files.length) {
    return;
  }

  if (pollHandle) {
    clearInterval(pollHandle);
    pollHandle = null;
  }

  setSubmitState(true);
  jobPanel.classList.remove("hidden");
  jobMessage.textContent = "Uploading files...";
  progressBar.style.width = "0%";
  videoList.innerHTML = "";
  downloadActions.innerHTML = "";

  const payload = new FormData();
  payload.append("gpx", gpxInput.files[0]);

  Array.from(videosInput.files).forEach((file) => {
    payload.append("videos", file);
  });

  [
    "overlay_theme",
    "layout_style",
    "units_preset",
    "map_style",
    "speed_units",
    "gpx_speed_unit",
    "distance_units",
    "altitude_units",
    "temperature_units",
    "gpx_offset_seconds",
    "fps_mode",
    "fixed_fps",
    "render_profile",
  ].forEach((fieldId) => {
    const node = document.getElementById(fieldId);
    payload.append(fieldId, node.value);
  });

  const componentVisibility = getComponentVisibility();
  const includeMaps = componentVisibility.route_maps !== false;
  payload.append("component_visibility", JSON.stringify(componentVisibility));
  payload.append("include_maps", includeMaps ? "true" : "false");

  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      body: payload,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Failed to create render job");
    }

    const data = await response.json();
    activeJobId = data.job_id;
    await pollJob(activeJobId);

    pollHandle = setInterval(() => {
      pollJob(activeJobId);
    }, 2000);
  } catch (error) {
    jobMessage.textContent = error.message;
    setSubmitState(false);
  }
});
