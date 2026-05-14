"""
radar_parser.py — Helpers for reading and inspecting radar JSON files.

All operations are read-only; nothing is extracted to disk.
Used by notebooks/01_radar_json_schema_inspection.ipynb and later notebooks.
"""

from __future__ import annotations

import base64
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

# ── File-pattern for radar sensor JSON ───────────────────────────────────────
RADAR_FILE_PATTERN = re.compile(
    r"Radars_Run_(\d+)_sensor(\d+)\.json$", re.IGNORECASE
)

# ── Fields to probe inside each detection object ─────────────────────────────
OBJECT_FIELDS_TO_CHECK: list[str] = [
    # Identity / tracking
    "id", "object_id", "track_id",
    # Classification
    "class", "classification", "type", "label", "category",
    # Kinematics
    "speed", "velocity", "speed_magnitude",
    "heading", "course", "orientation",
    # Dimensions
    "length", "width", "height",
    # Lane / zone context
    "closest_lane", "lane", "lane_id",
    "within_zone", "zone", "zone_id",
    # Position
    "position_front", "position_facing", "position",
    "x", "y", "z",
    # Quality
    "tracking_status", "tracking_quality", "confidence",
]

# ── Known names for the object-list field inside payload ─────────────────────
OBJECT_LIST_FIELDS: list[str] = [
    "objects", "detections", "tracks", "targets",
    "radar_objects", "object_list", "detected_objects",
    "vehicleList", "vehicle_list",
]

# ── Field names that look like timestamps ────────────────────────────────────
TIMESTAMP_FIELD_NAMES: set[str] = {
    "timestamp", "time", "receivedAt", "received_at",
    "capture_time", "frame_time", "epoch", "unix_time",
    "created_at", "updated_at", "event_time",
}


# ─────────────────────────────────────────────────────────────────────────────
# Zip / file I/O
# ─────────────────────────────────────────────────────────────────────────────

def find_radar_files_in_zip(zip_path: Path) -> list[dict[str, Any]]:
    """
    Scan a zip's central directory and return a record for every
    Radars_Run_XXXX_sensorN.json file found.

    Returns a list of dicts with keys:
        zip_name, internal_path, run_id, sensor_id, file_size_kb
    """
    results: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                m = RADAR_FILE_PATTERN.search(info.filename)
                if m:
                    results.append({
                        "zip_name":      zip_path.name,
                        "internal_path": info.filename,
                        "run_id":        m.group(1).zfill(4),
                        "sensor_id":     int(m.group(2)),
                        "file_size_kb":  round(info.file_size / 1024, 1),
                    })
    except zipfile.BadZipFile as exc:
        print(f"[ERROR] Cannot open {zip_path.name}: {exc}")
    return results


def safe_json_load_from_zip(zip_path: Path, internal_path: str) -> Any | None:
    """
    Read and parse a JSON file stored inside a zip archive.
    Returns the parsed Python object, or None on any error.
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            with zf.open(internal_path) as fh:
                return json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"  [WARN] JSON decode error — {internal_path}: {exc}")
    except KeyError:
        print(f"  [WARN] Path not found in zip — {internal_path}")
    except Exception as exc:
        print(f"  [WARN] Unexpected error reading {internal_path}: {exc}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Payload decoding
# ─────────────────────────────────────────────────────────────────────────────

def decode_payload_if_needed(payload: Any) -> tuple[Any, str]:
    """
    Normalise a raw payload field to a Python object.

    Returns (decoded_object, encoding_label) where encoding_label is one of:
        'dict_or_list'      already a Python dict or list
        'string_json'       was a JSON-encoded string
        'base64_json'       was a base64-encoded JSON string
        'plain_string'      a string that is not JSON
        'bytes_undecodable' raw bytes that could not be decoded
        'none'              payload was None or missing
        'unknown_<type>'    unrecognised type
    """
    if payload is None:
        return None, "none"
    if isinstance(payload, (dict, list)):
        return payload, "dict_or_list"
    if isinstance(payload, bytes):
        try:
            payload = payload.decode("utf-8")
        except Exception:
            return None, "bytes_undecodable"
    if isinstance(payload, str):
        stripped = payload.strip()
        # Try plain JSON first
        if stripped.startswith(("{", "[")):
            try:
                return json.loads(stripped), "string_json"
            except json.JSONDecodeError:
                pass
        # Try base64-encoded JSON
        try:
            decoded_bytes = base64.b64decode(stripped)
            return json.loads(decoded_bytes.decode("utf-8")), "base64_json"
        except Exception:
            pass
        return payload, "plain_string"
    return payload, f"unknown_{type(payload).__name__}"


# ─────────────────────────────────────────────────────────────────────────────
# Schema walking
# ─────────────────────────────────────────────────────────────────────────────

def inspect_nested_schema(
    obj: Any,
    prefix: str = "",
    max_depth: int = 5,
    depth: int = 0,
) -> dict[str, str]:
    """
    Return a flat dict mapping dotted key paths to Python type names.

    Example output:
        {
            "receivedAt":            "str",
            "payload":               "dict",
            "payload.objects":       "list[dict]",
            "payload.objects[0].id": "int",
            ...
        }
    """
    schema: dict[str, str] = {}
    if depth > max_depth:
        return schema
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            schema[path] = type(v).__name__
            if isinstance(v, (dict, list)):
                schema.update(
                    inspect_nested_schema(v, path, max_depth, depth + 1)
                )
    elif isinstance(obj, list):
        if obj:
            list_path = f"{prefix}[]"
            schema[list_path] = f"list[{type(obj[0]).__name__}]"
            schema.update(
                inspect_nested_schema(obj[0], f"{prefix}[0]", max_depth, depth + 1)
            )
    return schema


def flatten_keys_sample(
    records: list[Any],
    max_records: int = 10,
    max_depth: int = 5,
) -> Counter:
    """
    Return a Counter of {dotted_path: number_of_records_containing_it}
    across the first max_records records.
    Useful for finding which fields are consistently present.
    """
    counter: Counter = Counter()
    for rec in records[:max_records]:
        schema = inspect_nested_schema(rec, max_depth=max_depth)
        for path in schema:
            counter[path] += 1
    return counter


# ─────────────────────────────────────────────────────────────────────────────
# Object extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_object_list(payload: Any) -> list[dict] | None:
    """
    Search a decoded payload for the object detection list.
    Tries all known field names; returns the first non-empty list of dicts,
    or None if not found.
    """
    if not isinstance(payload, dict):
        return None
    for field in OBJECT_LIST_FIELDS:
        val = payload.get(field)
        if isinstance(val, list) and val and isinstance(val[0], dict):
            return val
    return None


def get_object_list_field_name(payload: dict) -> str | None:
    """Return the name of the field that holds the object list, or None."""
    for field in OBJECT_LIST_FIELDS:
        val = payload.get(field)
        if isinstance(val, list) and val and isinstance(val[0], dict):
            return field
    return None


def check_object_fields(obj: dict) -> dict[str, Any]:
    """
    Given one detection object dict, return a mapping of
    every OBJECT_FIELDS_TO_CHECK name to its value (None if absent).
    """
    return {field: obj.get(field) for field in OBJECT_FIELDS_TO_CHECK}


# ─────────────────────────────────────────────────────────────────────────────
# Timestamp helpers
# ─────────────────────────────────────────────────────────────────────────────

def find_timestamp_fields(
    obj: Any,
    prefix: str = "",
    depth: int = 0,
    max_depth: int = 5,
) -> dict[str, Any]:
    """
    Recursively find all timestamp-like fields inside an object.
    Returns a dict of {dotted_path: raw_value}.
    """
    found: dict[str, Any] = {}
    if depth > max_depth:
        return found
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            if k in TIMESTAMP_FIELD_NAMES:
                found[path] = v
            if isinstance(v, (dict, list)):
                found.update(find_timestamp_fields(v, path, depth + 1, max_depth))
    elif isinstance(obj, list) and obj:
        found.update(
            find_timestamp_fields(obj[0], f"{prefix}[0]", depth + 1, max_depth)
        )
    return found


def guess_timestamp_format(value: Any) -> str:
    """
    Return a human-readable guess of a timestamp value's format.
    """
    if value is None:
        return "None"
    if isinstance(value, str):
        if "T" in value and ("+0" in value or "Z" in value or "+00" in value):
            return "ISO-8601 string (timezone-aware)"
        if "T" in value:
            return "ISO-8601 string (no tz)"
        if re.match(r"^\d{4}-\d{2}-\d{2}", value):
            return "date string"
        return f"plain string"
    if isinstance(value, float):
        if value > 1e12:
            return "Unix milliseconds (float)"
        if value > 1e9:
            return "Unix seconds (float)"
    if isinstance(value, int):
        if value > 1e12:
            return "Unix milliseconds (int)"
        if value > 1e9:
            return "Unix seconds (int)"
    return f"unknown ({type(value).__name__})"
