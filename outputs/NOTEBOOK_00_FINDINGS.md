# Notebook 00 — Findings Summary
**Physics-Informed Trigger Event Analysis — Urban Intersection Safety**  
**Dataset:** USDOT Intersection Safety Challenge Stage-1B  
**Date produced:** 2026-05-14  
**Source outputs:** `outputs/tables/training_zip_inventory.csv`, `training_zip_sample_paths.csv`, `sample_trigger_semantics_probe.csv`

---

## 1. Dataset Scale

| Metric | Value |
|--------|-------|
| Training zip files | 4 |
| Total compressed size | ~603 GB |
| Unique runs (total) | **800** (200 per zip) |
| Internal files per zip | ~6,700 |
| Recording dates | January – February 2024 |

---

## 2. Per-Run Folder Structure

Every run is stored as a flat folder `Run_XXXX/` inside the zip.
Two distinct run types exist (confirmed by matching file counts).

```
Run_XXXX/
│
│  ── present in ALL 800 runs ────────────────────────────────────────
│
├── VisualCamera1_Run_XXXX.mp4
├── VisualCamera2_Run_XXXX.mp4
│   ...
├── VisualCamera8_Run_XXXX.mp4                 (8 visual cameras)
├── VisualCamera1_Run_XXXX_frame-timing.csv
│   ...
├── VisualCamera8_Run_XXXX_frame-timing.csv
│
├── ThermalCamera1_Run_XXXX.mp4
│   ...
├── ThermalCamera5_Run_XXXX.mp4                (5 thermal cameras)
├── ThermalCamera1_Run_XXXX_frame-timing.csv
│   ...
├── ThermalCamera5_Run_XXXX_frame-timing.csv
│
├── Lidar1_Run_XXXX.pcap                       (2 LiDAR sensors — pcap)
├── Lidar2_Run_XXXX.pcap
│
└── ISC_Run_XXXX_ISC_all_timing.csv
│
│  ── present in ~50% of runs (RADAR RUNS only) ──────────────────────
│
├── Radars_Run_XXXX_sensor1.json
├── Radars_Run_XXXX_sensor2.json
├── Radars_Run_XXXX_sensor3.json
├── Radars_Run_XXXX_sensor4.json               (4 radar sensors)
│
├── Radars_Run_XXXX_traffic-triggers-output.json
│
├── V2XHubSensor_Run_XXXX.csv
├── V2XHubSPaT_Run_XXXX.pcap                  (Signal Phase & Timing capture)
└── ISC_Run_XXXX_v2xhub_timing.csv
```

---

## 3. The Two Run Types

File count arithmetic from the inventory reveals a clean 50/50 split.

### Radar Runs (~50% of all runs)

| Zip | Radar runs | Evidence |
|-----|-----------|---------|
| Training Data 1 | **104 / 200** | 416 radar JSONs ÷ 4 sensors = 104; trigger count = 104 (exact match) |
| Training Data 2 | **99 / 200** | 396 ÷ 4 = 99; trigger count = 99 |
| Training Data 3 | **100 / 200** | 400 ÷ 4 = 100; trigger count = 100 |
| Training Data 4 | **88 / 200** | 352 ÷ 4 = 88; trigger count = 88 |

**Key fact:** radar sensor count and trigger file count match exactly in every zip.
Radar presence ↔ trigger presence is a strict 1:1 relationship.

### Camera-Only Runs (~50% of all runs)

No radar, no trigger JSON, no V2XHub data.
Only: cameras (visual + thermal) + LiDAR + ISC all-timing.

> **Implication for modelling:** the trigger vs. non-trigger classifier trains exclusively
> on radar runs. Camera-only runs are structurally different and likely serve a
> different purpose (annotation, background, or diversity augmentation).

---

## 4. Sensor Suite Per Full Radar Run

| Sensor | Count | Format | Notes |
|--------|-------|--------|-------|
| Visual cameras | 8 | `.mp4` + `_frame-timing.csv` | VisualCamera1–8 |
| Thermal cameras | 5 | `.mp4` + `_frame-timing.csv` | ThermalCamera1–5 |
| Radar sensors | 4 | `.json` | sensor1–sensor4 |
| LiDAR sensors | 2 | `.pcap` | Lidar1, Lidar2 |
| V2XHub sensor | 1 | `.csv` | vehicle-to-infrastructure messages |
| V2XHub SPaT | 1 | `.pcap` | traffic signal phase & timing capture |
| Traffic triggers | 1 | `.json` | MQTT message log |
| ISC all-timing | 1 | `.csv` | synchronisation timing across all sensors |
| V2XHub timing | 1 | `.csv` | V2X-specific timing |

**Total per full run: 13 video files, 4 radar JSONs, 1 trigger JSON, 2 LiDAR pcaps, 1 SPaT pcap, ~5 CSVs.**

---

## 5. Trigger JSON Structure — Critical Finding

`Radars_Run_XXXX_traffic-triggers-output.json` is a **list of raw MQTT messages**,
not a structured trigger-event table.

### Outer envelope (confirmed by probe)

```json
[
  {
    "topic":      "<mqtt-topic-string>",
    "payload":    { ... },
    "qos":        0,
    "receivedAt": "2024-02-16T14:55:51+00:00",
    "retain":     false
  },
  ...
]
```

| Field | What it is | Status |
|-------|-----------|--------|
| `topic` | MQTT topic path — likely encodes sensor/zone/lane semantics (e.g. `/isc/radar/sensor1/zone3`) | **Present — decode in NB 02** |
| `payload` | Nested object — actual trigger data lives here | **Not yet decoded** |
| `qos` | MQTT quality-of-service flag (0/1/2) | Present |
| `receivedAt` | ISO 8601 message receipt timestamp | **Present — usable for alignment** |
| `retain` | MQTT retain flag | Present |

### Why semantic fields were not found in NB 00

The probe searched for `reference_name`, `associated_lane`, `associated_zone`,
and `associated_sensor` at top level and shallow nesting.
All four fields are almost certainly nested **inside `payload`**.
The `payload` object may itself be a JSON sub-object or a base64/string-encoded
JSON that requires explicit decoding.

---

## 6. Semantic Trigger Names — Current Status

**None extracted yet.** The shallow probe confirmed the MQTT envelope
but did not reach into `payload`.

| Field | Location | Status |
|-------|----------|--------|
| `reference_name` | Inside `payload` | Not yet found |
| `associated_lane` | Inside `payload` | Not yet found |
| `associated_zone` | Inside `payload` | Not yet found |
| `associated_sensor` | Inside `payload` | Not yet found |
| `topic` (MQTT path) | Top level | Present — likely contains semantic info |

> **Semantic warning (carried forward):**
> Traffic trigger `reference_name` values are not yet decoded.
> At this stage they should be treated as detector/zone activation identifiers,
> not confirmed safety event categories.

---

## 7. Ground-Truth (GT) File Alert

| Zip | GT CSV count |
|-----|-------------|
| Training Data 1 | **4** |
| Training Data 2 | 0 |
| Training Data 3 | 0 |
| Training Data 4 | 0 |

Only 4 GT files for 200 runs is far too low for one-file-per-run labels.
Likely explanations:
- The GT file covers **multiple runs in aggregate** (e.g. one per intersection site or one per challenge split).
- The filename does not match the expected pattern `Run_\d+_GT\.csv` and is named differently.
- GT labels may be encoded inside the `ISC_Run_XXXX_ISC_all_timing.csv` or another file type.

**Action needed in NB 01:** search for all `.csv` files that do not match any known
per-sensor pattern; inspect their headers to locate the actual label structure.

---

## 8. Unexpected Sensors Discovered

Two sensor types not in the original working assumptions appeared in the sample paths.

### LiDAR (every run)
- Files: `Lidar1_Run_XXXX.pcap`, `Lidar2_Run_XXXX.pcap`
- Format: pcap (raw packet capture of LiDAR point cloud stream)
- Relevance: 3D object geometry and distance — potential ground truth for radar object positions
- Action: heavy file, do not process in early notebooks; note for later fusion work

### V2XHub SPaT (radar runs only)
- File: `V2XHubSPaT_Run_XXXX.pcap`
- Contains: Signal Phase and Timing (SPaT) messages from the intersection controller
- Relevance: **very high** — knowing whether a traffic signal was red/green/yellow at the
  moment a trigger fired is direct evidence for interpreting what the trigger represents
- Action: decode SPaT pcap in a later notebook to align signal state with trigger timestamps

---

## 9. Implications for the Research Pipeline

| Stage | Insight from NB 00 |
|-------|--------------------|
| Data selection | Use radar runs only (~400 of 800); camera-only runs have no trigger signal |
| Trigger alignment | Use `receivedAt` timestamps from trigger MQTT messages to align with radar object data |
| Semantic decoding | Must read `payload` and `topic` fields in NB 02 before any trigger labelling |
| Feature engineering | 4 radar sensors per run → can compute multi-sensor object count, speed, distance, relative speed, TTC proxy, density/flow PDE residual |
| Signal context | V2XHub SPaT pcap provides signal phase context — strong future feature for physics-informed modelling |
| GT labels | Locate and understand GT file structure before constructing window labels in NB 03 |

---

## 10. Immediate Next Steps

### Notebook 01 — Radar JSON Schema Inspection
- Open one `Radars_Run_XXXX_sensor1.json` (directly from zip, no extraction)
- Print: top-level keys, object list schema, coordinate system, timestamp format, object ID structure
- Confirm which fields to use for: position, speed, heading, object class

### Notebook 02 — Trigger Log Deep Inspection
- Open one `traffic-triggers-output.json` and explicitly decode the `payload` field
- Print all `topic` strings (10–20 samples) — look for lane/zone/sensor path components
- Decode `reference_name`, `associated_lane`, `associated_zone` from inside `payload`
- Begin building a `topic → semantic label` mapping table

### Notebook 03 — Window Dataset Construction
- Align trigger `receivedAt` timestamps with radar object detection timestamps
- Build labelled windows: trigger window (positive) vs. no-trigger window (negative)
- Only use runs confirmed to have both radar JSON and trigger JSON

---

*Generated from notebook 00 outputs. Update this file after each new notebook.*
