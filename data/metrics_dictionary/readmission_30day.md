# 30-day readmission rate

The share of eligible index inpatient admissions followed by an unplanned inpatient
readmission **within 30 days of discharge**.

```
readmission_rate = readmitted_index_admissions / eligible_index_admissions
```

Both numerator and denominator are counts of **index admissions**, not of patients and
not of readmissions.

## The window is anchored on discharge

The 30 days run from the **`STOP` (discharge)** of the index admission, never from its
`START`. Anchoring on admission shortens the effective follow-up window by the length of
the index stay, so it undercounts — and it undercounts *non-uniformly*, penalising
longer stays more. The resulting rate is lower, entirely plausible, and wrong in a way
nothing in the output reveals.

## Index admission eligibility

An inpatient admission is an index admission unless excluded. Exclude:

- **In-hospital deaths.** The patient cannot be readmitted; leaving them in the
  denominator understates the rate.
- **Transfers to another acute facility.** The episode of care has not ended, so the
  transfer-out is not a discharge to the community.
- **Discharges against medical advice (AMA).**
- **Still-admitted encounters.** No discharge date, so no window. See [[open_stays]].
- **Admissions with no observable 30-day window** — those discharged within 30 days of
  the end of the reporting period.

  **What this trades.** Excluding them shrinks the denominator, so the rate is computed
  over fewer admissions and is slightly noisier, and the most recent month of activity
  is absent from the figure. The alternative is worse: including them counts *"not yet
  observed"* as *"not readmitted"*, which is not a neutral assumption — it can only
  push the rate down, and it does so precisely on the newest data, which is where
  attention usually is. A rate that improves at the reporting boundary is the classic
  artifact this exclusion prevents. Report the count excluded so the denominator's
  shrinkage is visible.

## Which readmissions count

- **Any-facility, all-cause.** A readmission to a *different* organization counts.
  Restricting to the same facility undercounts and is a **different metric** — if a
  question asks for same-facility, it is asking for something else and this entry is
  not the right definition for it.
- **Planned readmissions do not count** — scheduled chemotherapy, staged procedures,
  planned rehabilitation.
- **One readmission per index admission.** A patient readmitted twice inside the window
  contributes one readmitted index admission, not two.
- A readmission may itself be an index admission for a subsequent window.

## Also required

Deduplicate encounters before computing either side of the ratio
([[encounter_deduplication]]), and resolve facility identity before any per-facility
breakdown ([[organization_identity]]).
