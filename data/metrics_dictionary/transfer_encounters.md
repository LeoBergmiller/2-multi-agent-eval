# Transfer encounters

An episode of care spanning more than one facility appears as **separate encounters**,
one per organization, linked by patient and adjacency in time rather than by any field.

## Why this matters

- **The transfer-out is not a discharge to the community.** The patient's episode
  continues elsewhere, so the sending facility's encounter is excluded from readmission
  index admissions. See [[readmission_30day]].
- **The transfer-in is not a readmission.** It is a continuation, not a return, and
  counting it as one inflates the receiving facility's rate.
- Length of stay for a transferred patient is per-encounter by default. Whole-episode
  length of stay requires stitching the encounters together and must be stated as such.
  See [[length_of_stay]].

## The detection problem

`encounters` has no transfer flag. A transfer is inferred from an inpatient encounter at
one organization ending as another begins for the same patient, within a short window.
That inference is heuristic — a genuine same-day readmission at a different hospital
looks identical — so any rule adopted should be stated in the answer.

## Not to be confused with

A readmission ([[readmission_30day]]) or a second admission. All three are "two
inpatient encounters for one patient", distinguished only by timing and interpretation.
