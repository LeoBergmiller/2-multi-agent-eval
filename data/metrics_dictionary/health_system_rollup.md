# Health-system rollup

Aggregation of several organizations into the parent system or network that owns them.

## When this is the right metric

System-level reporting: total volume across a network, system market share, and
comparisons between health systems rather than between individual sites.

## Rules

- Rollup is a **deliberate aggregation across distinct facilities**, each of which
  remains a separate organization with its own id and name.
- Requires an ownership mapping. It cannot be inferred from name similarity — two sites
  sharing a town name may have different owners, and one system's sites frequently have
  unrelated names.

## Not to be confused with

[[organization_identity]], which resolves **one** organization whose id changed over
time back to itself. That is a correction of a data artifact; this is an intentional
grouping of genuinely different facilities.

Confusing them is bidirectional and both directions are wrong: rolling up when the
question asked per-facility hides site-level variation, and treating an id change as a
merger of two facilities invents a site that never existed.
