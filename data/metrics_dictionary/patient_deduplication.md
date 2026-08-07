# Patient deduplication

Resolving multiple patient records that refer to the **same person** — created by
registration errors, name changes, or records originating in different systems — into a
single identity.

## When this applies

Any per-patient measure: patient volume, per-patient utilisation, longitudinal
follow-up, and readmission (a readmission is only detectable if both encounters are
known to belong to the same person).

## Rules

- Match on a stable identifier where one exists. Demographic matching (name, date of
  birth, address) is probabilistic and produces both false merges and false splits.
- A **false split** understates per-patient utilisation and hides readmissions — the
  return visit looks like a different person's first visit.
- A **false merge** attributes one person's care to another and is harder to detect
  afterwards.

## Not to be confused with

[[encounter_deduplication]], which removes duplicate *rows describing the same
encounter* caused by a double-posted feed. These are different problems at different
grains: encounter deduplication fixes a delivery artifact and is resolved exactly by
`Id`; patient deduplication resolves identity across records and is never exact.

Applying either to the other's problem leaves it unfixed. Deduplicating encounters does
nothing for a split patient record, and resolving patient identity does nothing about a
row delivered twice.
