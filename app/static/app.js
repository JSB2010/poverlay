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
const unitsPresetSelect = document.getElementById("units_preset");
const speedUnitsSelect = document.getElementById("speed_units");
const distanceUnitsSelect = document.getElementById("distance_units");
const altitudeUnitsSelect = document.getElementById("altitude_units");
const temperatureUnitsSelect = document.getElementById("temperature_units");

let activeJobId = null;
let pollHandle = null;
const renderProfilesById = new Map();

const terminalStates = new Set(["completed", "completed_with_errors", "failed"]);

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
      return;
    }
    const meta = await response.json();
    const themes = meta.theme_options || [];
    overlayThemeSelect.innerHTML = "";
    themes.forEach((theme) => {
      const option = document.createElement("option");
      option.value = typeof theme === "string" ? theme : theme.id;
      option.textContent = typeof theme === "string" ? theme : theme.label || theme.id;
      overlayThemeSelect.append(option);
    });

    if (!overlayThemeSelect.value && overlayThemeSelect.options.length > 0) {
      overlayThemeSelect.value = overlayThemeSelect.options[0].value;
    }

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
  }
}

function syncFpsFieldVisibility() {
  const isFixed = fpsModeSelect.value === "fixed";
  fixedFpsField.style.display = isFixed ? "grid" : "none";
}

syncFpsFieldVisibility();
fpsModeSelect.addEventListener("change", syncFpsFieldVisibility);
renderProfileSelect.addEventListener("change", updateRenderProfileHelp);
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

  payload.append("include_maps", document.getElementById("include_maps").checked ? "true" : "false");

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
