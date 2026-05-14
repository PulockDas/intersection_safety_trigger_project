# Physics-Informed Trigger Event Analysis
### Urban Intersection Safety — Master's Research Project

---

## Overview

This project develops a **physics-informed machine learning pipeline** for
analysing trigger events at urban intersections using the
**USDOT Intersection Safety Challenge (ISC) Stage-1B dataset**.

The core idea is to extract radar-based object detections and traffic trigger
activation logs, engineer physics-informed features (speed, TTC proxy,
stopping distance, energy proxy, PDE-inspired density/flow residuals), and
build a supervised classifier that distinguishes trigger vs. non-trigger
time windows.

---

## Repository Structure

```
intersection_safety_trigger_project/
│
├── notebooks/
│   └── 00_training_zip_structure_check.ipynb   ← Task 0: zip inventory
│
├── src/
│   ├── config.py           ← constants, file patterns, scan limits
│   ├── zip_utils.py        ← zip scanning, JSON reading, trigger probe
│   ├── file_discovery.py   ← zip discovery, output dir creation
│   └── utils.py            ← formatting, sys.path, safe_get, printers
│
├── outputs/
│   ├── tables/             ← CSVs (inventory, sample paths, trigger probe)
│   ├── figures/            ← plots (generated in later notebooks)
│   ├── samples/            ← small JSON / CSV excerpts for inspection
│   └── logs/               ← run logs
│
├── README.md
└── requirements.txt
```

---

## Dataset

| File | Contents |
|------|----------|
| `Training Data 1.zip` | Subset of Run_XXXX folders |
| `Training Data 2.zip` | Subset of Run_XXXX folders |
| `Training Data 3.zip` | Subset of Run_XXXX folders |
| `Training Data 4.zip` | Subset of Run_XXXX folders |

Each `Run_XXXX` folder is expected to contain:

| File pattern | Description |
|---|---|
| `Run_XXXX_GT.csv` | Ground-truth labels |
| `Radars_Run_XXXX_sensor{1-4}.json` | Radar object detection data |
| `Radars_Run_XXXX_traffic-triggers-output.json` | Traffic detector/zone activations |
| `V2XHubSensor_Run_XXXX.csv` | V2X hub sensor data |
| `VisualCamera*_Run_XXXX_frame-timing.csv` | Visual camera frame timing |
| `ThermalCamera*_Run_XXXX_frame-timing.csv` | Thermal camera frame timing |
| `ISC_Run_XXXX_ISC_all_timing.csv` | ISC all-sensor timing |
| `ISC_Run_XXXX_v2xhub_timing.csv` | V2X hub timing |

---

## Notebook Roadmap

| # | Notebook | Status |
|---|----------|--------|
| 00 | Training Zip Structure Check | ✅ Task 0 |
| 01 | Radar JSON Schema Inspection | ⬜ Planned |
| 02 | Trigger Log Schema Inspection | ⬜ Planned |
| 03 | Window Dataset Construction | ⬜ Planned |
| 04 | Physics Feature Engineering | ⬜ Planned |
| 05 | Baseline Model Training | ⬜ Planned |

---

## Quick Start (Google Colab from GitHub)

1. Push this repo to GitHub.

2. Open the notebook directly in Colab:
   `https://colab.research.google.com/github/YOUR_USERNAME/intersection_safety_trigger_project/blob/main/notebooks/00_training_zip_structure_check.ipynb`

3. In **Cell 4 (Clone Repo)**, set `GITHUB_REPO_URL` to your repo URL.
   The cell clones the repo into `/content/` so `src/` modules are available.

4. In **Cell 8 (Project Setup)**, set `TRAINING_ZIP_DIR` to the Google Drive
   folder that holds your 4 training zip files.
   Drive is mounted **read-only** — nothing is written to Drive.

5. Run all cells from top to bottom.

6. **Section 8** zips all outputs and triggers a browser download.
   Outputs are saved to `/content/` only — they are **not** saved to Drive.

7. Unzip the downloaded file, add the CSVs to `outputs/tables/`, and push to GitHub.

---

## Installation (local)

```bash
pip install -r requirements.txt
```

---

## Research Goals

1. **Trigger vs. Non-trigger window classification** using radar signals
2. **Physics-informed feature extraction**: TTC proxy, stopping distance,
   kinetic energy proxy, PDE-inspired density/flow residual
3. **Interpretable models** that connect physical quantities to safety events
4. **Semantic trigger decoding**: map `reference_name` values to lane/zone
   activations via multi-modal evidence (radar + camera + V2X timing)

---

## Important Notes

- Traffic trigger `reference_name` values are **not yet semantically decoded**.
  They should be treated as detector/zone activation identifiers until
  further mapping evidence is collected (see Notebook 02).
- Video (`.mp4`, `.ts`) and network capture (`.pcap`) files are identified
  in the inventory but **never read or extracted** in Task 0.
- All zip scanning is performed on the **central directory only** — no
  full extraction occurs.

---

## License

For academic research use. Dataset provided under USDOT ISC challenge terms.
