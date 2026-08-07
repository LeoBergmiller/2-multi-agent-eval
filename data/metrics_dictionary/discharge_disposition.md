# Discharge disposition

Where the patient went on leaving: home, home with services, skilled nursing, another
acute facility, hospice, against medical advice, or expired.

## Why it is load-bearing for other metrics

Readmission eligibility depends almost entirely on disposition — in-hospital deaths,
transfers to another acute facility, and discharges against medical advice are all
excluded as index admissions on the basis of where the patient went. See
[[readmission_30day]].

## Rules

- Disposition is a property of the **discharge**, so it does not exist for an open stay.
  See [[open_stays]].
- A discharge to hospice is a discharge, not a death, even when death follows shortly.
- "Home with services" is a discharge to the community and remains readmission-eligible.

## Availability caution

This dataset has **no explicit discharge-disposition field**. Where a metric's
definition refers to disposition, it must be inferred — death from the patient's
`DEATHDATE`, transfer from a subsequent encounter at another organization (see
[[transfer_encounters]]) — and the inference stated as an assumption in the answer. Do
not silently treat an unavailable exclusion as an empty one; report which exclusions
could be applied and which could not.
