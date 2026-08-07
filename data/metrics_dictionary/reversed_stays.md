# Discharge before admission — reversed stays

An encounter whose **discharge is before its admission** — `STOP` earlier than `START` —
is **invalid data**, not a real event.

These are encounters where the discharge date precedes the admission date, where the
stay appears to have ended before it began, and which therefore produce a **negative
length of stay**.

## Rule

**Exclude them. Do not clamp them to zero.**

Clamping is the tempting move and it is wrong: it converts a data-quality defect into a
same-day discharge, which is a legitimate and meaningfully different thing (see
[[length_of_stay]]). The count of genuine same-day discharges is itself an operational
signal, so contaminating it with corrupt rows corrupts that signal too.

## Why it must be handled explicitly

Duration arithmetic over these rows produces **negative** values. Negative durations do
not raise, do not fail a type check, and are silently absorbed into any average — where
they pull the result down by an amount that depends on how many slipped through. The
result is a plausible number that is quietly too low.

Any measure computing an interval from `START` and `STOP` must filter these first:
length of stay, time-to-readmission, throughput, bed-day utilisation.

## Reporting

Report the number of excluded rows. It is a data-quality metric in its own right, and a
sudden change in it is worth knowing about.
