# 90-day readmission rate

The share of eligible index inpatient admissions followed by an unplanned inpatient
readmission within **90 days** of discharge.

Mechanically identical to [[readmission_30day]] — discharge-anchored, any-facility,
all-cause, one readmission per index admission — with the follow-up window extended to
90 days.

## When this is the right metric

Longer-horizon programmes: bundled-payment episodes, post-acute care coordination, and
chronic-condition management, where 30 days is too short to capture the outcome the
programme is accountable for. It is the standard window for several episode-based
payment models.

## Consequences of the longer window

- The rate is **materially higher** than the 30-day figure — more time, more returns.
- More index admissions fail the observable-window test, since 90 days of follow-up must
  exist after discharge. The denominator shrinks further.
- Attribution weakens: at 90 days a readmission is less plausibly related to the index
  stay, which is why the shorter window is preferred for quality measurement.

## Not to be confused with

[[readmission_30day]]. The two differ by a single number in the window and by nothing
else, which makes them easy to retrieve interchangeably and impossible to substitute.
A 90-day figure reported against a 30-day question is not slightly high — it is a
different metric.
