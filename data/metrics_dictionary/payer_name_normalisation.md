# Payer name normalisation

Payer names in the source arrive with **inconsistent casing and trailing whitespace**.
The same payer can appear as `Aetna`, `AETNA`, and `AETNA  ` across rows.

## Rule

**Group payers by `Id`, or by a normalised name** — trimmed of surrounding whitespace
and case-folded. Never group by the raw `NAME` string.

## Why this is silent rather than obvious

SQL string comparison is **case-sensitive**, unlike SQL identifiers. `'AETNA' = 'Aetna'`
is false, and `'AETNA  ' = 'AETNA'` is false. So a naive `GROUP BY NAME` splits one
payer into two or three separate rows.

The output still looks correct: every row has a plausible payer name, the counts are
positive, and the **shares still sum to 1**. The only visible symptom is that a payer
appears more than once in the result — which reads as a data quirk rather than an error,
and disappears entirely if the answer is truncated to a top-N list.

## Rules

- Prefer grouping on `payers.Id`, which is stable and unaffected by name formatting.
- When a name must be displayed, pick one canonical spelling per `Id` rather than
  showing whichever variant happened to sort first.
- Do not normalise by case-folding alone; trailing whitespace survives it.
- Applies wherever payers are aggregated — payer mix, coverage rates, revenue by payer.
  See [[payer_mix_denominator]].
