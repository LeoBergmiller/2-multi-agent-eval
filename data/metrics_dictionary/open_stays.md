# Open stays (still-admitted patients)

An encounter with a **null `STOP`** is a stay that has not ended: the patient is still
admitted as of the data cut.

`STOP` is a real `TIMESTAMP` column and the missing values are genuine SQL `NULL`s, not
empty strings. Comparisons against them return `NULL` rather than false, so they drop
out of filters silently rather than erroring.

## Rules by measure

- **Volume and admission counts: include them.** A still-admitted patient was admitted.
  A stray `STOP IS NOT NULL`, or an inner join onto a discharge event, removes them and
  undercounts. See [[admission]].
- **Length of stay: exclude them.** The length of an unfinished stay is not defined
  yet. Treating null as zero drags the average down; substituting the data-cut date
  mixes complete and incomplete stays and understates the true figure for long ones.
  See [[length_of_stay]].
- **Readmission index admissions: exclude them.** An index admission needs a discharge
  date to anchor its follow-up window. See [[readmission_30day]].

The pattern is that "include" and "exclude" are both correct, for different measures.
State which was applied.

## Reporting

When a measure excludes open stays, report how many were excluded alongside the result.
A silently shrinking denominator is the thing that makes this error hard to catch later.
