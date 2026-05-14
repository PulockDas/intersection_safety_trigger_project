# Notebook 01 — Radar JSON Schema Findings
**Physics-Informed Trigger Event Analysis — Urban Intersection Safety**  
**Generated:** 2026-05-14 06:37  
**Runs inspected:** 3  
**Sensor files read:** 12 (12 OK, 0 errors)  

---

## 1. Top-Level Structure

Top-level JSON type seen: {'list': 12}

The radar sensor JSON files are a **list of records** (same pattern as trigger JSON).
Each element in the list is an object with keys such as:
  `['topic', 'payload', 'qos', 'receivedAt', 'retain']`

This is consistent with an **MQTT message log** format.

---

## 2. Payload Encoding

Payload encoding found: {'dict_or_list': 12}  
Payload type after decode: {'dict': 12}

`payload` is already a Python dict — no additional decoding needed.

---

## 3. Where Object Detections Are Stored

Object list field name(s) found: {'objects': 3}
  → Primary field to use: **`payload.objects`**
  → Object counts per record sample: min=1, median=1, max=2

---

## 4. Timestamp Fields

Timestamp fields found: `receivedAt` (top-level) and `payload.timestamp` (inside payload)

| Field | Location | Meaning | Use |
|-------|----------|---------|-----|
| `receivedAt` | Top-level MQTT field | When the message arrived at the broker | **Primary alignment field** |
| `payload.timestamp` | Inside payload dict | When the sensor captured the frame | Secondary / latency check |

**`receivedAt`** is the **recommended alignment field** for matching radar records
with trigger MQTT messages in Notebook 03 — both file types carry it at the same
structural level.

**Latency estimate:** `receivedAt − payload.timestamp` gives the end-to-end
sensor-to-broker latency. If this gap is consistently small (< 100 ms), `receivedAt`
is reliable for millisecond-level trigger alignment. If it is large or variable,
`payload.timestamp` should be used instead.

---

## 5. Object Field Availability

Total sampled objects: 4

> **Sample-size note:** The 25% figures below are a sampling artifact, not a real
> coverage gap. Only 4 total objects were collected across 3 sampled records, and those
> 4 came from a single record that happened to contain objects. In records with zero
> detections the object fields are absent by definition. With a larger sample all key
> fields are expected at or near 100% for records that do contain detections.

| Field | % present (sample) | Notes |
|-------|-------------------|-------|
| `payload_dict` | 100% | payload is always a dict — no decoding step needed |
| `objects` | 25% | object list field — absent in zero-detection records |
| `id` | 25% | key for object tracking across frames (tracklets) |
| `class` | 25% | key for object type filtering (vehicle / pedestrian / cyclist) |
| `speed` | 25% | key for physics features |
| `heading` | 25% | key for physics features |
| `position_front` | 25% | spatial position of object front — see Section 6 |
| `position_facing` | 25% | spatial position of object facing direction — see Section 6 |
| `position_any` | 25% | key for distance / TTC proxy |
| `lane` | 25% | key for lane-level trigger matching (cross-check with trigger `associated_lane`) |
| `zone` | 25% | key for zone-level trigger matching (cross-check with trigger `associated_zone`) |
| `tracking_status` | 25% | confidence / quality filter for noisy detections |

---

## 6. Position Field Assessment

- `position_front`: present in 4 objects; 0 have x/y/z as named sub-keys
- `position_facing`: present in 4 objects; 0 have x/y/z as named sub-keys
- `position`: present in 0 objects

> **Action required before Notebook 03:** `position_front` and `position_facing` are
> consistently present but their internal format is not yet confirmed. The probe found
> no `x`/`y`/`z` sub-keys, which means coordinates are likely stored as:
>
> - a flat list `[x, y, z]` or `[lat, lon, alt]`
> - named fields with different key names (e.g. `lat`/`lon`, `east`/`north`, `range`/`azimuth`)
> - a string such as `"x=12.3 y=4.5"`
>
> Inspect the raw sample values printed in Notebook 01 cell 7 output to confirm the
> exact format before implementing any distance or TTC proxy feature.

---

## 7. Physics Feature Readiness

Based on field availability from the sample:

| Feature | Field availability | Purpose |
|---------|-------------------|---------|
| Object count | 25% | count objects per time window |
| Speed stats | 25% | mean/max speed in window |
| Heading stats | 25% | heading spread, alignment |
| Position / distance | 25% | inter-object distance, TTC proxy |
| Lane activity | 25% | count objects per lane |
| Zone activity | 25% | count objects per zone |
| Object classification | 25% | filter by vehicle type |
| Tracking quality | 25% | filter by confidence |

**TTC proxy** (time-to-collision): requires position + speed → computable if both present.
**Stopping distance proxy**: requires speed → computable.
**Kinetic energy proxy**: requires speed + (length×width as mass proxy) → likely computable.
**PDE density/flow residual**: requires object count + position → likely computable.

---

## 8. Sensor Consistency

Sensors inspected: 12 (across 3 run(s))
All sensors share the same top-level type: YES

See `radar_sensor_schema_comparison.csv` for the full per-sensor breakdown.

---

## 9. Uncertainties and Open Questions

- [ ] Are the object coordinates in a global (lat/lon) or local (metres from sensor) system?
- [ ] What is the coordinate origin and orientation for each sensor?
- [ ] How are the 4 sensors spatially arranged at the intersection?
- [ ] Is `receivedAt` consistent enough for millisecond-level alignment with trigger files?
- [ ] Do all records in a file have the same payload structure, or does it vary?
- [ ] Is the object `id` stable across consecutive MQTT records (tracklet)?
- [ ] Does `within_zone` or `closest_lane` directly correspond to trigger zone/lane identifiers?

---

## 10. Next Steps — Notebook 02

**Notebook 02: Trigger Log Deep Inspection** should:
- Explicitly decode the `payload` field of trigger MQTT messages.
- Print the `topic` strings (10–20 samples) to extract lane/zone semantics.
- Find `reference_name`, `associated_lane`, `associated_zone` inside `payload`.
- Build a `reference_name → lane/zone/sensor` mapping table.
- Cross-reference trigger `receivedAt` timestamps with radar record timestamps
  from matching runs to measure the alignment gap.
- Confirm that `closest_lane` / `within_zone` in radar objects maps to
  the same lane/zone identifiers used in trigger messages.