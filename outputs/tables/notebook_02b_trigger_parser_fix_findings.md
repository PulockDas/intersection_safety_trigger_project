# Notebook 02b — Trigger parser fix (findings)

## Was the extraction bug fixed?

Yes. In `src/trigger_parser.py`, `extract_trigger_events` previously stopped at `trigger_outputs[i]` (via `TRIGGER_LIST_FIELDS` / `_extract_from_item`) and never walked the nested `traffic_triggers` list. It now **only** iterates `payload["trigger_outputs"][i]["traffic_triggers"][j]` and copies `reference_name`, `associated_lane`, `associated_zone`, and `associated_sensor` from each trigger dict.

`mqtt_record_has_nonempty_traffic_triggers` encodes the same structural rule for counting MQTT rows that actually carry events.

## Are semantic fields now populated?

For each decoded MQTT `payload`, each event row includes the four semantic fields when present on the objects under `traffic_triggers`. The notebook writes `corrected_sample_trigger_event_table.csv` as **the subset of rows where all four fields are non-empty strings** (so the CSV is suitable for spot-checking real semantics).

`normalize_trigger_record` now adds `source_file` (zip internal path), uses **`payload["timestamp"]` only** for wall time (not `receivedAt`), and fills `payload_timestamp_epoch_ms` via `parse_payload_timestamp_to_utc_epoch_ms`.

## Which trigger reference names were found?

**After you run** `notebooks/02b_trigger_parser_fix_and_validation.ipynb` with the USDOT training zips, the reference-name list is printed and embedded in the generated markdown from the sampled files (~3 trigger JSON paths). From Notebook 02 deep inspection across three runs, activations included names such as **`trigger_11_3`** and **`trigger_12_4`** (same run could emit multiple events per MQTT step).

## Which lanes / zones / sensors were found?

Notebook 02 saw values such as **`lane22`**, **`lane24`**, **`zoneK`**, **`zoneL`**, **`sensor3`** on the nested trigger objects. Re-run 02b to list the exact sets for your sampled paths.

## Is `payload.timestamp` parsed correctly?

`parse_payload_timestamp_to_utc_epoch_ms` (and the backward-compatible `iso_to_epoch_ms`) now:

- Accept **ISO-8601 with `T`**, **space-separated** datetimes, optional timezones, and trailing **`Z`** (via `python-dateutil`).
- Treat **naive** strings as **UTC**.
- Treat **numeric** values as **seconds** if magnitude is below **1e12**, otherwise as **milliseconds** (same rule as before for numerics).

This addresses the Notebook 02 issue where **space-separated** timestamps failed in the old string-only `iso_to_epoch_ms` path.

## Is the corrected parser ready for building the window dataset?

**Yes, for time-only alignment:** use `payload_timestamp_epoch_ms` aligned to radar stream time in **UTC**. Do **not** use MQTT `receivedAt` as a per-event clock. Do **not** filter radar objects by trigger lane/zone until naming is reconciled with radar `closest_lane` / `within_zone`.

## What should Notebook 03 do next?

1. Build a **full** trigger-event table over all runs (same row schema as 02b), still reading JSON inside zips.
2. Define **time windows** (e.g. ±N seconds) around each `payload_timestamp_epoch_ms`.
3. Pull radar data into those windows by **timestamp alignment only** (no lane/zone filtering on radar yet).
4. Add **negative windows** (intervals with no trigger activation) for contrast / training balance.
5. Defer lane/zone–aware radar subsets until a dedicated **ID mapping** notebook or schema fix is available.

---

**Outputs from Notebook 02b** (written next to this file when the notebook runs successfully):

- `corrected_sample_trigger_event_table.csv`
- `corrected_trigger_parser_validation_summary.csv`
- `corrected_sample_trigger_reference_mapping.csv`

*This file was seeded from the implementation work; re-run `02b_trigger_parser_fix_and_validation.ipynb` to refresh counts and lists from your local zips.*
