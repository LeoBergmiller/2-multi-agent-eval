# Same-day discharge

An inpatient encounter admitted and discharged **on the same calendar date**, crossing
no midnight.

## Rules

- Its length of stay is **0 midnights**, not 1. See [[length_of_stay]].
- It is a **real admission** and counts in admission volume. See [[admission]].
- It is a valid index admission for readmission purposes.

## Why the category is tracked separately

The share of same-day discharges is an operational signal in its own right: it reflects
admission-appropriateness, observation-status practice, and pressure on beds. A rising
share can mean improved throughput or it can mean patients are being admitted who should
have been placed in observation.

That is precisely why invalid rows must not be folded into it. An encounter with
`STOP < START` is corrupt data; clamping its duration to zero would file it here and
contaminate a category that is being watched for real movement. See [[reversed_stays]].

## Not to be confused with

[[reversed_stays]] (invalid, excluded) or [[observation_stay]] (outpatient status, not
an admission at all). All three are short, all three look similar in a duration
histogram, and only this one is a genuine zero-midnight admission.
