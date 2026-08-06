# Length of stay

**Length of stay (LOS) is counted in midnights**: the number of midnights between the
`START` and `STOP` of an inpatient encounter.

```
los_midnights = date_diff('day', CAST(START AS DATE), CAST(STOP AS DATE))
```

## Why midnights and not elapsed time

A patient admitted at 23:00 and discharged at 07:00 the next morning has occupied a bed
across one midnight. Elapsed-hours arithmetic calls that 0.33 days; calendar-day
subtraction on the raw timestamps can call it 0. The midnight count is what determines
bed-day utilisation and what payers reimburse, so it is the operational definition.

## Rules

- **A same-day discharge has LOS = 0**, not 1. Admitted and discharged before the first
  midnight means no bed-night was consumed.
- **Still-admitted patients are excluded** from LOS averages. A null `STOP` means the stay
  has not ended and its length is not yet defined. Treating null as zero drags the mean
  down; treating it as "today minus START" mixes complete and incomplete stays.
- **Outliers above 365 midnights are truncated to 365** before averaging.
- **Encounters with `STOP < START` are invalid** and excluded, not clamped to zero. They
  are a data-quality artifact, not a real same-day stay.

Report the **median** alongside the mean when the distribution is asked about: LOS is
right-skewed and the mean alone overstates the typical stay.
