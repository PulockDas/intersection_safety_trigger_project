"""
trigger_parser.py — Helpers for reading and inspecting trigger JSON files.

All operations are read-only; nothing is extracted to disk.
Used by notebooks/02_trigger_log_deep_inspection.ipynb.
"""

from __future__ import annotations

import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from radar_parser import (
    safe_json_load_from_zip,
    decode_payload_if_needed,
    find_timestamp_fields,
    guess_timestamp_format,
    TIMESTAMP_FIELD_NAMES,
)

# ── File-pattern for trigger output JSON ─────────────────────────────────────
TRIGGER_FILE_PATTERN = re.compile(
    r"Radars_Run_(\d+)_traffic-triggers-output\.json$", re.IGNORECASE
)

# ── Target semantic fields to search for inside trigger payload ───────────────
TRIGGER_SEMANTIC_FIELDS: set[str] = {
    "reference_name", "associated_lane", "associated_zone", "associated_sensor",
    "traffic_triggers", "trigger_outputs", "trigger_id", "trigger_type",
    "detector_id", "lane_id", "zone_id", "sensor_id",
    "name", "lane", "zone", "sensor",
}

# ── Known container field names that may hold a list of trigger events ────────
TRIGGER_LIST_FIELDS: list[str] = [
    "traffic_triggers", "trigger_outputs", "triggers",
    "events", "activations", "trigger_events", "outputs", "detections",
]

# ── Radar file pattern (reused for cross-check) ───────────────────────────────
RADAR_FILE_PATTERN = re.compile(
    r"Radars_Run_(\d+)_sensor(\d+)\.json$", re.IGNORECASE
)


# ─────────────────────────────────────────────────────────────────────────────
# Zip scanning
# ─────────────────────────────────────────────────────────────────────────────

def find_trigger_files_in_zip(zip_path: Path) -> list[dict[str, Any]]:
    """
    Scan a zip's central directory and return a record for every
    Radars_Run_XXXX_traffic-triggers-output.json file found.
    """
    results: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                m = TRIGGER_FILE_PATTERN.search(info.filename)
                if m:
                    results.append({
                        "zip_name":      zip_path.name,
                        "internal_path": info.filename,
                        "run_id":        m.group(1).zfill(4),
                        "file_size_kb":  round(info.file_size / 1024, 1),
                    })
    except zipfile.BadZipFile as exc:
        print(f"[ERROR] Cannot open {zip_path.name}: {exc}")
    return results


def find_radar_path_for_run(zip_path: Path, run_id: str, sensor_id: int = 1) -> str | None:
    """
    Find the internal path of a radar sensor file for a given run in a zip.
    run_id should be zero-padded (e.g. '0166').
    Returns the internal path string, or None if not found.
    """
    run_num = str(int(run_id))  # Strip leading zeros for filename matching
    pattern = re.compile(
        rf"Radars_Run_{re.escape(run_num)}_sensor{sensor_id}\.json$",
        re.IGNORECASE,
    )
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                if not info.is_dir() and pattern.search(info.filename):
                    return info.filename
    except zipfile.BadZipFile:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Nested field searching
# ─────────────────────────────────────────────────────────────────────────────

def find_field_paths_recursive(
    obj: Any,
    target_fields: set[str],
    prefix: str = "",
    depth: int = 0,
    max_depth: int = 8,
) -> dict[str, list[tuple[str, Any]]]:
    """
    Recursively search an object for any of the target field names.

    Returns {field_name: [(dotted_path, value), ...]} for all occurrences found.
    List items are sampled (first 5) to avoid memory issues on large payloads.
    """
    found: dict[str, list] = defaultdict(list)
    if depth > max_depth:
        return dict(found)

    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            if k in target_fields:
                found[k].append((path, v))
            if isinstance(v, (dict, list)):
                sub = find_field_paths_recursive(v, target_fields, path, depth + 1, max_depth)
                for field, hits in sub.items():
                    found[field].extend(hits)
    elif isinstance(obj, list):
        for i, item in enumerate(obj[:5]):   # sample first 5 list elements
            path = f"{prefix}[{i}]"
            sub = find_field_paths_recursive(item, target_fields, path, depth + 1, max_depth)
            for field, hits in sub.items():
                found[field].extend(hits)

    return dict(found)


# ─────────────────────────────────────────────────────────────────────────────
# Trigger event extraction
# ─────────────────────────────────────────────────────────────────────────────

def _extract_from_item(item: dict, base_event: dict) -> list[dict]:
    """
    From one dict inside a trigger container, build one or more event rows.
    Handles nested trigger_outputs lists.
    """
    events = []

    # Copy known semantic fields from this item
    event = dict(base_event)
    for field in ("reference_name", "associated_lane", "associated_zone",
                  "associated_sensor", "trigger_id", "trigger_type",
                  "lane_id", "zone_id", "sensor_id"):
        if item.get(field) is not None:
            event[field] = item[field]

    # If nested trigger_outputs exist, recurse one level
    nested = item.get("trigger_outputs") or item.get("outputs")
    if isinstance(nested, list) and nested:
        for j, nitem in enumerate(nested):
            if isinstance(nitem, dict):
                nevent = dict(event)
                nevent["trigger_index"] = j
                for field in ("reference_name", "associated_lane",
                              "associated_zone", "associated_sensor"):
                    if nitem.get(field) is not None:
                        nevent[field] = nitem[field]
                events.append(nevent)
        return events

    events.append(event)
    return events


def extract_trigger_events(payload: Any) -> list[dict]:
    """
    Extract a list of normalized trigger event dicts from a decoded payload dict.

    Each returned dict has at minimum:
        reference_name, associated_lane, associated_zone, associated_sensor,
        trigger_output_index, trigger_index, container_field
    (values may be None if not found).
    """
    if not isinstance(payload, dict):
        return []

    events: list[dict] = []

    # Try known list container fields
    for container_field in TRIGGER_LIST_FIELDS:
        container = payload.get(container_field)
        if not isinstance(container, list) or not container:
            continue
        for i, item in enumerate(container):
            if not isinstance(item, dict):
                continue
            base = {
                "trigger_output_index": i,
                "trigger_index":        0,
                "container_field":      container_field,
                "reference_name":       None,
                "associated_lane":      None,
                "associated_zone":      None,
                "associated_sensor":    None,
            }
            events.extend(_extract_from_item(item, base))
        if events:
            return events   # return on first container field that yields results

    # Fallback: payload itself may be a single trigger event dict
    if any(payload.get(f) is not None for f in
           ("reference_name", "associated_lane", "associated_zone")):
        events.append({
            "trigger_output_index": 0,
            "trigger_index":        0,
            "container_field":      "payload_direct",
            "reference_name":       payload.get("reference_name"),
            "associated_lane":      payload.get("associated_lane"),
            "associated_zone":      payload.get("associated_zone"),
            "associated_sensor":    payload.get("associated_sensor"),
        })

    return events


def normalize_trigger_record(
    record: dict,
    run_id: str,
    zip_name: str,
) -> list[dict]:
    """
    Given one MQTT record from a trigger file, return a list of
    normalized trigger event rows (one row per trigger event found).
    Returns an empty list if the record has no trigger events.
    """
    received_at = record.get("receivedAt", "")
    topic       = record.get("topic", "")
    raw_payload = record.get("payload")

    if raw_payload is None:
        return []

    payload, encoding = decode_payload_if_needed(raw_payload)
    if not isinstance(payload, dict):
        return []

    # Find payload timestamp
    payload_ts: Any = None
    for ts_key in ("timestamp", "time", "capture_time", "event_time"):
        if payload.get(ts_key) is not None:
            payload_ts = payload[ts_key]
            break

    trigger_events = extract_trigger_events(payload)
    rows = []
    for ev in trigger_events:
        row = {
            "run_id":               run_id,
            "zip_name":             zip_name,
            "receivedAt":           received_at,
            "payload_timestamp":    payload_ts,
            "topic":                topic,
            "reference_name":       ev.get("reference_name"),
            "associated_lane":      ev.get("associated_lane"),
            "associated_zone":      ev.get("associated_zone"),
            "associated_sensor":    ev.get("associated_sensor"),
            "trigger_output_index": ev.get("trigger_output_index", 0),
            "trigger_index":        ev.get("trigger_index", 0),
            "container_field":      ev.get("container_field", ""),
        }
        rows.append(row)
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Topic string analysis
# ─────────────────────────────────────────────────────────────────────────────

def parse_topic_string(topic: str) -> dict[str, Any]:
    """
    Attempt to extract semantic components from a slash-delimited MQTT topic.

    Returns a dict with:
        raw_topic, parts, depth,
        likely_sensor, likely_lane, likely_zone, likely_intersection
    """
    parts = [p for p in topic.split("/") if p]
    result: dict[str, Any] = {
        "raw_topic":            topic,
        "parts":                parts,
        "depth":                len(parts),
        "likely_sensor":        None,
        "likely_lane":          None,
        "likely_zone":          None,
        "likely_intersection":  None,
    }
    for part in parts:
        pl = part.lower()
        if result["likely_sensor"] is None and re.search(r"sensor\d+", pl):
            result["likely_sensor"] = part
        if result["likely_lane"] is None and re.search(r"lane\d*", pl):
            result["likely_lane"] = part
        if result["likely_zone"] is None and re.search(r"zone\d*", pl):
            result["likely_zone"] = part
        if result["likely_intersection"] is None and re.search(
            r"(intersection|site|location|isc)\w*", pl
        ):
            result["likely_intersection"] = part
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Timestamp parsing
# ─────────────────────────────────────────────────────────────────────────────

def iso_to_epoch_ms(ts: Any) -> float | None:
    """
    Convert an ISO 8601 timestamp string (or numeric) to epoch milliseconds.
    Returns None if conversion fails.
    """
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        # Already numeric — detect if seconds or milliseconds
        return float(ts) if ts > 1e12 else float(ts) * 1000
    if not isinstance(ts, str):
        return None
    try:
        import datetime
        s = ts.strip()
        # Normalise +00:00 → +0000 for strptime
        s_norm = re.sub(r"([+-]\d{2}):(\d{2})$", r"\1\2", s.rstrip("Z"))
        if "T" in s_norm:
            if re.search(r"[+-]\d{4}$", s_norm):
                dt = datetime.datetime.strptime(s_norm, "%Y-%m-%dT%H:%M:%S%z")
            else:
                dt = datetime.datetime.fromisoformat(s_norm)
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt.timestamp() * 1000
    except Exception:
        pass
    return None
