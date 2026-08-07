# Attributed provider

The individual clinician an encounter is attributed to, from the encounter's
**`PROVIDER`** field.

## The admitting / attending / discharging distinction

For an inpatient stay these can be three different people:

- **Admitting** — wrote the admission order. Relevant to access and referral patterns.
- **Attending** — held responsibility for the stay. The default for clinical quality
  attribution, and the one meant when a question says "the patient's doctor".
- **Discharging** — signed the discharge. Relevant to discharge-process measures and
  early readmission.

The `PROVIDER` field records a single clinician per encounter and does not distinguish
these roles. Any question that turns on the distinction needs it stated as an assumption
rather than inferred from the field.

## Not to be confused with

[[attributed_organization]]. Provider is an individual; organization is a facility.
They are different grains, and a "top performers" answer computed at the wrong grain is
not merely mis-scaled — it lists the wrong entities entirely. A question about
hospitals, sites or facilities means organization; only a question about clinicians
means provider.
