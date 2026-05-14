# Notebook 02b — Trigger parser fix (findings)

**Run:** Colab execution with training zips under `ITS_Intersection_USDOT` (4 zips detected). **Sample:** first **3** trigger JSON paths after sorting `(zip_name, internal_path)` — all three from **`Training Data 1.zip`** (runs **1016**, **1023**, **0106**).

Artifacts committed under: `outputs/tables/notebook-2b/`.

---

## Was the extraction bug fixed?

Yes. **`extract_trigger_events`** in `src/trigger_parser.py` now walks only:

`payload["trigger_outputs"][i]["traffic_triggers"][j]`.

The previous bug (treating each `trigger_outputs[i]` object as a single event) is gone.

---

## Cell output (§3 — validation)

Printed summary (abridged):

| run_id | zip_name            | total_mqtt_records | records_with_trigger_events | empty_records | extracted_trigger_events | unique_reference_names | unique_lanes | unique_zones | unique_sensors |
|--------|---------------------|-------------------:|----------------------------:|--------------:|---------------------------:|-----------------------:|-------------:|-------------:|---------------:|
| 1016   | Training Data 1.zip | 2317               | 2317                        | 0             | 30121                      | 13                     | 13           | 13           | 4              |
| 1023   | Training Data 1.zip | 2525               | 1549                        | 976           | 18588                      | 12                     | 12           | 12           | 4              |
| 0106   | Training Data 1.zip | 2073               | 2073                        | 0             | 26949                      | 13                     | 13           | 13           | 4              |

Follow-up lines confirmed saves:

- `corrected_sample_trigger_event_table.csv` — **75,658** rows  
- `corrected_trigger_parser_validation_summary.csv`  
- `corrected_sample_trigger_reference_mapping.csv`  
- `notebook_02b_trigger_parser_fix_findings.md`  

No `[WARN]` lines appeared after the sanity checks (no zero-extraction file, no bulk-empty semantics, no timestamp parse failures).

---

## Are semantic fields now populated?

**Yes.** After extraction, **every** row in the combined sample had non-empty `reference_name`, `associated_lane`, `associated_zone`, and `associated_sensor`:

- **Raw extracted events:** 30,121 + 18,588 + 26,949 = **75,658**  
- **Rows in `corrected_sample_trigger_event_table.csv`:** **75,658** (filter removed nothing)

So for these three files, the nested trigger objects always carried the full four semantic fields.

---

## Which trigger reference names were found? (sample)

**13** distinct `reference_name` values appear in the merged `corrected_sample_trigger_reference_mapping.csv`:

`trigger_11_3`, `trigger_12_4`, `trigger_13_5`, `trigger_14_6`, `trigger_15_7`, `trigger_16_8`, `trigger_17_9`, `trigger_18_10`, `trigger_19_11`, `trigger_1_0`, `trigger_20_12`, `trigger_4_1`, `trigger_7_2`

Run **1023** alone shows **12** unique references in the per-file summary (one fewer than 1016 / 0106), which is consistent with a slightly smaller activation set on that run.

---

## Which lanes / zones / sensors were found? (sample)

From the corrected mapping (13 lane–zone–sensor combinations):

- **Lanes (13):** lane1, lane2, lane5, lane8, lane15, lane16, lane17, lane18, lane19, lane20, lane21, lane22, lane24  
- **Zones (13):** zoneA, zoneD, zoneG, zoneK, zoneL, zoneM, zoneN, zoneO, zoneP, zoneQ, zoneR, zoneS, zoneT  
- **Sensors (4):** sensor1, sensor2, sensor3, sensor4  

---

## Per-file interpretation notes

- **1016** and **0106:** every MQTT record had non-empty `traffic_triggers` (`empty_records = 0`).  
- **1023:** **976** MQTT records had **no** non-empty `traffic_triggers` (`empty_records = 976`). That is expected: empty time steps are valid; extraction still produced **18,588** events on the remaining steps.

---

## Is `payload.timestamp` parsed correctly?

**Yes, on this sample.** Example from `corrected_sample_trigger_event_table.csv`:

- String: `2024-02-19T18:46:34+00:00`  
- `payload_timestamp_epoch_ms`: **1708368394000.0**  

The notebook’s parse-failure counter reported **0** MQTT records with a non-null `timestamp` that failed to convert to epoch ms.

---

## Is the corrected parser ready for building the window dataset?

**Yes, for timestamp-only alignment:** use **`payload_timestamp_epoch_ms`** (UTC). Do **not** use MQTT `receivedAt` as the event clock. Do **not** filter radar by trigger lane or zone until trigger and radar identifiers are harmonized.

---

## What should Notebook 03 do next?

1. Enumerate **all** trigger files (~391 paths across four zips, or a chosen subset) and write one **full** trigger-event table using the same schema as 02b.  
2. Define fixed windows (e.g. ±N s) around each **`payload_timestamp_epoch_ms`**.  
3. Join radar JSON by **time only** inside those windows (no lane/zone gating on radar yet).  
4. Sample **negative** windows (no activations) for balance / contrast.  
5. Add a later step or notebook for **lane/zone ID mapping** if spatial conditioning is required.

---

*Generated by `notebooks/02b_trigger_parser_fix_and_validation.ipynb`; refreshed from committed CSVs and saved notebook stdout.*
