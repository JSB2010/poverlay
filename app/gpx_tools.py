from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
import xml.etree.ElementTree as ET

GPX_NS = "http://www.topografix.com/GPX/1/1"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SPEED_FACTORS = {
    "mps": 1.0,
    "mph": 2.2369362920544,
    "kph": 3.6,
    "knots": 1.9438444924406,
}


def _parse_timestamp(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _local_name(tag: str) -> str:
    return tag[tag.find("}") + 1 :] if "}" in tag else tag


def _namespace(tag: str) -> str | None:
    if "}" not in tag or not tag.startswith("{"):
        return None
    return tag[1 : tag.find("}")]


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # Fast distance estimate; sufficient for speed-unit inference.
    radius_m = 6_371_000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return 2.0 * radius_m * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def _extract_trackpoints(root: ET.Element) -> list[dict]:
    points: list[dict] = []
    for node in root.iter():
        if _local_name(node.tag) != "trkpt":
            continue

        lat = _parse_number(node.attrib.get("lat"))
        lon = _parse_number(node.attrib.get("lon"))
        time_value: datetime | None = None
        speed_element = None
        speed_value = None
        speed_ns = None

        extensions = next((child for child in list(node) if _local_name(child.tag) == "extensions"), None)
        for child in list(node):
            if _local_name(child.tag) == "time" and child.text:
                time_value = _parse_timestamp(child.text)

        if extensions is not None:
            for ext in extensions.iter():
                if ext is extensions:
                    continue
                lname = _local_name(ext.tag)
                if lname == "speed":
                    speed_element = ext
                    speed_value = _parse_number(ext.text)
                    speed_ns = _namespace(ext.tag)
                    continue

                attr_speed = _parse_number(ext.attrib.get("speed"))
                if attr_speed is not None:
                    speed_value = attr_speed
                    if speed_ns is None:
                        speed_ns = _namespace(ext.tag)

        points.append(
            {
                "node": node,
                "extensions": extensions,
                "lat": lat,
                "lon": lon,
                "time": time_value,
                "speed_raw": speed_value,
                "speed_element": speed_element,
                "speed_ns": speed_ns,
            }
        )
    return points


def _infer_speed_unit(points: list[dict], preferred_unit: str) -> str:
    if preferred_unit in SPEED_FACTORS and preferred_unit != "auto":
        return preferred_unit

    ratios: list[float] = []
    for current, nxt in zip(points, points[1:]):
        speed_raw = current.get("speed_raw")
        if speed_raw is None:
            continue

        time_a = current.get("time")
        time_b = nxt.get("time")
        lat_a = current.get("lat")
        lon_a = current.get("lon")
        lat_b = nxt.get("lat")
        lon_b = nxt.get("lon")

        if None in (time_a, time_b, lat_a, lon_a, lat_b, lon_b):
            continue

        dt = (time_b - time_a).total_seconds()
        if dt <= 0 or dt > 10:
            continue

        dist_m = _haversine_m(lat_a, lon_a, lat_b, lon_b)
        ground_speed_mps = dist_m / dt if dt > 0 else 0.0
        if ground_speed_mps < 0.8:
            continue

        ratios.append(speed_raw / ground_speed_mps)

    if ratios:
        ratios.sort()
        median_ratio = ratios[len(ratios) // 2]
        unit_by_ratio = min(
            SPEED_FACTORS.keys(),
            key=lambda unit_name: abs(SPEED_FACTORS[unit_name] - median_ratio),
        )
        rel_error = abs(SPEED_FACTORS[unit_by_ratio] - median_ratio) / max(SPEED_FACTORS[unit_by_ratio], 1e-6)
        if rel_error < 0.35:
            return unit_by_ratio

    raw_speeds = [p["speed_raw"] for p in points if p.get("speed_raw") is not None]
    if raw_speeds:
        max_raw = max(raw_speeds)
        if max_raw > 90:
            return "kph"
        if max_raw > 45:
            return "mph"

    return "mps"


def _normalize_speed_extensions(root: ET.Element, speed_unit: str = "auto") -> None:
    # gopro-overlay expects extension elements named "speed" in m/s.
    points = _extract_trackpoints(root)
    source_unit = _infer_speed_unit(points, speed_unit)
    factor = SPEED_FACTORS[source_unit]

    for point in points:
        extensions = point["extensions"]
        speed_value = point["speed_raw"]
        if extensions is None or speed_value is None:
            continue

        speed_element = point["speed_element"]
        speed_ns = point["speed_ns"]
        speed_mps = speed_value / factor

        if speed_element is None:
            speed_tag = f"{{{speed_ns}}}speed" if speed_ns else "speed"
            speed_element = ET.SubElement(extensions, speed_tag)

        speed_element.text = f"{speed_mps:.6f}"


def shift_gpx_timestamps(source_path: Path, destination_path: Path, seconds: float, speed_unit: str = "auto") -> Path:
    root = ET.parse(source_path).getroot()
    _normalize_speed_extensions(root, speed_unit=speed_unit)

    if abs(seconds) >= 1e-9:
        delta = timedelta(seconds=seconds)
        for node in root.iter():
            if not node.tag.endswith("time") or node.text is None:
                continue
            dt = _parse_timestamp(node.text)
            if dt is None:
                continue
            shifted = dt + delta
            shifted_utc = shifted.astimezone(timezone.utc)
            node.text = shifted_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    ET.register_namespace("", GPX_NS)
    ET.register_namespace("xsi", XSI_NS)
    ET.register_namespace("slp", "http://www.gpstrackeditor.com/xmlschemas/General/1")

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(destination_path, encoding="utf-8", xml_declaration=True)
    return destination_path
