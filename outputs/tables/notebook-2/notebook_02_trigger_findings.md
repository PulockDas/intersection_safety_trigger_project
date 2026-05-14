# Notebook 02 — Trigger Log Deep Inspection Findings
**Physics-Informed Trigger Event Analysis**  
**Generated:** 2026-05-14 07:10 (updated: 2026-05-14)  
**Runs inspected:** 3 | **Total MQTT records processed:** 7,009 | **Events extracted:** 4,332  

> **Semantic warning:** `reference_name` values are treated as detector/zone
> activation identifiers until confirmed by cross-modal evidence.

---

## 1. Trigger JSON Top-Level Structure

Same MQTT message-log format as radar JSON:

```
[ { "topic", "payload", "qos", "receivedAt", "retain" }, ... ]
```

`payload` is already a Python dict — no base64 or JSON-string decoding required.  
Payload has exactly **two top-level keys**: `timestamp` and `trigger_outputs`.

---

## 2. Exact Payload Structure — Two-Level Nesting

The semantic trigger fields are **two levels deep** inside the payload:

```
payload = {
  "timestamp":       "2024-01-31T16:28:38+00:00",   ← per-event UTC timestamp
  "trigger_outputs": [                               ← outer container list
    {
      "traffic_triggers": [                          ← actual trigger events here
        {
          "reference_name":    "trigger_11_3",
          "associated_lane":   "lane22",
          "associated_zone":   "zoneK",
          "associated_sensor": "sensor3"
        },
        {
          "reference_name":    "trigger_12_4",
          "associated_lane":   "lane24",
          "associated_zone":   "zoneL",
          "associated_sensor": "sensor3"
        }
      ]
    }
  ]
}
```

Full path to each trigger event:
`payload.trigger_outputs[i].traffic_triggers[j]`

---

## 3. Extraction Bug — Why Semantic Fields Are Blank in Event Table

The `normalize_trigger_record` function in `trigger_parser.py` found `trigger_outputs`
as the container field but **stopped one level too early**. It iterated
`trigger_outputs[i]` directly without descending into the `traffic_triggers` list
inside each item.

Result: 4,332 event rows were created but all have empty `reference_name`,
`associated_lane`, `associated_zone`, and `associated_sensor` values.

**Fix required before Notebook 03:**  
In `trigger_parser.py`, the extraction loop must iterate
`payload.trigger_outputs[i].traffic_triggers[j]`, not `payload.trigger_outputs[i]`.

---

## 4. Semantic Fields — Actual Values Confirmed

From `trigger_nested_field_paths.csv`, consistent across all 3 runs from 3 different zips:

| Field | Sample values | Notes |
|-------|--------------|-------|
| `reference_name` | `trigger_11_3`, `trigger_12_4` | Format: `trigger_{X}_{Y}` — meaning of X, Y TBD |
| `associated_lane` | `lane22`, `lane24` | Alphanumeric lane IDs |
| `associated_zone` | `zoneK`, `zoneL` | Letter-suffixed zone IDs |
| `associated_sensor` | `sensor3` | Only sensor3 seen in sample |

The `reference_name` format `trigger_{X}_{Y}` — the numbers may encode a
detector type, lane group, or sensor index combination. Semantic meaning is not
yet confirmed without cross-referencing the intersection metadata.

---

## 5. MQTT Topic — No Embedded Semantics

There is exactly **one MQTT topic** across all trigger messages:  
`traffic-triggers-output`

A single flat string — no sensor, lane, zone, or intersection ID is embedded.
The topic carries no semantic value; all semantics come from inside `payload`.

---

## 6. Timestamps — Critical Finding: receivedAt is File-Level, Not Per-Event

| Field | Format | Example | Behaviour |
|-------|--------|---------|-----------|
| `receivedAt` | Space-separated, no timezone | `2024-01-31 11:27:51` | **Same value for ALL records in a run** → file export timestamp |
| `payload.timestamp` | ISO 8601 UTC | `2024-01-31T16:28:38+00:00` | **Changes per record** → actual per-event timestamp |

`receivedAt` in trigger files is **not a per-message timestamp**. It holds the
same value for every record within a run, making it useless for fine-grained
alignment. This contrasts with radar files where `receivedAt` is per-message.

The ~5-hour offset between `receivedAt` (11:27 local) and `payload.timestamp`
(16:28 UTC) confirms `receivedAt` is in UTC-5 (CST) and is a file export time.

**→ Use `payload.timestamp` (UTC, per-event) for radar–trigger alignment.**

> **Additional bug:** `iso_to_epoch_ms` in `trigger_parser.py` could not parse the
> space-separator format (`2024-01-31 11:27:51`) — the alignment probe was skipped.
> Fix the parser to handle both `T`-separator and space-separator ISO formats.

---

## 7. Trigger Frequency Per Sampled Run

| Run | Zip | Total records | With events | Empty | Event rows |
|-----|-----|--------------|-------------|-------|-----------|
| 0048 | Training Data 1 | 1,965 | 1,801 | 164 | 1,801 |
| 0045 | Training Data 2 | 1,808 | 798 | 1,010 | 798 |
| 0001 | Training Data 3 | 3,236 | 1,733 | 1,503 | 1,733 |

Empty records (no `traffic_triggers` in a time step) are legitimate —
they represent moments with no detector activation and are valid negative
evidence for the window classification task.

**Event density varies significantly by run:** Run 0048 has events in 92%
of records; Run 0045 only 44%. This may reflect different traffic volumes
or time-of-day conditions.

---

## 8. Lane/Zone Identifier Mismatch — Cannot Directly Join

| Source | Lane examples | Zone examples |
|--------|--------------|---------------|
| Trigger `associated_lane` / `associated_zone` | `lane22`, `lane24` | `zoneK`, `zoneL` |
| Radar `closest_lane` / `within_zone` | `lane10` | `zoneAI` |

**No overlap between radar and trigger identifiers.**  
They use completely different naming schemes:
- Trigger lanes use numeric suffixes (`lane22`, `lane24`)
- Radar lanes use numeric suffixes (`lane10`) — different numbering
- Trigger zones use letter suffixes (`zoneK`, `zoneL`)
- Radar zones use alphanumeric IDs (`zoneAI`)

A **lane/zone mapping table** must be built before zone-level object filtering
is possible. This is a blocker for the physics-informed feature extraction step
where we want to count objects within the trigger's lane/zone.

---

## 9. Two Bugs to Fix Before Notebook 03

| Bug | Location | Fix |
|-----|----------|-----|
| Extraction stops at `trigger_outputs` level | `trigger_parser.py` → `extract_trigger_events()` | Iterate `trigger_outputs[i].traffic_triggers[j]` |
| `iso_to_epoch_ms` can't parse space-separator timestamps | `trigger_parser.py` → `iso_to_epoch_ms()` | Handle both `2024-01-31T...` and `2024-01-31 ...` formats |

---

## 10. What Notebook 03 Should Do

**Before writing Notebook 03**, apply the two bug fixes above and re-run
Notebook 02 to verify that the event table is populated correctly.

Then Notebook 03 (Window Dataset Construction) should:

- Load all trigger events from all ~391 trigger files (not just 3 runs).
- Use `payload.timestamp` as the trigger event time (not `receivedAt`).
- For each trigger event, define a time window of ±N seconds around the event time.
- Load radar records from sensor1–sensor4 for the same run within that window.
- Use `payload.timestamp` from radar records for alignment (if available),
  otherwise use `receivedAt` from radar records.
- Collect all objects (`payload.objects`) from records within the window.
- Label the window as **positive** (trigger activation).
- Sample an equal number of **negative** windows (no trigger in that period).
- Do NOT filter by lane/zone yet — the identifier mismatch must be resolved first.
- Save the labelled window dataset for feature engineering.
- Keep the raw `reference_name`, `associated_lane`, `associated_zone` values
  in the window metadata for later semantic analysis.

> Do not start feature engineering or ML until the window dataset is validated
> and the lane/zone mapping issue is documented or resolved.
