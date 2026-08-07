# Length of stay

**Length of stay (LOS) is counted in midnights**: the number of calendar-day boundaries
crossed between an inpatient encounter's `START` and `STOP`.

## Why midnights

A patient admitted at 23:00 and discharged at 07:00 the next morning occupied a bed
across one midnight. Elapsed-hours arithmetic calls that 0.33 days; subtracting raw
timestamps and truncating can call it 0. The midnight count is what drives bed-day
utilisation and what payers reimburse, so it is the operational definition.

## Rules

- **A same-day discharge has LOS = 0**, not 1. Admitted and discharged before the first
  midnight means no bed-night was consumed. This is a real and meaningful category —
  do not conflate it with invalid data (see [[reversed_stays]]).
- **Exclude still-admitted patients.** A stay in progress has no defined length yet.
  See [[open_stays]].
- **Exclude reversed stays** (`STOP < START`) rather than clamping them to zero. See
  [[reversed_stays]].
- **Truncate outliers above 365 midnights to 365** before averaging.
- **Deduplicate encounters first.** A double-posted stay would otherwise be counted
  twice in the distribution. See [[encounter_deduplication]].

## Reporting

LOS is **right-skewed**: a small number of very long stays pull the mean well above the
typical stay. Report the **median** alongside the mean whenever the question concerns
the distribution or "typical" length, and say which statistic is which. A mean reported
alone is not wrong arithmetic but it is a misleading answer to most LOS questions.

Applies to **inpatient encounters only**. LOS is not defined for ambulatory, wellness or
virtual encounters. See [[admission]].
