# 30-day readmission rate

The fraction of eligible index inpatient admissions followed by an unplanned inpatient
readmission **within 30 days of discharge**.

```
readmission_rate = readmitted_index_admissions / eligible_index_admissions
```

## The window is anchored on discharge

The 30 days run from the **`STOP` (discharge) of the index admission**, not its `START`.
Anchoring on admission date shortens the effective window by the length of the index stay
and undercounts readmissions — more so for longer stays, so the bias is not uniform.

## Index admission eligibility

An inpatient admission is an index admission unless it is excluded. Exclude:

- **In-hospital deaths.** The patient cannot be readmitted; leaving them in the denominator
  understates the rate.
- **Transfers to another acute facility.** The stay has not truly ended, so the transfer-out
  is not a discharge to the community.
- **Discharges against medical advice (AMA).**
- **Admissions with no 30-day observable follow-up window** — those discharged within 30
  days of the end of the reporting period. Their outcome is unknown, not negative.

## Which readmissions count

- **Any-facility, all-cause.** A readmission to a *different* organization still counts.
  Restricting to the same facility undercounts, and is a distinct metric.
- **Planned readmissions do not count** — scheduled chemotherapy, staged procedures,
  rehabilitation admissions.
- **One readmission per index admission.** A patient readmitted twice within 30 days
  contributes one readmitted index admission, not two.
- A readmission may itself be an index admission for a subsequent window.
