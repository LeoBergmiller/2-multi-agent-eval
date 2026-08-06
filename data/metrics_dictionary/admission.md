# Admission

An **admission** is an encounter whose `ENCOUNTERCLASS` is `inpatient`.

No other encounter class counts. The `encounters` table mixes `wellness`, `ambulatory`,
`outpatient`, `emergency`, `urgentcare` and `inpatient` rows in one relation, and the
non-inpatient classes outnumber inpatient encounters by roughly an order of magnitude.
Counting all encounters as admissions is therefore not a small error — it is a wrong
answer with the right shape, which is the failure mode this definition exists to prevent.

## Boundary cases

- **Emergency encounters are not admissions** unless the patient was subsequently admitted
  as an inpatient, which appears as a separate `inpatient` encounter row. Count that row,
  not the emergency one.
- **Observation stays are not admissions.** They are outpatient by billing status even when
  the patient occupies a bed overnight.
- **Still-admitted patients count.** An encounter with a null `STOP` is an admission that
  has not yet ended. Filtering to `STOP IS NOT NULL` silently drops current inpatients and
  understates volume.

## Counting

Count **encounters**, not patients. One patient with three separate inpatient stays
contributes three admissions. Use distinct patients only when the question asks for
patients, and say which was used.
