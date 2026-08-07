# Observation stay

A short-duration hospital stay under **outpatient** billing status, used while a
decision to admit is pending. The patient may occupy a bed overnight.

## Why it exists as a category

Observation is a billing and regulatory status, not a clinical one. From the bedside it
can be indistinguishable from a short inpatient admission; from the ledger it is
outpatient, reimbursed differently, and excluded from inpatient quality measures.

## Rules

- Observation stays are **not admissions**. See [[admission]].
- They are **not index admissions** for readmission, and a readmission *into*
  observation does not count as a readmission. See [[readmission_30day]].
- Their duration is measured in **elapsed hours**, not midnights — the operative
  thresholds are hour-based. See [[length_of_stay_hours]].

## Why the distinction matters

Shifting patients between observation and inpatient status changes reported admission
volume, length of stay and readmission rates without any change in care delivered. When
comparing periods or facilities, confirm the status mix is comparable before attributing
a difference to performance.

## Not to be confused with

[[admission]] or [[length_of_stay]], neither of which applies to observation encounters.
