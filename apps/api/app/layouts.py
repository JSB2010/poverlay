from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OverlayTheme:
    name: str
    label: str
    panel_bg: str
    panel_bg_alt: str
    speed_rgb: str
    accent_rgb: str
    text_rgb: str


@dataclass(frozen=True)
class OverlayLayoutStyle:
    name: str
    label: str
    description: str


@dataclass(frozen=True)
class OverlayComponentOption:
    name: str
    label: str
    description: str
    default_enabled: bool = True


THEMES: dict[str, OverlayTheme] = {
    "powder-neon": OverlayTheme(
        name="powder-neon",
        label="Powder Neon",
        panel_bg="8,18,36,210",
        panel_bg_alt="16,34,58,195",
        speed_rgb="66,238,255",
        accent_rgb="255,171,95",
        text_rgb="240,247,255",
    ),
    "summit-ember": OverlayTheme(
        name="summit-ember",
        label="Summit Ember",
        panel_bg="25,18,23,210",
        panel_bg_alt="42,26,28,190",
        speed_rgb="255,126,86",
        accent_rgb="255,203,130",
        text_rgb="255,244,233",
    ),
    "glacier-steel": OverlayTheme(
        name="glacier-steel",
        label="Glacier Steel",
        panel_bg="12,24,34,210",
        panel_bg_alt="19,37,50,194",
        speed_rgb="128,228,255",
        accent_rgb="154,199,245",
        text_rgb="234,244,255",
    ),
    "forest-sprint": OverlayTheme(
        name="forest-sprint",
        label="Forest Sprint",
        panel_bg="15,34,30,208",
        panel_bg_alt="27,52,43,194",
        speed_rgb="124,255,181",
        accent_rgb="199,255,152",
        text_rgb="234,255,244",
    ),
    "night-sprint": OverlayTheme(
        name="night-sprint",
        label="Night Sprint",
        panel_bg="17,12,31,210",
        panel_bg_alt="32,23,54,194",
        speed_rgb="214,164,255",
        accent_rgb="129,223,255",
        text_rgb="243,236,255",
    ),
    "sunset-drive": OverlayTheme(
        name="sunset-drive",
        label="Sunset Drive",
        panel_bg="36,20,14,212",
        panel_bg_alt="54,31,22,194",
        speed_rgb="255,176,116",
        accent_rgb="255,228,146",
        text_rgb="255,245,234",
    ),
}


LAYOUT_STYLES: dict[str, OverlayLayoutStyle] = {
    "summit-grid": OverlayLayoutStyle(
        name="summit-grid",
        label="Summit Grid",
        description="Balanced dashboard with maps on the right and stats anchored along the bottom.",
    ),
    "velocity-rail": OverlayLayoutStyle(
        name="velocity-rail",
        label="Velocity Rail",
        description="Tall left rail for telemetry, leaving a clean right side for terrain and map context.",
    ),
    "cinematic-lower-third": OverlayLayoutStyle(
        name="cinematic-lower-third",
        label="Cinematic Lower Third",
        description="Film-style lower-third telemetry with layered map modules in the upper corner.",
    ),
    "apex-split": OverlayLayoutStyle(
        name="apex-split",
        label="Apex Split",
        description="Center-focused speed cluster with mirrored top and bottom information zones.",
    ),
    "moto-dial-bars": OverlayLayoutStyle(
        name="moto-dial-bars",
        label="Moto Dial Bars",
        description="Gauge-driven speed dial with zone bars and load bars for a motorsport-style cluster.",
    ),
    "telemetry-hud": OverlayLayoutStyle(
        name="telemetry-hud",
        label="Telemetry HUD",
        description="Heads-up telemetry strip with live speed chart and performance zone meters.",
    ),
    "race-cluster": OverlayLayoutStyle(
        name="race-cluster",
        label="Race Cluster",
        description="Dual-indicator race dashboard with compass heading and stacked performance bars.",
    ),
    "moto-journey-needle": OverlayLayoutStyle(
        name="moto-journey-needle",
        label="Moto Journey Needle",
        description="Moto-inspired needle dial with brake/throttle bars, journey map stack, and speed trend chart.",
    ),
    "moto-journey-dual-bars": OverlayLayoutStyle(
        name="moto-journey-dual-bars",
        label="Moto Journey Dual Bars",
        description="Dual-indicator moto cluster with mirrored control bars and moving journey map stack.",
    ),
    "compass-asi-cluster": OverlayLayoutStyle(
        name="compass-asi-cluster",
        label="Compass ASI Cluster",
        description="Heading compass with mirrored ASI gauges and center speed cluster.",
    ),
    "power-zone-pro": OverlayLayoutStyle(
        name="power-zone-pro",
        label="Power Zone Pro",
        description="Power-focused telemetry HUD with zone bars, gradient trend chart, and icon-backed metrics.",
    ),
}


DEFAULT_LAYOUT_STYLE = "summit-grid"


COMPONENT_OPTIONS: dict[str, OverlayComponentOption] = {
    "time_panel": OverlayComponentOption(
        name="time_panel",
        label="Time Panel",
        description="Date and clock display.",
        default_enabled=True,
    ),
    "speed_panel": OverlayComponentOption(
        name="speed_panel",
        label="Speed Panel",
        description="Primary speed readout.",
        default_enabled=True,
    ),
    "stats_panel": OverlayComponentOption(
        name="stats_panel",
        label="Stats Panel",
        description="Compact panel for altitude, grade, and distance.",
        default_enabled=True,
    ),
    "altitude_metric": OverlayComponentOption(
        name="altitude_metric",
        label="Altitude",
        description="Altitude metric inside Stats panel.",
        default_enabled=True,
    ),
    "grade_metric": OverlayComponentOption(
        name="grade_metric",
        label="Grade",
        description="Slope/grade metric inside Stats panel.",
        default_enabled=True,
    ),
    "distance_metric": OverlayComponentOption(
        name="distance_metric",
        label="Distance",
        description="Distance traveled metric inside Stats panel.",
        default_enabled=True,
    ),
    "gps_panel": OverlayComponentOption(
        name="gps_panel",
        label="GPS Panel",
        description="GPS lock panel with status icon.",
        default_enabled=True,
    ),
    "gps_coordinates": OverlayComponentOption(
        name="gps_coordinates",
        label="GPS Coordinates",
        description="Latitude/longitude text lines inside GPS panel.",
        default_enabled=True,
    ),
    "route_maps": OverlayComponentOption(
        name="route_maps",
        label="Route Maps",
        description="Moving and full-route map components.",
        default_enabled=True,
    ),
}


DEFAULT_COMPONENT_VISIBILITY: dict[str, bool] = {
    key: option.default_enabled for key, option in COMPONENT_OPTIONS.items()
}


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def _metric_sizes(height: int) -> dict[str, int]:
    return {
        "label": _clamp(int(height * 0.018), 20, 52),
        "speed": _clamp(int(height * 0.105), 110, 340),
        "metric": _clamp(int(height * 0.042), 36, 120),
        "small_metric": _clamp(int(height * 0.03), 28, 84),
        "time": _clamp(int(height * 0.033), 30, 86),
    }


def _is_enabled(visibility: dict[str, bool], component_name: str) -> bool:
    return bool(visibility.get(component_name, DEFAULT_COMPONENT_VISIBILITY.get(component_name, True)))


def _speed_scale_profile(speed_units: str) -> dict[str, int]:
    normalized = speed_units.lower().strip()
    if normalized == "mph":
        return {"max": 90, "z1": 28, "z2": 45, "z3": 65, "yellow": 55, "end": 90}
    if normalized == "mps":
        return {"max": 40, "z1": 12, "z2": 18, "z3": 28, "yellow": 24, "end": 40}
    if normalized == "knots":
        return {"max": 80, "z1": 24, "z2": 36, "z3": 52, "yellow": 44, "end": 80}
    return {"max": 140, "z1": 40, "z2": 62, "z3": 90, "yellow": 75, "end": 140}


def _time_panel(
    theme: OverlayTheme,
    x: int,
    y: int,
    width: int,
    height: int,
    panel_radius: int,
    label_size: int,
    time_size: int,
    visibility: dict[str, bool],
) -> str:
    if not _is_enabled(visibility, "time_panel"):
        return ""
    return f"""    <composite x=\"{x}\" y=\"{y}\" name=\"clock_panel\">
        <frame width=\"{width}\" height=\"{height}\" bg=\"{theme.panel_bg}\" cr=\"{panel_radius}\" opacity=\"0.88\">
            <component type=\"text\" x=\"{int(width * 0.06)}\" y=\"{int(height * 0.14)}\" size=\"{label_size}\" rgb=\"{theme.accent_rgb}\">LOCAL TIME</component>
            <component type=\"datetime\" x=\"{int(width * 0.06)}\" y=\"{int(height * 0.36)}\" format=\"%Y-%m-%d\" size=\"{time_size}\" rgb=\"{theme.text_rgb}\"/>
            <component type=\"datetime\" x=\"{int(width * 0.06)}\" y=\"{int(height * 0.63)}\" format=\"%H:%M:%S\" size=\"{time_size}\" rgb=\"{theme.text_rgb}\"/>
        </frame>
    </composite>"""


def _speed_panel(
    theme: OverlayTheme,
    x: int,
    y: int,
    width: int,
    height: int,
    panel_radius: int,
    label_size: int,
    speed_size: int,
    visibility: dict[str, bool],
) -> str:
    if not _is_enabled(visibility, "speed_panel"):
        return ""
    return f"""    <composite x=\"{x}\" y=\"{y}\" name=\"speed_panel\">
        <frame width=\"{width}\" height=\"{height}\" bg=\"{theme.panel_bg}\" cr=\"{panel_radius}\" opacity=\"0.90\">
            <component type=\"text\" x=\"{int(width * 0.08)}\" y=\"{int(height * 0.08)}\" size=\"{label_size}\" rgb=\"{theme.accent_rgb}\">SPEED</component>
            <component type=\"metric_unit\" x=\"{int(width * 0.92)}\" y=\"{int(height * 0.09)}\" metric=\"speed\" units=\"speed\" size=\"{label_size}\" align=\"right\" rgb=\"{theme.accent_rgb}\">{{:~c}}</component>
            <component type=\"metric\" x=\"{int(width * 0.08)}\" y=\"{int(height * 0.26)}\" metric=\"speed\" units=\"speed\" dp=\"1\" size=\"{speed_size}\" rgb=\"{theme.speed_rgb}\" outline=\"0,0,0\" outline_width=\"4\"/>
        </frame>
    </composite>"""


def _stats_columns(
    theme: OverlayTheme,
    panel_width: int,
    panel_height: int,
    label_size: int,
    metric_size: int,
    small_metric_size: int,
    visibility: dict[str, bool],
) -> str:
    metric_ids = [
        metric_id
        for metric_id in ("altitude_metric", "grade_metric", "distance_metric")
        if _is_enabled(visibility, metric_id)
    ]
    if not metric_ids:
        return ""

    slot_width = panel_width / len(metric_ids)
    lines: list[str] = []
    for index, metric_id in enumerate(metric_ids):
        base_x = int(slot_width * index + slot_width * 0.08)
        if metric_id == "altitude_metric":
            lines.append(
                f'            <component type="text" x="{base_x}" y="{int(panel_height * 0.10)}" size="{label_size}" rgb="{theme.accent_rgb}">ALT</component>'
            )
            lines.append(
                f'            <component type="metric" x="{base_x}" y="{int(panel_height * 0.34)}" metric="alt" units="alt" dp="0" size="{metric_size}" rgb="{theme.text_rgb}"/>'
            )
            lines.append(
                f'            <component type="metric_unit" x="{base_x}" y="{int(panel_height * 0.66)}" metric="alt" units="alt" size="{label_size}" rgb="{theme.accent_rgb}">{{:~c}}</component>'
            )
        elif metric_id == "grade_metric":
            lines.append(
                f'            <component type="text" x="{base_x}" y="{int(panel_height * 0.10)}" size="{label_size}" rgb="{theme.accent_rgb}">GRADE</component>'
            )
            lines.append(
                f'            <component type="metric" x="{base_x}" y="{int(panel_height * 0.34)}" metric="gradient" dp="1" size="{metric_size}" rgb="{theme.text_rgb}"/>'
            )
            lines.append(
                f'            <component type="text" x="{base_x}" y="{int(panel_height * 0.66)}" size="{label_size}" rgb="{theme.accent_rgb}">%</component>'
            )
        else:
            lines.append(
                f'            <component type="text" x="{base_x}" y="{int(panel_height * 0.10)}" size="{label_size}" rgb="{theme.accent_rgb}">DIST</component>'
            )
            lines.append(
                f'            <component type="metric" x="{base_x}" y="{int(panel_height * 0.34)}" metric="odo" units="distance" dp="2" size="{small_metric_size}" rgb="{theme.text_rgb}"/>'
            )
            lines.append(
                f'            <component type="metric_unit" x="{base_x}" y="{int(panel_height * 0.66)}" metric="odo" units="distance" size="{label_size}" rgb="{theme.accent_rgb}">{{:~c}}</component>'
            )
    return "\n".join(lines)


def _stats_panel(
    theme: OverlayTheme,
    x: int,
    y: int,
    width: int,
    height: int,
    panel_radius: int,
    label_size: int,
    metric_size: int,
    small_metric_size: int,
    visibility: dict[str, bool],
) -> str:
    if not _is_enabled(visibility, "stats_panel"):
        return ""
    stats_lines = _stats_columns(theme, width, height, label_size, metric_size, small_metric_size, visibility)
    if not stats_lines:
        return ""
    return f"""    <composite x=\"{x}\" y=\"{y}\" name=\"stats_panel\">
        <frame width=\"{width}\" height=\"{height}\" bg=\"{theme.panel_bg_alt}\" cr=\"{panel_radius}\" opacity=\"0.88\">
{stats_lines}
        </frame>
    </composite>"""


def _gps_panel(
    theme: OverlayTheme,
    x: int,
    y: int,
    width: int,
    height: int,
    panel_radius: int,
    label_size: int,
    icon_size: int,
    visibility: dict[str, bool],
) -> str:
    if not _is_enabled(visibility, "gps_panel"):
        return ""
    coordinates_enabled = _is_enabled(visibility, "gps_coordinates")
    coordinate_rows = ""
    if coordinates_enabled:
        coordinate_rows = (
            f'\n            <component type="metric" x="{int(width * 0.22)}" y="{int(height * 0.40)}" metric="lat" dp="5" cache="False" size="{label_size}" rgb="{theme.text_rgb}"/>'
            f'\n            <component type="metric" x="{int(width * 0.22)}" y="{int(height * 0.67)}" metric="lon" dp="5" cache="False" size="{label_size}" rgb="{theme.text_rgb}"/>'
        )
    else:
        coordinate_rows = (
            f'\n            <component type="text" x="{int(width * 0.24)}" y="{int(height * 0.50)}" size="{label_size}" rgb="{theme.text_rgb}">LOCK STATUS</component>'
        )

    return f"""    <composite x=\"{x}\" y=\"{y}\" name=\"gps_panel\">
        <frame width=\"{width}\" height=\"{height}\" bg=\"{theme.panel_bg}\" cr=\"{panel_radius}\" opacity=\"0.84\">
            <component type=\"text\" x=\"{int(width * 0.08)}\" y=\"{int(height * 0.12)}\" size=\"{label_size}\" rgb=\"{theme.accent_rgb}\">GPS LOCK</component>
            <composite x=\"{int(width * 0.08)}\" y=\"{int(height * 0.42)}\">
                <component type=\"gps-lock-icon\" size=\"{icon_size}\"/>
            </composite>
{coordinate_rows}
        </frame>
    </composite>"""


def _map_components(
    map_specs: list[dict[str, int]],
    panel_radius: int,
    visibility: dict[str, bool],
) -> str:
    if not _is_enabled(visibility, "route_maps"):
        return ""
    lines: list[str] = []
    for spec in map_specs:
        map_type = spec.get("type")
        x = spec.get("x")
        y = spec.get("y")
        size = spec.get("size")
        if map_type not in {"moving_map", "journey_map"}:
            continue
        if not isinstance(x, int) or not isinstance(y, int) or not isinstance(size, int):
            continue
        if map_type == "moving_map":
            zoom = int(spec.get("zoom", 15))
            lines.append(
                f'    <component type="moving_map" name="moving_map" x="{x}" y="{y}" size="{size}" zoom="{zoom}" corner_radius="{int(panel_radius * 1.2)}"/>'
            )
        else:
            lines.append(
                f'    <component type="journey_map" name="journey_map" x="{x}" y="{y}" size="{size}" corner_radius="{int(panel_radius * 1.2)}"/>'
            )
    return "\n".join(lines)


def _render_style_summit_grid(
    width: int,
    height: int,
    theme: OverlayTheme,
    visibility: dict[str, bool],
) -> list[str]:
    margin = _clamp(int(min(width, height) * 0.02), 24, 72)
    panel_radius = _clamp(int(min(width, height) * 0.018), 20, 54)
    sizes = _metric_sizes(height)

    speed_w = int(width * 0.23)
    speed_h = int(height * 0.20)
    speed_x = margin
    speed_y = height - speed_h - margin

    stats_w = int(width * 0.33)
    stats_h = int(height * 0.15)
    stats_x = speed_x + speed_w + margin
    stats_y = height - stats_h - margin

    time_w = int(width * 0.24)
    time_h = int(height * 0.16)
    time_x = margin
    time_y = margin

    map_size = int(min(width, height) * 0.24)
    map_x = width - map_size - margin
    moving_map_y = margin
    journey_map_y = moving_map_y + map_size + margin

    gps_w = int(width * 0.24)
    gps_h = int(height * 0.11)
    gps_x = width - gps_w - margin
    gps_y = journey_map_y + map_size + margin

    return [
        _time_panel(theme, time_x, time_y, time_w, time_h, panel_radius, sizes["label"], sizes["time"], visibility),
        _speed_panel(
            theme,
            speed_x,
            speed_y,
            speed_w,
            speed_h,
            panel_radius,
            sizes["label"],
            sizes["speed"],
            visibility,
        ),
        _stats_panel(
            theme,
            stats_x,
            stats_y,
            stats_w,
            stats_h,
            panel_radius,
            sizes["label"],
            sizes["metric"],
            sizes["small_metric"],
            visibility,
        ),
        _gps_panel(
            theme,
            gps_x,
            gps_y,
            gps_w,
            gps_h,
            panel_radius,
            sizes["label"],
            sizes["small_metric"],
            visibility,
        ),
        _map_components(
            [
                {"type": "moving_map", "x": map_x, "y": moving_map_y, "size": map_size, "zoom": 15},
                {"type": "journey_map", "x": map_x, "y": journey_map_y, "size": map_size},
            ],
            panel_radius,
            visibility,
        ),
    ]


def _render_style_velocity_rail(
    width: int,
    height: int,
    theme: OverlayTheme,
    visibility: dict[str, bool],
) -> list[str]:
    margin = _clamp(int(min(width, height) * 0.02), 24, 72)
    panel_radius = _clamp(int(min(width, height) * 0.017), 18, 50)
    sizes = _metric_sizes(height)

    rail_x = margin
    rail_w = int(width * 0.24)
    time_h = int(height * 0.13)
    speed_h = int(height * 0.26)
    stats_h = int(height * 0.18)
    gps_h = int(height * 0.13)

    time_y = margin
    speed_y = time_y + time_h + margin
    stats_y = speed_y + speed_h + margin
    gps_y = stats_y + stats_h + margin
    if gps_y + gps_h > height - margin:
        gps_y = height - gps_h - margin

    map_size = int(min(width, height) * 0.23)
    map_x = width - map_size - margin
    moving_map_y = margin
    journey_map_y = moving_map_y + map_size + margin

    return [
        _time_panel(theme, rail_x, time_y, rail_w, time_h, panel_radius, sizes["label"], sizes["time"], visibility),
        _speed_panel(
            theme,
            rail_x,
            speed_y,
            rail_w,
            speed_h,
            panel_radius,
            sizes["label"],
            int(sizes["speed"] * 0.94),
            visibility,
        ),
        _stats_panel(
            theme,
            rail_x,
            stats_y,
            rail_w,
            stats_h,
            panel_radius,
            sizes["label"],
            int(sizes["metric"] * 0.88),
            int(sizes["small_metric"] * 0.88),
            visibility,
        ),
        _gps_panel(
            theme,
            rail_x,
            gps_y,
            rail_w,
            gps_h,
            panel_radius,
            sizes["label"],
            sizes["small_metric"],
            visibility,
        ),
        _map_components(
            [
                {"type": "moving_map", "x": map_x, "y": moving_map_y, "size": map_size, "zoom": 16},
                {"type": "journey_map", "x": map_x, "y": journey_map_y, "size": map_size},
            ],
            panel_radius,
            visibility,
        ),
    ]


def _render_style_cinematic_lower_third(
    width: int,
    height: int,
    theme: OverlayTheme,
    visibility: dict[str, bool],
) -> list[str]:
    margin = _clamp(int(min(width, height) * 0.02), 24, 72)
    panel_radius = _clamp(int(min(width, height) * 0.02), 22, 56)
    sizes = _metric_sizes(height)

    speed_w = int(width * 0.34)
    speed_h = int(height * 0.22)
    speed_x = margin
    speed_y = height - speed_h - margin

    stats_w = int(width * 0.27)
    stats_h = int(height * 0.16)
    stats_x = speed_x + speed_w + margin
    stats_y = height - stats_h - margin

    gps_w = int(width * 0.25)
    gps_h = int(height * 0.12)
    gps_x = width - gps_w - margin
    gps_y = height - gps_h - margin

    time_w = int(width * 0.22)
    time_h = int(height * 0.12)
    time_x = margin
    time_y = speed_y - time_h - margin

    journey_size = int(min(width, height) * 0.27)
    journey_x = width - journey_size - margin
    journey_y = margin
    moving_size = int(journey_size * 0.52)
    moving_x = journey_x + journey_size - moving_size - int(margin * 0.35)
    moving_y = journey_y + journey_size - moving_size - int(margin * 0.35)

    return [
        _time_panel(theme, time_x, time_y, time_w, time_h, panel_radius, sizes["label"], sizes["time"], visibility),
        _speed_panel(
            theme,
            speed_x,
            speed_y,
            speed_w,
            speed_h,
            panel_radius,
            sizes["label"],
            int(sizes["speed"] * 1.07),
            visibility,
        ),
        _stats_panel(
            theme,
            stats_x,
            stats_y,
            stats_w,
            stats_h,
            panel_radius,
            sizes["label"],
            int(sizes["metric"] * 0.84),
            int(sizes["small_metric"] * 0.84),
            visibility,
        ),
        _gps_panel(
            theme,
            gps_x,
            gps_y,
            gps_w,
            gps_h,
            panel_radius,
            sizes["label"],
            int(sizes["small_metric"] * 0.9),
            visibility,
        ),
        _map_components(
            [
                {"type": "journey_map", "x": journey_x, "y": journey_y, "size": journey_size},
                {"type": "moving_map", "x": moving_x, "y": moving_y, "size": moving_size, "zoom": 15},
            ],
            panel_radius,
            visibility,
        ),
    ]


def _render_style_apex_split(
    width: int,
    height: int,
    theme: OverlayTheme,
    visibility: dict[str, bool],
) -> list[str]:
    margin = _clamp(int(min(width, height) * 0.02), 24, 72)
    panel_radius = _clamp(int(min(width, height) * 0.016), 18, 48)
    sizes = _metric_sizes(height)

    speed_w = int(width * 0.31)
    speed_h = int(height * 0.24)
    speed_x = int((width - speed_w) / 2)
    speed_y = height - speed_h - margin

    stats_w = int(width * 0.42)
    stats_h = int(height * 0.15)
    stats_x = int((width - stats_w) / 2)
    stats_y = margin

    time_w = int(width * 0.21)
    time_h = int(height * 0.12)
    time_x = margin
    time_y = height - time_h - margin

    gps_w = int(width * 0.21)
    gps_h = int(height * 0.12)
    gps_x = width - gps_w - margin
    gps_y = height - gps_h - margin

    map_size = int(min(width, height) * 0.21)
    moving_x = margin
    moving_y = margin
    journey_x = width - map_size - margin
    journey_y = margin

    return [
        _time_panel(theme, time_x, time_y, time_w, time_h, panel_radius, sizes["label"], sizes["time"], visibility),
        _speed_panel(
            theme,
            speed_x,
            speed_y,
            speed_w,
            speed_h,
            panel_radius,
            sizes["label"],
            int(sizes["speed"] * 1.04),
            visibility,
        ),
        _stats_panel(
            theme,
            stats_x,
            stats_y,
            stats_w,
            stats_h,
            panel_radius,
            sizes["label"],
            sizes["metric"],
            sizes["small_metric"],
            visibility,
        ),
        _gps_panel(
            theme,
            gps_x,
            gps_y,
            gps_w,
            gps_h,
            panel_radius,
            sizes["label"],
            sizes["small_metric"],
            visibility,
        ),
        _map_components(
            [
                {"type": "moving_map", "x": moving_x, "y": moving_y, "size": map_size, "zoom": 16},
                {"type": "journey_map", "x": journey_x, "y": journey_y, "size": map_size},
            ],
            panel_radius,
            visibility,
        ),
    ]


def _render_style_moto_dial_bars(
    width: int,
    height: int,
    theme: OverlayTheme,
    visibility: dict[str, bool],
    speed_units: str,
) -> list[str]:
    margin = _clamp(int(min(width, height) * 0.02), 24, 72)
    panel_radius = _clamp(int(min(width, height) * 0.017), 18, 52)
    sizes = _metric_sizes(height)
    speed_profile = _speed_scale_profile(speed_units)

    time_w = int(width * 0.23)
    time_h = int(height * 0.12)
    time_x = margin
    time_y = margin

    stats_w = int(width * 0.34)
    stats_h = int(height * 0.14)
    stats_x = int(width * 0.33)
    stats_y = margin

    dial_w = int(width * 0.34)
    dial_h = int(height * 0.38)
    dial_x = margin
    dial_y = height - dial_h - margin

    bars_w = int(width * 0.36)
    bars_h = int(height * 0.22)
    bars_x = dial_x + dial_w + margin
    bars_y = height - bars_h - margin

    gps_w = int(width * 0.24)
    gps_h = int(height * 0.12)
    gps_x = bars_x
    gps_y = bars_y - gps_h - margin

    map_size = int(min(width, height) * 0.19)
    map_x = width - map_size - margin
    moving_y = margin
    journey_y = moving_y + map_size + margin

    dial_panel = ""
    if _is_enabled(visibility, "speed_panel"):
        dial_size = int(min(dial_w, dial_h) * 0.72)
        dial_panel = f"""    <composite x=\"{dial_x}\" y=\"{dial_y}\" name=\"speed_dial_panel\">
        <frame width=\"{dial_w}\" height=\"{dial_h}\" bg=\"{theme.panel_bg}\" cr=\"{panel_radius}\" opacity=\"0.92\">
            <component type=\"text\" x=\"{int(dial_w * 0.08)}\" y=\"{int(dial_h * 0.08)}\" size=\"{sizes["label"]}\" rgb=\"{theme.accent_rgb}\">SPEED DIAL</component>
            <composite x=\"{int((dial_w - dial_size) / 2)}\" y=\"{int(dial_h * 0.16)}\">
                <component type=\"msi\" metric=\"speed\" units=\"{speed_units}\" size=\"{dial_size}\" textsize=\"{int(sizes["label"] * 0.9)}\" needle=\"1\" yellow=\"{speed_profile["yellow"]}\" end=\"{speed_profile["end"]}\" outline=\"3\"/>
            </composite>
            <component type=\"metric\" x=\"{int(dial_w * 0.50)}\" y=\"{int(dial_h * 0.73)}\" metric=\"speed\" units=\"speed\" dp=\"0\" size=\"{int(sizes["metric"] * 1.15)}\" align=\"centre\" rgb=\"{theme.speed_rgb}\" outline=\"0,0,0\" outline_width=\"3\"/>
            <component type=\"metric_unit\" x=\"{int(dial_w * 0.50)}\" y=\"{int(dial_h * 0.86)}\" metric=\"speed\" units=\"speed\" size=\"{sizes["label"]}\" align=\"centre\" rgb=\"{theme.accent_rgb}\">{{:~c}}</component>
        </frame>
    </composite>"""

    bars_panel = ""
    if _is_enabled(visibility, "speed_panel"):
        bars_panel = f"""    <composite x=\"{bars_x}\" y=\"{bars_y}\" name=\"performance_bar_panel\">
        <frame width=\"{bars_w}\" height=\"{bars_h}\" bg=\"{theme.panel_bg_alt}\" cr=\"{panel_radius}\" opacity=\"0.90\">
            <component type=\"text\" x=\"{int(bars_w * 0.06)}\" y=\"{int(bars_h * 0.10)}\" size=\"{sizes["label"]}\" rgb=\"{theme.accent_rgb}\">SPEED ZONES</component>
            <composite x=\"{int(bars_w * 0.06)}\" y=\"{int(bars_h * 0.28)}\">
                <component type=\"zone-bar\" width=\"{int(bars_w * 0.88)}\" height=\"{int(bars_h * 0.20)}\" metric=\"speed\" units=\"{speed_units}\" min=\"0\" max=\"{speed_profile["max"]}\" z1=\"{speed_profile["z1"]}\" z2=\"{speed_profile["z2"]}\" z3=\"{speed_profile["z3"]}\" z0-rgb=\"84,162,255,185\" z1-rgb=\"67,235,52,200\" z2-rgb=\"240,232,19,200\" z3-rgb=\"207,19,2,210\" outline=\"255,255,255,150\" outline-width=\"2\"/>
            </composite>
            <component type=\"text\" x=\"{int(bars_w * 0.06)}\" y=\"{int(bars_h * 0.58)}\" size=\"{sizes["label"]}\" rgb=\"{theme.accent_rgb}\">GRADE LOAD</component>
            <composite x=\"{int(bars_w * 0.06)}\" y=\"{int(bars_h * 0.74)}\">
                <component type=\"bar\" width=\"{int(bars_w * 0.88)}\" height=\"{int(bars_h * 0.16)}\" metric=\"gradient\" min=\"-18\" max=\"18\" fill=\"255,255,255,18\" zero=\"255,255,255,180\" bar=\"{theme.speed_rgb}\" h-neg=\"255,129,129\" h-pos=\"124,255,181\" outline=\"255,255,255,150\" outline-width=\"2\"/>
            </composite>
        </frame>
    </composite>"""

    return [
        _time_panel(theme, time_x, time_y, time_w, time_h, panel_radius, sizes["label"], sizes["time"], visibility),
        _stats_panel(
            theme,
            stats_x,
            stats_y,
            stats_w,
            stats_h,
            panel_radius,
            sizes["label"],
            sizes["metric"],
            sizes["small_metric"],
            visibility,
        ),
        dial_panel,
        bars_panel,
        _gps_panel(
            theme,
            gps_x,
            gps_y,
            gps_w,
            gps_h,
            panel_radius,
            sizes["label"],
            sizes["small_metric"],
            visibility,
        ),
        _map_components(
            [
                {"type": "moving_map", "x": map_x, "y": moving_y, "size": map_size, "zoom": 15},
                {"type": "journey_map", "x": map_x, "y": journey_y, "size": map_size},
            ],
            panel_radius,
            visibility,
        ),
    ]


def _render_style_telemetry_hud(
    width: int,
    height: int,
    theme: OverlayTheme,
    visibility: dict[str, bool],
    speed_units: str,
) -> list[str]:
    margin = _clamp(int(min(width, height) * 0.02), 24, 72)
    panel_radius = _clamp(int(min(width, height) * 0.018), 20, 54)
    sizes = _metric_sizes(height)
    speed_profile = _speed_scale_profile(speed_units)

    time_w = int(width * 0.22)
    time_h = int(height * 0.11)
    time_x = margin
    time_y = margin

    stats_w = int(width * 0.30)
    stats_h = int(height * 0.13)
    stats_x = int((width - stats_w) / 2)
    stats_y = margin

    hud_w = width - (margin * 2)
    hud_h = int(height * 0.26)
    hud_x = margin
    hud_y = height - hud_h - margin

    gps_w = int(width * 0.24)
    gps_h = int(height * 0.11)
    gps_x = width - gps_w - margin
    gps_y = margin

    map_size = int(min(width, height) * 0.18)
    moving_x = width - map_size - margin
    moving_y = gps_y + gps_h + margin
    journey_x = moving_x - map_size - margin
    journey_y = moving_y

    hud_panel = ""
    if _is_enabled(visibility, "speed_panel"):
        hud_panel = f"""    <composite x=\"{hud_x}\" y=\"{hud_y}\" name=\"telemetry_hud_panel\">
        <frame width=\"{hud_w}\" height=\"{hud_h}\" bg=\"{theme.panel_bg}\" cr=\"{panel_radius}\" opacity=\"0.91\">
            <component type=\"text\" x=\"{int(hud_w * 0.03)}\" y=\"{int(hud_h * 0.10)}\" size=\"{sizes["label"]}\" rgb=\"{theme.accent_rgb}\">SPEED</component>
            <component type=\"metric\" x=\"{int(hud_w * 0.03)}\" y=\"{int(hud_h * 0.30)}\" metric=\"speed\" units=\"speed\" dp=\"1\" size=\"{int(sizes["speed"] * 0.72)}\" rgb=\"{theme.speed_rgb}\" outline=\"0,0,0\" outline_width=\"3\"/>
            <component type=\"metric_unit\" x=\"{int(hud_w * 0.17)}\" y=\"{int(hud_h * 0.18)}\" metric=\"speed\" units=\"speed\" size=\"{sizes["label"]}\" rgb=\"{theme.accent_rgb}\">{{:~c}}</component>
            <component type=\"text\" x=\"{int(hud_w * 0.36)}\" y=\"{int(hud_h * 0.10)}\" size=\"{sizes["label"]}\" rgb=\"{theme.accent_rgb}\">SPEED TREND</component>
            <component type=\"chart\" x=\"{int(hud_w * 0.36)}\" y=\"{int(hud_h * 0.22)}\" height=\"{int(hud_h * 0.56)}\" metric=\"speed\" units=\"{speed_units}\" samples=\"420\" values=\"false\" fill=\"58,188,255,160\" line=\"255,255,255,180\" bg=\"255,255,255,20\" text=\"255,255,255,200\"/>
            <component type=\"text\" x=\"{int(hud_w * 0.71)}\" y=\"{int(hud_h * 0.10)}\" size=\"{sizes["label"]}\" rgb=\"{theme.accent_rgb}\">ACTIVE ZONE</component>
            <composite x=\"{int(hud_w * 0.71)}\" y=\"{int(hud_h * 0.28)}\">
                <component type=\"zone-bar\" width=\"{int(hud_w * 0.25)}\" height=\"{int(hud_h * 0.20)}\" metric=\"speed\" units=\"{speed_units}\" min=\"0\" max=\"{speed_profile["max"]}\" z1=\"{speed_profile["z1"]}\" z2=\"{speed_profile["z2"]}\" z3=\"{speed_profile["z3"]}\" z0-rgb=\"84,162,255,185\" z1-rgb=\"67,235,52,200\" z2-rgb=\"240,232,19,200\" z3-rgb=\"207,19,2,210\" outline=\"255,255,255,150\" outline-width=\"2\"/>
            </composite>
            <composite x=\"{int(hud_w * 0.71)}\" y=\"{int(hud_h * 0.60)}\">
                <component type=\"bar\" width=\"{int(hud_w * 0.25)}\" height=\"{int(hud_h * 0.18)}\" metric=\"gradient\" min=\"-18\" max=\"18\" fill=\"255,255,255,18\" zero=\"255,255,255,180\" bar=\"{theme.speed_rgb}\" h-neg=\"255,129,129\" h-pos=\"124,255,181\" outline=\"255,255,255,150\" outline-width=\"2\"/>
            </composite>
        </frame>
    </composite>"""

    return [
        _time_panel(theme, time_x, time_y, time_w, time_h, panel_radius, sizes["label"], sizes["time"], visibility),
        _stats_panel(
            theme,
            stats_x,
            stats_y,
            stats_w,
            stats_h,
            panel_radius,
            sizes["label"],
            sizes["metric"],
            sizes["small_metric"],
            visibility,
        ),
        _gps_panel(
            theme,
            gps_x,
            gps_y,
            gps_w,
            gps_h,
            panel_radius,
            sizes["label"],
            sizes["small_metric"],
            visibility,
        ),
        hud_panel,
        _map_components(
            [
                {"type": "moving_map", "x": moving_x, "y": moving_y, "size": map_size, "zoom": 16},
                {"type": "journey_map", "x": journey_x, "y": journey_y, "size": map_size},
            ],
            panel_radius,
            visibility,
        ),
    ]


def _render_style_race_cluster(
    width: int,
    height: int,
    theme: OverlayTheme,
    visibility: dict[str, bool],
    speed_units: str,
) -> list[str]:
    margin = _clamp(int(min(width, height) * 0.02), 24, 72)
    panel_radius = _clamp(int(min(width, height) * 0.017), 19, 52)
    sizes = _metric_sizes(height)
    speed_profile = _speed_scale_profile(speed_units)

    time_w = int(width * 0.20)
    time_h = int(height * 0.11)
    time_x = margin
    time_y = margin

    stats_w = int(width * 0.34)
    stats_h = int(height * 0.13)
    stats_x = width - stats_w - margin
    stats_y = margin

    cluster_w = int(width * 0.36)
    cluster_h = int(height * 0.36)
    cluster_x = int((width - cluster_w) / 2)
    cluster_y = height - cluster_h - margin

    compass_w = int(width * 0.22)
    compass_h = int(height * 0.18)
    compass_x = margin
    compass_y = int(height * 0.36)

    load_w = int(width * 0.28)
    load_h = int(height * 0.20)
    load_x = width - load_w - margin
    load_y = int(height * 0.36)

    gps_w = int(width * 0.26)
    gps_h = int(height * 0.11)
    gps_x = int((width - gps_w) / 2)
    gps_y = margin

    map_size = int(min(width, height) * 0.17)
    moving_x = margin
    moving_y = height - map_size - margin
    journey_x = width - map_size - margin
    journey_y = height - map_size - margin

    cluster_panel = ""
    if _is_enabled(visibility, "speed_panel"):
        dial_size = int(min(cluster_w, cluster_h) * 0.66)
        cluster_panel = f"""    <composite x=\"{cluster_x}\" y=\"{cluster_y}\" name=\"race_cluster_panel\">
        <frame width=\"{cluster_w}\" height=\"{cluster_h}\" bg=\"{theme.panel_bg}\" cr=\"{panel_radius}\" opacity=\"0.92\">
            <component type=\"text\" x=\"{int(cluster_w * 0.08)}\" y=\"{int(cluster_h * 0.09)}\" size=\"{sizes["label"]}\" rgb=\"{theme.accent_rgb}\">RACE CLUSTER</component>
            <composite x=\"{int((cluster_w - dial_size) / 2)}\" y=\"{int(cluster_h * 0.18)}\">
                <component type=\"msi2\" metric=\"speed\" units=\"{speed_units}\" size=\"{dial_size}\" textsize=\"{int(sizes["label"] * 0.9)}\" yellow=\"{speed_profile["yellow"]}\" end=\"{speed_profile["end"]}\" outline=\"3\"/>
            </composite>
            <component type=\"metric\" x=\"{int(cluster_w * 0.50)}\" y=\"{int(cluster_h * 0.74)}\" metric=\"speed\" units=\"speed\" dp=\"0\" size=\"{int(sizes["metric"] * 1.18)}\" align=\"centre\" rgb=\"{theme.speed_rgb}\" outline=\"0,0,0\" outline_width=\"3\"/>
            <component type=\"metric_unit\" x=\"{int(cluster_w * 0.50)}\" y=\"{int(cluster_h * 0.87)}\" metric=\"speed\" units=\"speed\" size=\"{sizes["label"]}\" align=\"centre\" rgb=\"{theme.accent_rgb}\">{{:~c}}</component>
        </frame>
    </composite>"""

    compass_panel = ""
    if _is_enabled(visibility, "gps_panel"):
        compass_size = int(min(compass_w, compass_h) * 0.72)
        compass_panel = f"""    <composite x=\"{compass_x}\" y=\"{compass_y}\" name=\"compass_panel\">
        <frame width=\"{compass_w}\" height=\"{compass_h}\" bg=\"{theme.panel_bg_alt}\" cr=\"{panel_radius}\" opacity=\"0.88\">
            <component type=\"text\" x=\"{int(compass_w * 0.08)}\" y=\"{int(compass_h * 0.12)}\" size=\"{sizes["label"]}\" rgb=\"{theme.accent_rgb}\">HEADING</component>
            <composite x=\"{int((compass_w - compass_size) / 2)}\" y=\"{int(compass_h * 0.20)}\">
                <component type=\"compass_arrow\" size=\"{compass_size}\" textsize=\"{int(sizes["label"] * 0.9)}\" arrow=\"{theme.speed_rgb}\" text=\"{theme.text_rgb}\" outline=\"0,0,0\" arrow-outline=\"0,0,0\"/>
            </composite>
        </frame>
    </composite>"""

    load_panel = ""
    if _is_enabled(visibility, "speed_panel"):
        load_panel = f"""    <composite x=\"{load_x}\" y=\"{load_y}\" name=\"load_panel\">
        <frame width=\"{load_w}\" height=\"{load_h}\" bg=\"{theme.panel_bg_alt}\" cr=\"{panel_radius}\" opacity=\"0.90\">
            <component type=\"text\" x=\"{int(load_w * 0.08)}\" y=\"{int(load_h * 0.12)}\" size=\"{sizes["label"]}\" rgb=\"{theme.accent_rgb}\">PERFORMANCE</component>
            <composite x=\"{int(load_w * 0.08)}\" y=\"{int(load_h * 0.34)}\">
                <component type=\"zone-bar\" width=\"{int(load_w * 0.84)}\" height=\"{int(load_h * 0.20)}\" metric=\"speed\" units=\"{speed_units}\" min=\"0\" max=\"{speed_profile["max"]}\" z1=\"{speed_profile["z1"]}\" z2=\"{speed_profile["z2"]}\" z3=\"{speed_profile["z3"]}\" z0-rgb=\"84,162,255,185\" z1-rgb=\"67,235,52,200\" z2-rgb=\"240,232,19,200\" z3-rgb=\"207,19,2,210\" outline=\"255,255,255,150\" outline-width=\"2\"/>
            </composite>
            <composite x=\"{int(load_w * 0.08)}\" y=\"{int(load_h * 0.66)}\">
                <component type=\"bar\" width=\"{int(load_w * 0.84)}\" height=\"{int(load_h * 0.18)}\" metric=\"gradient\" min=\"-18\" max=\"18\" fill=\"255,255,255,18\" zero=\"255,255,255,180\" bar=\"{theme.speed_rgb}\" h-neg=\"255,129,129\" h-pos=\"124,255,181\" outline=\"255,255,255,150\" outline-width=\"2\"/>
            </composite>
        </frame>
    </composite>"""

    return [
        _time_panel(theme, time_x, time_y, time_w, time_h, panel_radius, sizes["label"], sizes["time"], visibility),
        _stats_panel(
            theme,
            stats_x,
            stats_y,
            stats_w,
            stats_h,
            panel_radius,
            sizes["label"],
            sizes["metric"],
            sizes["small_metric"],
            visibility,
        ),
        _gps_panel(
            theme,
            gps_x,
            gps_y,
            gps_w,
            gps_h,
            panel_radius,
            sizes["label"],
            sizes["small_metric"],
            visibility,
        ),
        cluster_panel,
        compass_panel,
        load_panel,
        _map_components(
            [
                {"type": "moving_map", "x": moving_x, "y": moving_y, "size": map_size, "zoom": 16},
                {"type": "journey_map", "x": journey_x, "y": journey_y, "size": map_size},
            ],
            panel_radius,
            visibility,
        ),
    ]


def _render_style_moto_journey_core(
    width: int,
    height: int,
    theme: OverlayTheme,
    visibility: dict[str, bool],
    speed_units: str,
    dial_component: str,
) -> list[str]:
    margin = _clamp(int(min(width, height) * 0.02), 24, 72)
    panel_radius = _clamp(int(min(width, height) * 0.018), 20, 54)
    sizes = _metric_sizes(height)
    speed_profile = _speed_scale_profile(speed_units)

    time_w = int(width * 0.24)
    time_h = int(height * 0.12)
    time_x = margin
    time_y = margin

    stats_w = int(width * 0.28)
    stats_h = int(height * 0.14)
    stats_x = margin
    stats_y = time_y + time_h + margin

    dial_w = int(width * 0.30)
    dial_h = int(height * 0.34)
    dial_x = margin
    dial_y = height - dial_h - margin

    bars_w = int(width * 0.31)
    bars_h = int(height * 0.15)
    bars_x = dial_x + dial_w + margin
    bars_y = height - bars_h - margin

    chart_x = bars_x + bars_w + margin
    chart_y = height - int(height * 0.15) - margin
    chart_w = width - chart_x - margin
    chart_h = int(height * 0.15)
    if chart_w < int(width * 0.18):
        chart_x = int(width * 0.43)
        chart_w = width - chart_x - margin

    map_size = int(min(width, height) * 0.18)
    map_x = width - map_size - margin
    map_y = margin
    map_gap = int(margin * 0.55)
    map_stack_h = (map_size * 2) + map_gap

    gps_w = int(width * 0.24)
    gps_h = int(height * 0.11)
    gps_x = width - gps_w - margin
    gps_y = map_y + map_stack_h + margin
    if gps_y + gps_h > height - margin:
        gps_y = height - gps_h - margin

    dial_panel = ""
    if _is_enabled(visibility, "speed_panel"):
        dial_size = int(min(dial_w, dial_h) * 0.72)
        needle = ' needle="1"' if dial_component == "msi" else ""
        dial_panel = f"""    <composite x=\"{dial_x}\" y=\"{dial_y}\" name=\"moto_journey_dial_panel\">
        <frame width=\"{dial_w}\" height=\"{dial_h}\" bg=\"{theme.panel_bg}\" cr=\"{panel_radius}\" opacity=\"0.92\">
            <component type=\"text\" x=\"{int(dial_w * 0.08)}\" y=\"{int(dial_h * 0.10)}\" size=\"{sizes["label"]}\" rgb=\"{theme.accent_rgb}\">MOTO SPEED</component>
            <composite x=\"{int((dial_w - dial_size) / 2)}\" y=\"{int(dial_h * 0.17)}\">
                <component type=\"{dial_component}\" metric=\"speed\" units=\"{speed_units}\" size=\"{dial_size}\" textsize=\"{int(sizes["label"] * 0.9)}\" yellow=\"{speed_profile["yellow"]}\" end=\"{speed_profile["end"]}\" outline=\"3\"{needle}/>
            </composite>
            <component type=\"metric\" x=\"{int(dial_w * 0.50)}\" y=\"{int(dial_h * 0.72)}\" metric=\"speed\" units=\"speed\" dp=\"0\" size=\"{int(sizes["metric"] * 1.15)}\" align=\"centre\" rgb=\"{theme.speed_rgb}\" outline=\"0,0,0\" outline_width=\"3\"/>
            <component type=\"metric_unit\" x=\"{int(dial_w * 0.50)}\" y=\"{int(dial_h * 0.85)}\" metric=\"speed\" units=\"speed\" size=\"{sizes["label"]}\" align=\"centre\" rgb=\"{theme.accent_rgb}\">{{:~c}}</component>
        </frame>
    </composite>"""

    bars_panel = ""
    if _is_enabled(visibility, "speed_panel"):
        bars_panel = f"""    <composite x=\"{bars_x}\" y=\"{bars_y}\" name=\"moto_control_bars\">
        <frame width=\"{bars_w}\" height=\"{bars_h}\" bg=\"{theme.panel_bg_alt}\" cr=\"{panel_radius}\" opacity=\"0.90\">
            <component type=\"text\" x=\"{int(bars_w * 0.07)}\" y=\"{int(bars_h * 0.10)}\" size=\"{sizes["label"]}\" rgb=\"{theme.accent_rgb}\">BRAKE / THROTTLE</component>
            <composite x=\"{int(bars_w * 0.07)}\" y=\"{int(bars_h * 0.40)}\">
                <component type=\"bar\" width=\"{int(bars_w * 0.40)}\" min=\"-3\" max=\"0\" height=\"{int(bars_h * 0.34)}\" metric=\"accel\" outline-width=\"2\" bar=\"255,157,157\" h-neg=\"255,157,157\" h-pos=\"255,157,157\" zero=\"0,0,0,0\"/>
            </composite>
            <composite x=\"{int(bars_w * 0.53)}\" y=\"{int(bars_h * 0.40)}\">
                <component type=\"bar\" width=\"{int(bars_w * 0.40)}\" min=\"0\" max=\"3\" height=\"{int(bars_h * 0.34)}\" metric=\"accel\" outline-width=\"2\" bar=\"157,157,255\" h-neg=\"157,157,255\" h-pos=\"157,157,255\" zero=\"0,0,0,0\"/>
            </composite>
        </frame>
    </composite>"""

    chart_panel = ""
    if _is_enabled(visibility, "speed_panel"):
        chart_panel = f"""    <composite x=\"{chart_x}\" y=\"{chart_y}\" name=\"moto_speed_chart\">
        <frame width=\"{chart_w}\" height=\"{chart_h}\" bg=\"{theme.panel_bg}\" cr=\"{panel_radius}\" opacity=\"0.88\">
            <component type=\"chart\" x=\"{int(chart_w * 0.04)}\" y=\"{int(chart_h * 0.18)}\" height=\"{int(chart_h * 0.62)}\" metric=\"speed\" units=\"{speed_units}\" samples=\"300\" values=\"false\" fill=\"58,188,255,160\" line=\"255,255,255,180\" bg=\"255,255,255,20\" text=\"255,255,255,200\"/>
        </frame>
    </composite>"""

    map_stack = ""
    if _is_enabled(visibility, "route_maps"):
        map_stack = f"""    <composite x=\"{map_x}\" y=\"{map_y}\" name=\"journey_map_stack\">
        <frame width=\"{map_size}\" height=\"{map_size}\" bg=\"{theme.panel_bg_alt}\" cr=\"{int(panel_radius * 0.9)}\" opacity=\"0.72\">
            <component type=\"moving_map\" name=\"moving_map\" size=\"{map_size}\" zoom=\"15\" corner_radius=\"{int(panel_radius * 0.9)}\"/>
        </frame>
        <frame y=\"{map_size + map_gap}\" width=\"{map_size}\" height=\"{map_size}\" bg=\"{theme.panel_bg_alt}\" cr=\"{int(panel_radius * 0.9)}\" opacity=\"0.72\">
            <component type=\"moving_journey_map\" size=\"{map_size}\" zoom=\"14\"/>
        </frame>
    </composite>"""

    return [
        _time_panel(theme, time_x, time_y, time_w, time_h, panel_radius, sizes["label"], sizes["time"], visibility),
        _stats_panel(
            theme,
            stats_x,
            stats_y,
            stats_w,
            stats_h,
            panel_radius,
            sizes["label"],
            sizes["metric"],
            sizes["small_metric"],
            visibility,
        ),
        _gps_panel(
            theme,
            gps_x,
            gps_y,
            gps_w,
            gps_h,
            panel_radius,
            sizes["label"],
            sizes["small_metric"],
            visibility,
        ),
        dial_panel,
        bars_panel,
        chart_panel,
        map_stack,
    ]


def _render_style_moto_journey_needle(
    width: int,
    height: int,
    theme: OverlayTheme,
    visibility: dict[str, bool],
    speed_units: str,
) -> list[str]:
    return _render_style_moto_journey_core(width, height, theme, visibility, speed_units, dial_component="msi")


def _render_style_moto_journey_dual_bars(
    width: int,
    height: int,
    theme: OverlayTheme,
    visibility: dict[str, bool],
    speed_units: str,
) -> list[str]:
    return _render_style_moto_journey_core(width, height, theme, visibility, speed_units, dial_component="msi2")


def _render_style_compass_asi_cluster(
    width: int,
    height: int,
    theme: OverlayTheme,
    visibility: dict[str, bool],
    speed_units: str,
) -> list[str]:
    margin = _clamp(int(min(width, height) * 0.02), 24, 72)
    panel_radius = _clamp(int(min(width, height) * 0.017), 19, 52)
    sizes = _metric_sizes(height)

    time_w = int(width * 0.22)
    time_h = int(height * 0.11)
    time_x = margin
    time_y = margin

    stats_w = int(width * 0.34)
    stats_h = int(height * 0.13)
    stats_x = width - stats_w - margin
    stats_y = margin

    cluster_w = int(width * 0.42)
    cluster_h = int(height * 0.28)
    cluster_x = int((width - cluster_w) / 2)
    cluster_y = height - cluster_h - margin

    compass_w = int(width * 0.23)
    compass_h = int(height * 0.20)
    compass_x = margin
    compass_y = int(height * 0.38)

    gps_w = int(width * 0.26)
    gps_h = int(height * 0.11)
    gps_x = int((width - gps_w) / 2)
    gps_y = margin

    map_size = int(min(width, height) * 0.17)
    moving_x = width - map_size - margin
    moving_y = int(height * 0.38)
    journey_x = moving_x - map_size - margin
    journey_y = moving_y

    cluster_panel = ""
    if _is_enabled(visibility, "speed_panel"):
        cluster_panel = f"""    <composite x=\"{cluster_x}\" y=\"{cluster_y}\" name=\"compass_asi_speed_cluster\">
        <frame width=\"{cluster_w}\" height=\"{cluster_h}\" bg=\"{theme.panel_bg}\" cr=\"{panel_radius}\" opacity=\"0.92\">
            <component type=\"text\" x=\"{int(cluster_w * 0.08)}\" y=\"{int(cluster_h * 0.10)}\" size=\"{sizes["label"]}\" rgb=\"{theme.accent_rgb}\">ASI CLUSTER</component>
            <composite x=\"{int(cluster_w * 0.12)}\" y=\"{int(cluster_h * 0.28)}\">
                <component type=\"asi\" vs0=\"10\"/>
            </composite>
            <composite x=\"{int(cluster_w * 0.56)}\" y=\"{int(cluster_h * 0.28)}\">
                <component type=\"asi\" vs0=\"10\" rotate=\"180\"/>
            </composite>
            <component type=\"metric\" x=\"{int(cluster_w * 0.50)}\" y=\"{int(cluster_h * 0.70)}\" metric=\"speed\" units=\"speed\" dp=\"0\" size=\"{int(sizes["metric"] * 1.25)}\" align=\"centre\" rgb=\"{theme.speed_rgb}\" outline=\"0,0,0\" outline_width=\"3\"/>
            <component type=\"metric_unit\" x=\"{int(cluster_w * 0.50)}\" y=\"{int(cluster_h * 0.84)}\" metric=\"speed\" units=\"speed\" size=\"{sizes["label"]}\" align=\"centre\" rgb=\"{theme.accent_rgb}\">{{:~c}}</component>
        </frame>
    </composite>"""

    compass_panel = ""
    if _is_enabled(visibility, "gps_panel"):
        compass_size = int(min(compass_w, compass_h) * 0.78)
        compass_panel = f"""    <composite x=\"{compass_x}\" y=\"{compass_y}\" name=\"compass_heading_panel\">
        <frame width=\"{compass_w}\" height=\"{compass_h}\" bg=\"{theme.panel_bg_alt}\" cr=\"{panel_radius}\" opacity=\"0.89\">
            <component type=\"text\" x=\"{int(compass_w * 0.08)}\" y=\"{int(compass_h * 0.10)}\" size=\"{sizes["label"]}\" rgb=\"{theme.accent_rgb}\">HEADING</component>
            <composite x=\"{int((compass_w - compass_size) / 2)}\" y=\"{int(compass_h * 0.18)}\">
                <component type=\"compass\" size=\"{compass_size}\" bg=\"0,0,0,0\" fg=\"{theme.text_rgb}\" text=\"{theme.speed_rgb}\" textsize=\"{int(sizes["label"] * 0.9)}\"/>
            </composite>
        </frame>
    </composite>"""

    return [
        _time_panel(theme, time_x, time_y, time_w, time_h, panel_radius, sizes["label"], sizes["time"], visibility),
        _stats_panel(
            theme,
            stats_x,
            stats_y,
            stats_w,
            stats_h,
            panel_radius,
            sizes["label"],
            sizes["metric"],
            sizes["small_metric"],
            visibility,
        ),
        _gps_panel(
            theme,
            gps_x,
            gps_y,
            gps_w,
            gps_h,
            panel_radius,
            sizes["label"],
            sizes["small_metric"],
            visibility,
        ),
        cluster_panel,
        compass_panel,
        _map_components(
            [
                {"type": "moving_map", "x": moving_x, "y": moving_y, "size": map_size, "zoom": 16},
                {"type": "journey_map", "x": journey_x, "y": journey_y, "size": map_size},
            ],
            panel_radius,
            visibility,
        ),
    ]


def _render_style_power_zone_pro(
    width: int,
    height: int,
    theme: OverlayTheme,
    visibility: dict[str, bool],
    speed_units: str,
) -> list[str]:
    margin = _clamp(int(min(width, height) * 0.02), 24, 72)
    panel_radius = _clamp(int(min(width, height) * 0.018), 20, 54)
    sizes = _metric_sizes(height)

    time_w = int(width * 0.22)
    time_h = int(height * 0.11)
    time_x = margin
    time_y = margin

    stats_w = int(width * 0.30)
    stats_h = int(height * 0.13)
    stats_x = int((width - stats_w) / 2)
    stats_y = margin

    gps_w = int(width * 0.24)
    gps_h = int(height * 0.11)
    gps_x = width - gps_w - margin
    gps_y = margin

    maps_size = int(min(width, height) * 0.18)
    moving_x = width - maps_size - margin
    moving_y = gps_y + gps_h + margin
    journey_x = moving_x - maps_size - margin
    journey_y = moving_y

    power_w = width - (margin * 2)
    power_h = int(height * 0.30)
    power_x = margin
    power_y = height - power_h - margin

    power_panel = ""
    if _is_enabled(visibility, "speed_panel"):
        power_panel = f"""    <composite x=\"{power_x}\" y=\"{power_y}\" name=\"power_zone_panel\">
        <frame width=\"{power_w}\" height=\"{power_h}\" bg=\"{theme.panel_bg}\" cr=\"{panel_radius}\" opacity=\"0.92\">
            <component type=\"text\" x=\"{int(power_w * 0.03)}\" y=\"{int(power_h * 0.09)}\" size=\"{sizes["label"]}\" rgb=\"{theme.accent_rgb}\">POWER ZONE PRO</component>
            <component type=\"metric\" x=\"{int(power_w * 0.03)}\" y=\"{int(power_h * 0.28)}\" metric=\"speed\" units=\"speed\" dp=\"0\" size=\"{int(sizes["speed"] * 0.68)}\" rgb=\"{theme.speed_rgb}\" outline=\"0,0,0\" outline_width=\"3\"/>
            <component type=\"metric_unit\" x=\"{int(power_w * 0.16)}\" y=\"{int(power_h * 0.18)}\" metric=\"speed\" units=\"speed\" size=\"{sizes["label"]}\" rgb=\"{theme.accent_rgb}\">{{:~c}}</component>
            <component type=\"icon\" x=\"{int(power_w * 0.03)}\" y=\"{int(power_h * 0.74)}\" file=\"mountain.png\" size=\"{int(sizes["small_metric"] * 1.6)}\"/>
            <component type=\"metric\" x=\"{int(power_w * 0.10)}\" y=\"{int(power_h * 0.77)}\" metric=\"alt\" units=\"alt\" dp=\"0\" size=\"{sizes["small_metric"]}\" rgb=\"{theme.text_rgb}\"/>
            <component type=\"icon\" x=\"{int(power_w * 0.22)}\" y=\"{int(power_h * 0.74)}\" file=\"slope-triangle.png\" size=\"{int(sizes["small_metric"] * 1.6)}\"/>
            <component type=\"metric\" x=\"{int(power_w * 0.29)}\" y=\"{int(power_h * 0.77)}\" metric=\"gradient\" dp=\"1\" size=\"{sizes["small_metric"]}\" rgb=\"{theme.text_rgb}\"/>
            <component type=\"gradient_chart\" x=\"{int(power_w * 0.36)}\" y=\"{int(power_h * 0.22)}\"/>
            <component type=\"icon\" x=\"{int(power_w * 0.64)}\" y=\"{int(power_h * 0.22)}\" file=\"heartbeat.png\" size=\"{int(sizes["small_metric"] * 1.7)}\"/>
            <component type=\"metric\" x=\"{int(power_w * 0.71)}\" y=\"{int(power_h * 0.25)}\" metric=\"hr\" dp=\"0\" size=\"{sizes["small_metric"]}\" rgb=\"{theme.text_rgb}\"/>
            <composite x=\"{int(power_w * 0.64)}\" y=\"{int(power_h * 0.38)}\">
                <component type=\"zone-bar\" width=\"{int(power_w * 0.32)}\" height=\"{int(power_h * 0.16)}\" metric=\"hr\" max=\"200\" z1=\"130\" z2=\"163\" z3=\"183\" z0-rgb=\"52,122,235,200\" z1-rgb=\"67,235,52,200\" z2-rgb=\"240,232,19,200\" z3-rgb=\"207,19,2,200\" outline=\"255,255,255,150\" outline-width=\"2\"/>
            </composite>
            <component type=\"icon\" x=\"{int(power_w * 0.64)}\" y=\"{int(power_h * 0.58)}\" file=\"power.png\" size=\"{int(sizes["small_metric"] * 1.7)}\"/>
            <component type=\"metric\" x=\"{int(power_w * 0.71)}\" y=\"{int(power_h * 0.61)}\" metric=\"power\" dp=\"0\" size=\"{sizes["small_metric"]}\" rgb=\"{theme.text_rgb}\"/>
            <composite x=\"{int(power_w * 0.64)}\" y=\"{int(power_h * 0.74)}\">
                <component type=\"zone-bar\" width=\"{int(power_w * 0.32)}\" height=\"{int(power_h * 0.16)}\" metric=\"power\" max=\"600\" z1=\"130\" z2=\"160\" z3=\"200\" z0-rgb=\"67,235,52,200\" z1-rgb=\"67,235,52,200\" z2-rgb=\"240,232,19,200\" z3-rgb=\"207,19,2,200\" outline=\"255,255,255,150\" outline-width=\"2\"/>
            </composite>
        </frame>
    </composite>"""

    return [
        _time_panel(theme, time_x, time_y, time_w, time_h, panel_radius, sizes["label"], sizes["time"], visibility),
        _stats_panel(
            theme,
            stats_x,
            stats_y,
            stats_w,
            stats_h,
            panel_radius,
            sizes["label"],
            sizes["metric"],
            sizes["small_metric"],
            visibility,
        ),
        _gps_panel(
            theme,
            gps_x,
            gps_y,
            gps_w,
            gps_h,
            panel_radius,
            sizes["label"],
            sizes["small_metric"],
            visibility,
        ),
        power_panel,
        _map_components(
            [
                {"type": "moving_map", "x": moving_x, "y": moving_y, "size": maps_size, "zoom": 16},
                {"type": "journey_map", "x": journey_x, "y": journey_y, "size": maps_size},
            ],
            panel_radius,
            visibility,
        ),
    ]


STYLE_RENDERERS = {
    "summit-grid": lambda w, h, t, v, _s: _render_style_summit_grid(w, h, t, v),
    "velocity-rail": lambda w, h, t, v, _s: _render_style_velocity_rail(w, h, t, v),
    "cinematic-lower-third": lambda w, h, t, v, _s: _render_style_cinematic_lower_third(w, h, t, v),
    "apex-split": lambda w, h, t, v, _s: _render_style_apex_split(w, h, t, v),
    "moto-dial-bars": _render_style_moto_dial_bars,
    "telemetry-hud": _render_style_telemetry_hud,
    "race-cluster": _render_style_race_cluster,
    "moto-journey-needle": _render_style_moto_journey_needle,
    "moto-journey-dual-bars": _render_style_moto_journey_dual_bars,
    "compass-asi-cluster": _render_style_compass_asi_cluster,
    "power-zone-pro": _render_style_power_zone_pro,
}


def render_layout_xml(
    width: int,
    height: int,
    theme_name: str,
    include_maps: bool = True,
    layout_style: str = DEFAULT_LAYOUT_STYLE,
    component_visibility: dict[str, bool] | None = None,
    speed_units: str = "kph",
) -> str:
    theme = THEMES.get(theme_name, THEMES["powder-neon"])
    style_name = layout_style if layout_style in STYLE_RENDERERS else DEFAULT_LAYOUT_STYLE
    resolved_speed_units = speed_units if speed_units in {"kph", "mph", "mps", "knots"} else "kph"
    visibility = dict(DEFAULT_COMPONENT_VISIBILITY)

    if component_visibility:
        for key, value in component_visibility.items():
            if key in visibility:
                visibility[key] = bool(value)
    if not include_maps:
        visibility["route_maps"] = False

    fragments = STYLE_RENDERERS[style_name](width, height, theme, visibility, resolved_speed_units)
    body = "\n\n".join(fragment for fragment in fragments if fragment.strip())
    if body:
        return f"<layout>\n{body}\n</layout>\n"
    return "<layout>\n</layout>\n"
