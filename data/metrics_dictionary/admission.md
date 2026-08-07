# Admission

An **admission** is an encounter whose `ENCOUNTERCLASS` is `inpatient`.

No other encounter class counts. `encounters` mixes ten classes in one relation —
`ambulatory`, `emergency`, `home`, `hospice`, `inpatient`, `outpatient`, `snf`,
`urgentcare`, `virtual`, `wellness` — and the non-inpatient classes outnumber inpatient
by more than an order of magnitude. Counting every encounter row is therefore not a
small error; it is a wrong answer with the right shape, which is what this definition
exists to prevent.

## Boundary cases

- **Emergency encounters are not admissions.** A patient admitted from the emergency
  department appears as a *separate* `inpatient` encounter row. Count that row, not the
  emergency one, and do not count both.
- **Observation stays are not admissions.** They are outpatient by billing status even
  when the patient occupies a bed overnight.
- **`snf`, `hospice` and `home` are not admissions.** They are post-acute and
  community settings, not acute inpatient care.
- **Still-admitted patients count.** An encounter with a null `STOP` is an admission
  that has not ended yet. Filtering to `STOP IS NOT NULL` silently drops current
  inpatients and understates volume. See [[open_stays]].

## Counting

Count **encounters**, not patients. One patient with three separate inpatient stays
contributes three admissions. If a question asks for patients, count distinct patients
and say which unit was used.

Count **distinct encounters**, not rows — the source feed can double-post. See
[[encounter_deduplication]].
