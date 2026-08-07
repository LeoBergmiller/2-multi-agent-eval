# Readmission window anchored on admission date

A construction in which the 30-day follow-up window runs from the **`START` (admission)**
of the index encounter rather than from its discharge.

## Where this appears

Some legacy internal reports and simplified extracts anchor on admission because it
avoids handling null discharge dates and needs only one timestamp. It is occasionally
encountered in ad-hoc analyses and in datasets where discharge is unreliable.

## Why it is not the standard, and why it is dangerous

Anchoring on admission **includes the index stay itself inside the follow-up window**,
so the time actually available for a readmission to occur is 30 days *minus the length
of the index stay*. The measured rate is therefore lower than the true 30-day rate, and
lower **non-uniformly**: a patient with a 12-day stay gets 18 days of observation, one
with a 2-day stay gets 28. The bias is largest exactly where readmission risk is
highest, so it compresses differences between facilities and makes sicker populations
look better managed.

Nothing in the output signals any of this. The rate is well-formed, stable, and
plausible.

## Not to be confused with

[[readmission_30day]], which anchors on **discharge**. Unless a question explicitly asks
for an admission-anchored construction — which is essentially never — this is the wrong
definition, not an alternative one.
