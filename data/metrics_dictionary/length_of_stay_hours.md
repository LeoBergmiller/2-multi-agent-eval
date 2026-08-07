# Length of stay — elapsed hours

The **elapsed clock time** between an encounter's `START` and `STOP`, expressed in hours
or fractional days.

```
los_hours = date_diff('hour', START, STOP)
```

## When this is the right metric

Short-duration settings where midnights are too coarse to be informative: emergency
department throughput, observation units, procedural recovery, and time-to-treatment
measures. For an encounter lasting under a day, elapsed time is the only meaningful
duration.

## Why it is wrong for inpatient length of stay

Inpatient LOS measures **bed-nights consumed**, which is a count of midnights crossed,
not a duration. A patient admitted at 23:00 and discharged at 07:00 has occupied a bed
overnight — one midnight — but only 8 elapsed hours, which this construction reports as
0.33 days. Averaged across a population it systematically understates utilisation, and
it does so most for short stays, which are the majority.

## Not to be confused with

[[length_of_stay]]. Elapsed time and midnights answer different questions and are not
convertible into one another without the admission and discharge times of every stay.
