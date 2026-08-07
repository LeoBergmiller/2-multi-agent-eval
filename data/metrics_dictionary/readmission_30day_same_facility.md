# 30-day readmission rate — same facility only

The share of eligible index inpatient admissions followed by an unplanned inpatient
readmission **to the same organization** within 30 days of discharge.

Identical to [[readmission_30day]] in every respect — discharge-anchored window, index
eligibility, planned-readmission exclusion, one readmission per index admission —
**except** that a readmission counts only when it occurs at the organization that
discharged the patient.

## When this is the right metric

Use it when the question explicitly scopes to the same hospital, site, or organization:
"came back to us", "readmitted to the same facility", "our own readmissions". A question
that does not say so means the all-facility metric.

## What it measures differently

This is a **facility-operations** metric, not a population-outcome one. It answers "how
often do our discharges return to us", which a hospital can act on directly. It is
always **lower** than the any-facility rate, because readmissions to other organizations
are excluded rather than counted — so the two are not interchangeable and the difference
is not error.

Resolve organization identity before comparing, or a facility that changed its id will
appear to have no same-facility readmissions across the cutover. See
[[organization_identity]].

## Not to be confused with

[[readmission_30day]], the all-cause **any-facility** rate, which is the default when a
question does not specify. Applying the any-facility definition to a same-facility
question overcounts; applying this one to an unscoped question undercounts. Both produce
well-formed, plausible answers.
