# Coverage rate

The share of an encounter's cost **paid by the payer** rather than borne by the patient.

```
coverage_rate = PAYER_COVERAGE / TOTAL_CLAIM_COST
```

## When this is the right metric

Financial questions: patient responsibility, uncompensated care, and how generously a
given payer's plans cover a service line. It is a **cost** measure.

## Rules

- Exclude encounters with a zero or null total cost — the ratio is undefined, not zero.
- Aggregate as a **ratio of sums**, not a mean of per-encounter ratios: averaging ratios
  weights a $200 visit the same as a $60,000 stay.
- Normalise payer names before grouping. See [[payer_name_normalisation]].

## Not to be confused with

[[payer_mix_denominator]]. Payer mix is a **volume** distribution — what share of
encounters each payer accounts for. Coverage rate is a **cost** proportion within an
encounter. Both are percentages, both are reported by payer, and both look entirely
reasonable in a table; they answer unrelated questions.
