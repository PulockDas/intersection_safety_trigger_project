"""
config.py — Project-wide constants.

Tune MAX_SAMPLE_PATHS and MAX_TRIGGER_FILES_TO_INSPECT to control
how much data each scan notebook reads into memory.
"""

import re

# ── Scan limits ───────────────────────────────────────────────────────────────
MAX_SAMPLE_PATHS             = 200   # max internal paths saved to CSV per zip
MAX_TRIGGER_FILES_TO_INSPECT = 3     # max trigger JSON files read for semantics probe

# ── File-pattern registry ─────────────────────────────────────────────────────
# Each key is a short label; value is a compiled regex matched against
# the internal zip path (basename only, case-insensitive).
FILE_PATTERNS: dict[str, re.Pattern] = {
    "gt_csv": re.compile(
        r"Run_\d+_GT\.csv$", re.IGNORECASE
    ),
    "radar_sensor_json": re.compile(
        r"Radars_Run_\d+_sensor\d+\.json$", re.IGNORECASE
    ),
    "traffic_trigger_json": re.compile(
        r"Radars_Run_\d+_traffic-triggers-output\.json$", re.IGNORECASE
    ),
    "v2xhub_csv": re.compile(
        r"V2XHubSensor_Run_\d+\.csv$", re.IGNORECASE
    ),
    "visual_camera_timing": re.compile(
        r"VisualCamera.*_Run_\d+_frame-timing\.csv$", re.IGNORECASE
    ),
    "thermal_camera_timing": re.compile(
        r"ThermalCamera.*_Run_\d+_frame-timing\.csv$", re.IGNORECASE
    ),
    "isc_timing_csv": re.compile(
        r"ISC_Run_\d+_ISC_all_timing\.csv$", re.IGNORECASE
    ),
    "v2xhub_timing_csv": re.compile(
        r"ISC_Run_\d+_v2xhub_timing\.csv$", re.IGNORECASE
    ),
    "labels_csv": re.compile(
        r"labels.*\.csv$", re.IGNORECASE
    ),
    "video_file": re.compile(
        r"\.(mp4|avi|mkv|mov|h264|ts)$", re.IGNORECASE
    ),
    "pcap_file": re.compile(
        r"\.pcap(ng)?$", re.IGNORECASE
    ),
}

# ── Run-folder pattern ────────────────────────────────────────────────────────
RUN_PATTERN = re.compile(r"Run_(\d+)", re.IGNORECASE)

# ── Heavy-file labels (flagged in summary but not processed) ──────────────────
HEAVY_FILE_LABELS = {"video_file", "pcap_file"}

# ── Expected file labels (used to generate missing-file warnings) ─────────────
EXPECTED_LABELS = {
    "gt_csv",
    "radar_sensor_json",
    "traffic_trigger_json",
    "v2xhub_csv",
    "visual_camera_timing",
    "thermal_camera_timing",
    "isc_timing_csv",
}
