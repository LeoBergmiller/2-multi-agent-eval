# Encounter volume

The total count of **encounters of all classes** in a period: ambulatory, emergency,
home, hospice, inpatient, outpatient, snf, urgentcare, virtual and wellness combined.

## When this is the right metric

Whole-organisation activity: total patient contacts, system-wide throughput, capacity
across all care settings, or denominators for organisation-wide rates. It is a real and
useful measure when the question is genuinely about all contact with the health system.

## Rules

- Deduplicate by encounter `Id` first. See [[encounter_deduplication]].
- State the classes included. "Encounter volume" without qualification is ambiguous
  across organisations and should always be reported with its scope.

## Not to be confused with

[[admission]]. An admission is specifically an `inpatient` encounter, and the
non-inpatient classes outnumber inpatient by more than an order of magnitude — so
answering an admissions question with encounter volume is wrong by a factor of tens,
not by a margin. This is the single most consequential substitution in the dictionary:
both numbers are legitimate, both are large and plausible, and nothing about the result
indicates which was computed.
