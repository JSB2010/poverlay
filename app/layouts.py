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


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def render_layout_xml(width: int, height: int, theme_name: str, include_maps: bool = True) -> str:
    theme = THEMES.get(theme_name, THEMES["powder-neon"])

    margin = _clamp(int(min(width, height) * 0.02), 24, 72)
    panel_radius = _clamp(int(min(width, height) * 0.018), 20, 54)

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

    label_size = _clamp(int(height * 0.018), 20, 52)
    speed_size = _clamp(int(height * 0.105), 110, 340)
    metric_size = _clamp(int(height * 0.042), 36, 120)
    small_metric_size = _clamp(int(height * 0.03), 28, 84)
    time_metric_size = _clamp(int(height * 0.033), 30, 86)

    map_components = ""
    if include_maps:
        map_components = (
            f'    <component type="moving_map" name="moving_map" x="{map_x}" y="{moving_map_y}" '
            f'size="{map_size}" zoom="15" corner_radius="{int(panel_radius * 1.2)}"/>\n'
            f'    <component type="journey_map" name="journey_map" x="{map_x}" y="{journey_map_y}" '
            f'size="{map_size}" corner_radius="{int(panel_radius * 1.2)}"/>\n'
        )

    return f"""<layout>
    <composite x=\"{time_x}\" y=\"{time_y}\" name=\"clock_panel\">
        <frame width=\"{time_w}\" height=\"{time_h}\" bg=\"{theme.panel_bg}\" cr=\"{panel_radius}\" opacity=\"0.88\">
            <component type=\"text\" x=\"{int(time_w * 0.06)}\" y=\"{int(time_h * 0.14)}\" size=\"{label_size}\" rgb=\"{theme.accent_rgb}\">LOCAL TIME</component>
            <component type=\"datetime\" x=\"{int(time_w * 0.06)}\" y=\"{int(time_h * 0.36)}\" format=\"%Y-%m-%d\" size=\"{time_metric_size}\" rgb=\"{theme.text_rgb}\"/>
            <component type=\"datetime\" x=\"{int(time_w * 0.06)}\" y=\"{int(time_h * 0.63)}\" format=\"%H:%M:%S\" size=\"{time_metric_size}\" rgb=\"{theme.text_rgb}\"/>
        </frame>
    </composite>

    <composite x=\"{speed_x}\" y=\"{speed_y}\" name=\"speed_panel\">
        <frame width=\"{speed_w}\" height=\"{speed_h}\" bg=\"{theme.panel_bg}\" cr=\"{panel_radius}\" opacity=\"0.90\">
            <component type=\"text\" x=\"{int(speed_w * 0.08)}\" y=\"{int(speed_h * 0.08)}\" size=\"{label_size}\" rgb=\"{theme.accent_rgb}\">SPEED</component>
            <component type=\"metric_unit\" x=\"{int(speed_w * 0.92)}\" y=\"{int(speed_h * 0.09)}\" metric=\"speed\" units=\"speed\" size=\"{label_size}\" align=\"right\" rgb=\"{theme.accent_rgb}\">{{:~c}}</component>
            <component type=\"metric\" x=\"{int(speed_w * 0.08)}\" y=\"{int(speed_h * 0.26)}\" metric=\"speed\" units=\"speed\" dp=\"1\" size=\"{speed_size}\" rgb=\"{theme.speed_rgb}\" outline=\"0,0,0\" outline_width=\"4\"/>
        </frame>
    </composite>

    <composite x=\"{stats_x}\" y=\"{stats_y}\" name=\"stats_panel\">
        <frame width=\"{stats_w}\" height=\"{stats_h}\" bg=\"{theme.panel_bg_alt}\" cr=\"{panel_radius}\" opacity=\"0.88\">
            <component type=\"text\" x=\"{int(stats_w * 0.08)}\" y=\"{int(stats_h * 0.10)}\" size=\"{label_size}\" rgb=\"{theme.accent_rgb}\">ALT</component>
            <component type=\"metric\" x=\"{int(stats_w * 0.08)}\" y=\"{int(stats_h * 0.34)}\" metric=\"alt\" units=\"alt\" dp=\"0\" size=\"{metric_size}\" rgb=\"{theme.text_rgb}\"/>
            <component type=\"metric_unit\" x=\"{int(stats_w * 0.08)}\" y=\"{int(stats_h * 0.66)}\" metric=\"alt\" units=\"alt\" size=\"{label_size}\" rgb=\"{theme.accent_rgb}\">{{:~c}}</component>

            <component type=\"text\" x=\"{int(stats_w * 0.38)}\" y=\"{int(stats_h * 0.10)}\" size=\"{label_size}\" rgb=\"{theme.accent_rgb}\">GRADE</component>
            <component type=\"metric\" x=\"{int(stats_w * 0.38)}\" y=\"{int(stats_h * 0.34)}\" metric=\"gradient\" dp=\"1\" size=\"{metric_size}\" rgb=\"{theme.text_rgb}\"/>
            <component type=\"text\" x=\"{int(stats_w * 0.38)}\" y=\"{int(stats_h * 0.66)}\" size=\"{label_size}\" rgb=\"{theme.accent_rgb}\">%</component>

            <component type=\"text\" x=\"{int(stats_w * 0.68)}\" y=\"{int(stats_h * 0.10)}\" size=\"{label_size}\" rgb=\"{theme.accent_rgb}\">DIST</component>
            <component type=\"metric\" x=\"{int(stats_w * 0.68)}\" y=\"{int(stats_h * 0.34)}\" metric=\"odo\" units=\"distance\" dp=\"2\" size=\"{small_metric_size}\" rgb=\"{theme.text_rgb}\"/>
            <component type=\"metric_unit\" x=\"{int(stats_w * 0.68)}\" y=\"{int(stats_h * 0.66)}\" metric=\"odo\" units=\"distance\" size=\"{label_size}\" rgb=\"{theme.accent_rgb}\">{{:~c}}</component>
        </frame>
    </composite>

    <composite x=\"{gps_x}\" y=\"{gps_y}\" name=\"gps_panel\">
        <frame width=\"{gps_w}\" height=\"{gps_h}\" bg=\"{theme.panel_bg}\" cr=\"{panel_radius}\" opacity=\"0.84\">
            <component type=\"text\" x=\"{int(gps_w * 0.08)}\" y=\"{int(gps_h * 0.12)}\" size=\"{label_size}\" rgb=\"{theme.accent_rgb}\">GPS LOCK</component>
            <composite x=\"{int(gps_w * 0.08)}\" y=\"{int(gps_h * 0.42)}\">
                <component type=\"gps-lock-icon\" size=\"{small_metric_size}\"/>
            </composite>
            <component type=\"metric\" x=\"{int(gps_w * 0.22)}\" y=\"{int(gps_h * 0.40)}\" metric=\"lat\" dp=\"5\" size=\"{label_size}\" cache=\"False\" rgb=\"{theme.text_rgb}\"/>
            <component type=\"metric\" x=\"{int(gps_w * 0.22)}\" y=\"{int(gps_h * 0.67)}\" metric=\"lon\" dp=\"5\" size=\"{label_size}\" cache=\"False\" rgb=\"{theme.text_rgb}\"/>
        </frame>
    </composite>

{map_components.rstrip()}
</layout>
"""
