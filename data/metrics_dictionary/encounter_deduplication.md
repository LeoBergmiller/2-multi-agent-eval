# Encounter deduplication

The encounter feed can **double-post**: the same encounter is delivered more than once
and lands as multiple identical rows sharing one `Id`.

**Count distinct encounters by `Id`, never rows.** A duplicate is a delivery artifact,
not a second episode of care.

This applies to **any question that counts encounters** — "how many encounters",
"how many inpatient encounters started in a year", "encounter volume", "number of
visits", "how many stays". Every such count is a count of distinct encounters.

## Why this is not optional

`encounters` has no primary key, so the warehouse accepts duplicates without complaint.
The duplicated rows are byte-identical to the originals — same `Id`, same `START`, same
`PATIENT`, same costs — so nothing in the schema, the result shape or the query plan
indicates anything is wrong. A naive row count is plausible, stable across re-runs, and
too high. This is the failure mode most likely to go unnoticed, because the wrong answer
behaves exactly like a right one.

## Rules

- Deduplicate on `Id` **before** aggregating, not after. Deduplicating a count is not
  possible; deduplicating the row set is.
- Deduplication applies to any measure derived from encounters — volumes, length of
  stay, readmission denominators, payer mix. A duplicated encounter inflates every one
  of them.
- Sum-based measures are affected more severely than counts: a duplicated encounter
  double-counts its `TOTAL_CLAIM_COST` as well as its existence.
- Do **not** deduplicate on `(PATIENT, START)`. Two genuinely distinct encounters can
  legitimately share a patient and a start timestamp (a transfer between departments,
  a same-moment outpatient and inpatient record). `Id` is the identity.
