# Bed-day utilisation

The total **occupied bed-days** over a period, expressed against available bed capacity.

```
occupancy_rate = total_bed_days / (staffed_beds * days_in_period)
```

Bed-days are summed across encounters, where each encounter contributes its midnight
count. This is a **capacity** measure: it describes how full the hospital was, not how
long an individual stay lasted.

## When this is the right metric

Capacity planning, staffing, and surge analysis — questions about whether the facility
has enough beds, not about how long patients stay.

## Rules

- Unlike per-stay length of stay, **open stays contribute** their bed-days to date: a
  patient in a bed today occupies it whether or not they have been discharged. See
  [[open_stays]] — the event is ongoing and the occupancy is real, even though the
  interval has not completed.
- Truncating long stays would understate real occupancy, so the
  [[length_of_stay]] outlier rule does **not** apply here.

## Not to be confused with

[[length_of_stay]], which is a per-encounter duration. A question about average stay
length is not answered by total bed-days, and dividing bed-days by encounters gives a
mean that includes the open stays LOS excludes.
