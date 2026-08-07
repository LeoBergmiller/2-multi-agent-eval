# Patient volume

The count of **distinct patients** seen in a period, regardless of how many encounters
each generated.

```
patient_volume = count(DISTINCT PATIENT)
```

## When this is the right metric

Population size, panel size, market share, and any per-patient rate. It is the correct
denominator when the question is about *people*: "how many patients did we treat",
"what share of patients were readmitted at least once".

## Rules

- A patient seen ten times counts once. That is the point of the measure and also its
  main hazard when substituted for a volume question.
- Deduplicate encounters before deriving patient counts from them, and be aware that
  duplicate encounter rows do **not** affect a distinct-patient count — which is why a
  patient count can look correct while the encounter counts beside it are inflated. See
  [[encounter_deduplication]].

## Not to be confused with

[[admission]] and [[encounter_volume]], both of which count **events**. Patient counts
are always lower, often by a large factor in populations with chronic conditions, and
the gap between them varies by service line — so the substitution is not a constant
offset that could be spotted by its size.
