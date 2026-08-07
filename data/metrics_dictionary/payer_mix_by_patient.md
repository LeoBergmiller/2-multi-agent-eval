# Payer mix by distinct patients

The share of **distinct patients** whose care was covered by each payer.

```
payer_share[p] = distinct_patients_with_payer_p / distinct_patients_in_scope
```

## When this is the right metric

Population and panel questions: what the covered population looks like, contracting and
network questions, and anything where each person should count once regardless of how
much care they consumed.

## How it differs from the encounter-weighted view

It weights every patient equally, so it **shifts share toward payers covering healthier,
lower-utilising populations** and away from those covering the frequently-admitted. The
two views can rank payers differently, and both are correct answers to different
questions.

A patient covered by different payers during the period appears under each, so shares
computed this way can sum to more than 1 unless a single primary payer is assigned per
patient. State the rule used.

## Not to be confused with

[[payer_mix_denominator]], which is **encounter-weighted** and is the default when a
question does not specify. Reporting one while the question asked for the other produces
a plausible distribution that is wrong in ways no internal check would catch — both sum
to 1 and both list the same payers.
