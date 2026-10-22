# Offline OCR: test corpus, measured metrics and the audit of manual overrides

prompt.md R1-H requires offline OCR as a real ML component on both native platforms, test datasets covering
different dashboard formats and lighting, and an audit of manual corrections. This page records what the corpus is,
what each platform measured on it, and how a person's override of an OCR reading is audited. OCR confidence is
never treated as proof of authenticity (prompt.md §7): the original photo is kept, immutable and content-addressed,
and every override can be reviewed.

## Corpus (`contracts/fixtures/ocr`)

* Generator: `asseta.tools.ocr_fixtures` (deterministic, seed `20261021`); spec version 1 in `manifest.json`.
* 24 images: 4 display styles × 6 conditions.
  * Styles: `lcd_7seg` (seven-segment LCD), `mechanical_drum` (rolling drum with a red tenths wheel),
    `backlit_amber` (amber backlit display with a clock as a distractor), `plain_digital`.
  * Conditions: `normal`, `dim`, `glare`, `blur`, `rotated`, `noise`.
* Categories: **17 `must_read`** (a capture app must read these correctly) and **7 `fallback_ok`** (it may decline and
  fall back to manual entry, but must never return a confident wrong value): lcd_7seg glare/blur/noise,
  mechanical_drum glare/blur, backlit_amber glare, plain_digital glare.
* Parse spec: `parse_cases.json` (12 cases) with the Python reference parser; both native apps run the same cases.
* Acceptance targets (manifest `acceptance`): must_read accuracy ≥ 0.90 and **0 confident wrong reads** per platform.
* Known risk (manifest `known_risks`): text OCR can merge the drum's tenths wheel into the integer (20264.1 → 202641);
  apps use drum geometry or fall back, and the server's `IMPOSSIBLE_INCREMENT` / `METER_DECREASE` sequence rules catch
  a merged read that slips through.
* Limitation: the corpus is synthetic. Real dashboard photos with permission to use them are an open external
  dependency (EXT-05); the metrics below must be re-measured on them.

## Measured per platform (track.md, Gate 4)

| Platform | Engine | Run | must_read | fallback_ok read | Confident wrong |
|---|---|---|---|---|---|
| Android | ML Kit text v2 + geometric pipeline and seven-segment decoder | `connectedDebugAndroidTest`, API 35 emulator (2026-10-21, re-run independently) | **17/17** (lcd_7seg 3/3, drum 4/4, amber 5/5, plain 5/5); regression floor 16/17 | 5/7 | **0** |
| iOS | Vision text recognition + the same geometric pipeline | app-hosted tests, iPhone 17 Pro simulator (2026-10-21) | **17/17** at confidence ≥ 0.85 | — (declines are allowed) | **0** |

History: the first Android measurement was 9/17 must_read (target not met); the OCR uplift (geometric pipeline and
seven-segment decoder ported from iOS) brought it to 17/17 with 0 confident wrong reads.

## How a manual override is recorded

A meter capture stores the reading the supervisor submitted (`reading`) together with what OCR produced:
`ocr_value`, `ocr_confidence`, `ocr_engine` (e.g. `mlkit-text-v2@android`, `vision@ios`), `ocr_raw_text`, the photo
(`photo_attachment_id`, `photo_sha256`), GPS, device and capture/receive times, and the policy version applied.

* `manually_corrected = true` when an OCR value existed and the submitted reading differs from it. The meter rules
  then raise a `MANUAL_CORRECTION` exception (INFO; blocking for billing when the tenant's METER_CAPTURE policy sets
  `manual_correction_requires_review`), with `ocr_value` and `entered_value` as evidence, for a reviewer to mark
  EXPLAINED or CONFIRMED with a note.
* A capture taken in `MANUAL` mode while an OCR value also existed is an override too, even when the values agree.
* Low confidence below the policy threshold raises `LOW_OCR_CONFIDENCE` independently.

## The audit report

`GET /api/v1/tenant/insights/manual-overrides` (permission `tenant.meter.read`) lists every capture where OCR produced
a value but the stored reading was entered by a person: OCR value vs entered value and the difference, confidence and
engine, who captured it (user id and display name for members of the tenant), when (device and server time), machine,
job, capture kind and mode, and the related `MANUAL_CORRECTION` exception with its review status. Filters:
`captured_from` (inclusive), `captured_to` (exclusive), `machine_id`, `user_id`; paginated (`page`, `page_size`).
A summary gives the total, OCR corrections, manual-mode captures with OCR, captures whose values differ and
exceptions still open. The report is tenant-scoped (RLS) and read-only; it describes what was recorded and does not
judge anyone — repeated overrides are something to look at together with the photos, not a finding by themselves.
