# Length of stay — calendar days

The number of distinct **calendar dates** an inpatient encounter touches, counting both
the admission date and the discharge date.

```
los_calendar_days = date(STOP) - date(START) + 1
```

## When this is the right metric

Some registries, older state discharge datasets, and certain per-diem contracts count
days this way. It is also the intuitive reading of "how many days was the patient here",
which is why it appears in ad-hoc analyses.

## How it differs from the standard

Calendar days is always **exactly one more** than the midnight count for any completed
stay. Critically, a **same-day discharge is 1 calendar day but 0 midnights** — so this
construction reports bed-nights that were never consumed, and inflates mean length of
stay by roughly one day across the whole population.

## Not to be confused with

[[length_of_stay]], which counts **midnights** and is the basis for bed-day utilisation
and reimbursement. The off-by-one is uniform and therefore easy to miss: every facility,
every service line, every year shifts together, so the numbers stay internally
consistent while being consistently wrong.
