# Payer mix denominator

**Payer mix is computed over encounters**: the share of encounters attributed to each
payer, within a stated encounter class and period.

```
payer_share[p] = encounters_with_payer_p / total_encounters_in_scope
```

## Why the denominator has to be stated

Three denominators are defensible and they give materially different answers:

- **Encounters** — the default here. Weights payers by volume of care delivered.
- **Distinct patients** — weights every patient equally regardless of how much care
  they consumed. Shifts share toward payers covering healthier populations.
- **Member-months** — weights by insured time. This is the actuarially correct basis for
  premium and utilisation work, and requires `payer_transitions` rather than
  `encounters`.

None is wrong in general; using one while reporting another is. **State the denominator
in the answer.**

## Rules

- Restrict to the encounter class the question asks about. Payer mix over *all*
  encounters is dominated by ambulatory and wellness volume and says little about
  inpatient economics. See [[admission]].
- **Normalise payer names before grouping.** See [[payer_name_normalisation]].
- **Deduplicate encounters first.** See [[encounter_deduplication]].
- Shares should sum to 1 within rounding. That they sum to 1 is **not** evidence they
  are correct — a split payer name produces shares that still sum to 1.
- Encounters with no payer are a real category. Report them explicitly as uninsured or
  self-pay rather than dropping them, which would silently inflate every other share.
