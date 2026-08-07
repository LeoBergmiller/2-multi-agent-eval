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
- **Truncate outliers above 365 midnights to 365** before averaging. See below.
- **Deduplicate encounters first.** A double-posted stay would otherwise be counted
  twice in the distribution. See [[encounter_deduplication]].

## The 365-midnight truncation

**A stay longer than one year is not an acute inpatient stay.** It is either a data
artifact — a missing or corrupted discharge — or a long-term-care, rehabilitation or
psychiatric episode misclassified as acute. Either way it does not describe the thing
LOS is used to manage: acute bed capacity and throughput. Left untruncated, a handful of
such rows dominate the mean and distort any percentile above them.

**Why a fixed threshold rather than a percentile of the observed distribution.** A
truncation point derived from the data (p99, p99.9) would be reproducible in the sense
of "recomputable", but it would make the *definition* a function of the dataset it is
applied to. Re-seed the warehouse, change the population size, add a year of history,
and the threshold moves — which moves length of stay, which moves every ground truth
computed from it, with nothing in the task file recording that the definition changed.
A definition that shifts with its own input cannot anchor a verified number.

365 is therefore a **fixed clinical boundary, not a statistical one**: one calendar year
is the point past which an acute inpatient stay is implausible on its face, and that
remains true regardless of what any particular warehouse contains.

**This threshold is load-bearing for reported statistics, not only the mean.** A p90 or
a "share of stays exceeding a week" is computed over the truncated distribution, so
reference SQL must apply the truncation before computing them, and must say that it did.

## Reporting

LOS is **right-skewed**: a small number of very long stays pull the mean well above the
typical stay. Report the **median** alongside the mean whenever the question concerns
the distribution or "typical" length, and say which statistic is which. A mean reported
alone is not wrong arithmetic but it is a misleading answer to most LOS questions.

Applies to **inpatient encounters only**. LOS is not defined for ambulatory, wellness or
virtual encounters. See [[admission]].
