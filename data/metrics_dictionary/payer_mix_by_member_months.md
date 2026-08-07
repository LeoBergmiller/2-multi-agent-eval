# Payer mix by member-months

The share of total **member-months** attributable to each payer, where a member-month is
one covered person for one month of coverage.

Derived from `payer_transitions` (coverage spans) rather than from `encounters`.

## When this is the right metric

Actuarial and contracting work: premium calculations, per-member-per-month cost, risk
adjustment, and utilisation rates expressed per 1,000 member-months. It is the correct
exposure denominator when the question is about *insured time* rather than about care
delivered.

## Why it needs a different table

Encounters record care; they say nothing about months in which a member was covered and
consumed none. Member-months therefore cannot be derived from `encounters` at all —
computing it from encounter rows measures utilisation, not exposure, and the two diverge
most for healthy populations.

## Not to be confused with

[[payer_mix_denominator]] (encounter-weighted) or [[payer_mix_by_patient]]
(patient-weighted). All three are legitimate payer-mix definitions over the same period
and produce different numbers. This one is the only one that answers "how much coverage
did each payer provide"; the others answer "how much care".
