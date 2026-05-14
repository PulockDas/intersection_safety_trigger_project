"""
trigger_parser.py — Helpers for reading and inspecting trigger JSON files.

All operations are read-only; nothing is extracted to disk.
Used by notebooks/02_trigger_log_deep_inspection.ipynb and 02b validation.

Trigger events live at:
    payload["trigger_outputs"][i]["traffic_triggers"][j]
Per-event wall time is ``payload["timestamp"]`` (not MQTT ``receivedAt``).
"""

from __future__ import annotations

import re
import zipfile
from collections import defaultdict
from datetime import timezone
from pathlib import Path
from typing import Any

from dateutil import parser as dateutil_parser

from radar_parser import decode_payload_if_needed

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

def extract_trigger_events(payload: Any) -> list[dict]:
    """
    Extract trigger event dicts from a decoded payload.

    Walks ``payload["trigger_outputs"][i]["traffic_triggers"][j]`` only.
    Each dict includes trigger_output_index, trigger_index, semantic fields,
    and container_field ``trigger_outputs.traffic_triggers``.
    """
    if not isinstance(payload, dict):
        return []

    outputs = payload.get("trigger_outputs")
    if not isinstance(outputs, list) or not outputs:
        return []

    events: list[dict] = []
    for i, block in enumerate(outputs):
        if not isinstance(block, dict):
            continue
        triggers = block.get("traffic_triggers")
        if not isinstance(triggers, list):
            continue
        for j, trig in enumerate(triggers):
            if not isinstance(trig, dict):
                continue
            events.append({
                "trigger_output_index": i,
                "trigger_index":        j,
                "container_field":      "trigger_outputs.traffic_triggers",
                "reference_name":       trig.get("reference_name"),
                "associated_lane":      trig.get("associated_lane"),
                "associated_zone":      trig.get("associated_zone"),
                "associated_sensor":    trig.get("associated_sensor"),
            })
    return events


def mqtt_record_has_nonempty_traffic_triggers(record: dict) -> bool:
    """True if decoded payload has at least one non-empty ``traffic_triggers`` list."""
    raw = record.get("payload")
    if raw is None:
        return False
    payload, _enc = decode_payload_if_needed(raw)
    if not isinstance(payload, dict):
        return False
    outs = payload.get("trigger_outputs")
    if not isinstance(outs, list):
        return False
    for block in outs:
        if not isinstance(block, dict):
            continue
        tt = block.get("traffic_triggers")
        if isinstance(tt, list) and len(tt) > 0:
            return True
    return False


def normalize_trigger_record(
    record: dict,
    run_id: str,
    zip_name: str,
    source_file: str = "",
) -> list[dict]:
    """
    Given one MQTT record from a trigger file, return a list of
    normalized trigger event rows (one row per trigger event found).
    Uses ``payload["timestamp"]`` only for wall time (per-event trigger time).
    """
    topic = record.get("topic", "")
    raw_payload = record.get("payload")

    if raw_payload is None:
        return []

    payload, _encoding = decode_payload_if_needed(raw_payload)
    if not isinstance(payload, dict):
        return []

    payload_ts: Any = payload.get("timestamp")
    epoch_ms = parse_payload_timestamp_to_utc_epoch_ms(payload_ts)

    trigger_events = extract_trigger_events(payload)
    rows: list[dict] = []
    for ev in trigger_events:
        rows.append({
            "run_id":                     run_id,
            "zip_name":                   zip_name,
            "source_file":                source_file,
            "topic":                      topic,
            "payload_timestamp":          payload_ts,
            "payload_timestamp_epoch_ms": epoch_ms,
            "reference_name":             ev.get("reference_name"),
            "associated_lane":            ev.get("associated_lane"),
            "associated_zone":            ev.get("associated_zone"),
            "associated_sensor":          ev.get("associated_sensor"),
            "trigger_output_index":       ev.get("trigger_output_index", 0),
            "trigger_index":              ev.get("trigger_index", 0),
        })
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

def parse_payload_timestamp_to_utc_epoch_ms(ts: Any) -> float | None:
    """
    Parse trigger ``payload["timestamp"]`` to Unix epoch milliseconds in UTC.

    Supports ISO-8601 with ``T``, space-separated datetimes, optional timezones,
    and numeric epoch (seconds if magnitude < 1e12, else ms).
    Naive datetimes are treated as UTC.
    """
    if ts is None or isinstance(ts, bool):
        return None
    if isinstance(ts, (int, float)):
        v = float(ts)
        if v != v:  # NaN
            return None
        return v if v > 1e12 else v * 1000.0
    if not isinstance(ts, str):
        return None
    s = ts.strip()
    if not s:
        return None
    try:
        dt = dateutil_parser.parse(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.timestamp() * 1000.0
    except (ValueError, TypeError, OverflowError):
        return None


def iso_to_epoch_ms(ts: Any) -> float | None:
    """Backward-compatible name; delegates to :func:`parse_payload_timestamp_to_utc_epoch_ms`."""
    return parse_payload_timestamp_to_utc_epoch_ms(ts)
