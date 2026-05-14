"""
zip_utils.py — Low-level utilities for inspecting zip archives.

All functions are read-only: nothing is extracted to disk.
"""

from __future__ import annotations

import json
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from config import FILE_PATTERNS, RUN_PATTERN


# ─────────────────────────────────────────────────────────────────────────────
# Core zip scan
# ─────────────────────────────────────────────────────────────────────────────

def iter_zip_names(zf: zipfile.ZipFile):
    """Yield every file name stored inside a zip (directories excluded)."""
    for info in zf.infolist():
        if not info.is_dir():
            yield info.filename


def scan_zip(zip_path: Path, max_sample_paths: int = 200) -> dict[str, Any]:
    """
    Scan a zip archive and return a structured summary dict.

    Nothing is extracted; only the central directory of the zip is read.

    Parameters
    ----------
    zip_path : Path
        Absolute path to the .zip file.
    max_sample_paths : int
        Maximum number of internal paths to collect for the sample CSV.

    Returns
    -------
    dict with keys:
        zip_name, zip_size_gb, total_files, extension_counts (Counter),
        run_ids (sorted list of zero-padded strings), pattern_counts (dict),
        sample_paths (list), trigger_file_paths (list)
    """
    result: dict[str, Any] = {
        "zip_name":           zip_path.name,
        "zip_size_gb":        round(zip_path.stat().st_size / 1_000_000_000, 3),
        "total_files":        0,
        "extension_counts":   Counter(),
        "run_ids":            set(),
        "pattern_counts":     {k: 0 for k in FILE_PATTERNS},
        "sample_paths":       [],
        "trigger_file_paths": [],
    }

    print(f"  [scan] Opening {zip_path.name} …")

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = list(iter_zip_names(zf))
    except zipfile.BadZipFile as exc:
        print(f"  [ERROR] Could not open zip: {exc}")
        return result

    result["total_files"] = len(names)
    print(f"  [scan] Found {len(names):,} internal entries — scanning …")

    for name in names:
        # File extension
        ext = Path(name).suffix.lower() or "(no ext)"
        result["extension_counts"][ext] += 1

        # Run ID extraction
        m = RUN_PATTERN.search(name)
        if m:
            result["run_ids"].add(m.group(1).zfill(4))

        # Named pattern matching
        for label, regex in FILE_PATTERNS.items():
            if regex.search(name):
                result["pattern_counts"][label] += 1
                if label == "traffic_trigger_json":
                    result["trigger_file_paths"].append(name)

        # Sample path collection
        if len(result["sample_paths"]) < max_sample_paths:
            result["sample_paths"].append(name)

    result["run_ids"] = sorted(result["run_ids"])
    print(f"  [scan] Done — {len(result['run_ids'])} unique Run IDs detected")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# JSON reading from inside zip
# ─────────────────────────────────────────────────────────────────────────────

def read_json_from_zip(zip_path: Path, internal_path: str) -> Any | None:
    """
    Read and parse a single JSON file stored inside a zip archive.

    Returns the parsed Python object, or None if any error occurs.
    Does not extract the file to disk.
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            with zf.open(internal_path) as fh:
                return json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"  [WARN] JSON parse error in {internal_path}: {exc}")
        return None
    except KeyError:
        print(f"  [WARN] Path not found in zip: {internal_path}")
        return None
    except Exception as exc:
        print(f"  [WARN] Unexpected error reading {internal_path}: {exc}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Trigger semantics probe
# ─────────────────────────────────────────────────────────────────────────────

_SAMPLE_FIELDS = {
    "reference_name":    "sample_reference_names",
    "associated_lane":   "sample_associated_lanes",
    "associated_zone":   "sample_associated_zones",
    "associated_sensor": "sample_associated_sensors",
    "timestamp":         "sample_timestamps",
}


def _harvest_fields(obj: Any, result: dict, depth: int, max_depth: int = 5) -> None:
    """
    Recursively walk a parsed JSON object and collect sample field values.

    Capped at max_depth to avoid runaway recursion on deeply nested payloads.
    """
    if depth > max_depth:
        return
    if isinstance(obj, dict):
        for field, target in _SAMPLE_FIELDS.items():
            if field in obj:
                val = str(obj[field])
                bucket = result[target]
                if val not in bucket and len(bucket) < 15:
                    bucket.append(val)
        for v in obj.values():
            if isinstance(v, (dict, list)):
                _harvest_fields(v, result, depth + 1, max_depth)
    elif isinstance(obj, list):
        for item in obj[:10]:          # sample first 10 list items only
            _harvest_fields(item, result, depth + 1, max_depth)


def probe_trigger_json(zip_path: Path, internal_path: str) -> dict[str, Any]:
    """
    Safely read one traffic-triggers-output.json from inside a zip and
    return a lightweight structure summary.

    This function inspects keys and samples field values without loading
    any large arrays fully into memory.

    Returns
    -------
    dict with keys:
        zip_name, path, top_level_type, top_level_keys, first_item_keys,
        sample_reference_names, sample_associated_lanes,
        sample_associated_zones, sample_associated_sensors,
        sample_timestamps, error
    """
    result: dict[str, Any] = {
        "zip_name":                zip_path.name,
        "path":                    internal_path,
        "top_level_type":          None,
        "top_level_keys":          [],
        "first_item_keys":         [],
        "sample_reference_names":  [],
        "sample_associated_lanes": [],
        "sample_associated_zones": [],
        "sample_associated_sensors": [],
        "sample_timestamps":       [],
        "error":                   None,
    }

    data = read_json_from_zip(zip_path, internal_path)
    if data is None:
        result["error"] = "failed to read or parse JSON"
        return result

    try:
        if isinstance(data, dict):
            result["top_level_type"] = "dict"
            result["top_level_keys"] = list(data.keys())
            # Attempt to identify a list payload under common key names
            for key in ("trigger_outputs", "triggers", "payload",
                        "data", "outputs", "events"):
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    if items and isinstance(items[0], dict):
                        result["first_item_keys"] = list(items[0].keys())
                    break
        elif isinstance(data, list):
            result["top_level_type"] = "list"
            result["top_level_keys"] = ["<list>"]
            if data and isinstance(data[0], dict):
                result["first_item_keys"] = list(data[0].keys())

        # Recursively harvest sample field values
        _harvest_fields(data, result, depth=0)

    except Exception as exc:
        result["error"] = str(exc)

    return result
