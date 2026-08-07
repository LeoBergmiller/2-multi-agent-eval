# Organization identity

**Group by the organization's identity, not by its `ORGANIZATION` id.**

An organization's id is not stable over time. A facility that is reorganised, merged, or
re-registered receives a new id, and its encounters split at the cutover date: earlier
encounters carry the old id, later ones the new. Both ids remain present in
`organizations` under the same `NAME`.

## Consequence

Grouping by `ORGANIZATION` reports one hospital as two, roughly halving its apparent
volume and pushing it down any "busiest facility" ranking. Both fragments are internally
consistent, the totals still reconcile, and nothing about the result looks wrong.

## Rule

Resolve the id to the organization's `NAME` (joining `organizations`) and group on
that, or maintain an explicit id-to-identity mapping. A "top N facilities" answer
computed on raw ids can be wrong about *which* facilities are in the list, not merely
about their values — which is why this matters for rankings specifically.

## Caution

`NAME` alone is not a universal key: distinct sites can legitimately share a name (a
system's several clinics named for the same town). Use name **plus** a stable
discriminator such as city or address when resolving, and do not merge two
organizations that share a name but differ in location.
