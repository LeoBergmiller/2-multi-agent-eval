# Emergency department visits

The count of encounters with `ENCOUNTERCLASS` of `emergency`.

## When this is the right metric

ED throughput, demand, and access questions: how busy the department was, arrival
patterns, and denominators for ED-specific rates such as left-without-being-seen.

## Relationship to admissions

An ED visit that results in the patient being admitted appears as **two rows**: the
`emergency` encounter and a separate `inpatient` encounter. So:

- ED visits and admissions **overlap in patients but not in rows**.
- Adding them together double-counts the admitted-from-ED population.
- The **admission rate from the ED** is the share of ED visits followed by an inpatient
  encounter for the same patient — a join, not a filter.

## Not to be confused with

[[admission]]. An emergency encounter is not an admission, however sick the patient. If
they were admitted, the inpatient row is the admission and is the one to count.
