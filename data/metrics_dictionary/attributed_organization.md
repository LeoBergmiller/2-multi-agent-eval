# Attributed organization

The organization an encounter is attributed to is the one in the encounter's
**`ORGANIZATION`** field: the facility where the encounter took place.

Resolve that id to a stable identity before grouping — ids are not stable across a
facility reorganisation. See [[organization_identity]].

## For encounter-level measures

Volume, length of stay, and payer mix are attributed to the encounter's own
organization. There is no ambiguity here; the field says where the care happened.

## For readmission

**A readmission is attributed to the organization of the *index* admission**, not of the
readmission. The metric measures whether a discharging facility's patients came back —
so the facility being assessed is the one that discharged them.

Attributing to the readmitting facility inverts the meaning: a hospital that receives
other facilities' returning patients would score as if it had discharged them badly.
Both attributions produce a complete, plausible per-facility table; only one answers the
question. See [[readmission_30day]].

## Organization vs provider

`ORGANIZATION` is the facility; `PROVIDER` is an individual clinician. They are
different grains and are not interchangeable. A question about facilities, hospitals or
sites means `ORGANIZATION`. Provider-level attribution — admitting vs attending vs
discharging clinician — is a separate distinction and is not what "organization" means.
