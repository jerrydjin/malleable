# Phase 15c: a fair labour priority test on Potrero

Origin rule written on 2 November 2026, before any 15c simulation or outcome.
Base: main e4ba2a6. No retained file is edited. The isolated build reuses the
unchanged experiments/phase15-v2 materializer and record-host patch.

## Origin selection (fixed before diagnostics)

Consider every deduplicated incoming cross-street road in the five retained
15b crossing flows, in ascending incoming-link order. Use its retained legal
connector onto the hospital corridor, then the unchanged corridor suffix to
hospital node 4. Enumerate every candidate and legal route, including any
structural exclusion, in assets/phase15c/origin-manifest.json.

For each legal candidate, move only the 15b claimant to that origin/route;
retain her ID, departure, request time and all other trips/demand. Both twins
use this same hospital route. Use the existing Mock grant/deny policy and
recorded nearby/500 m priority reach. Evaluate only SENSOR_ONLY at 300 m,
seeds 1–10, paired with a solo trip at the same departure/request on the same
route. No RECORD run or benefit comparison is allowed during selection.

The approach is the incoming road, including an identical parallel clone if
an existing safe lane change occurs, ending when the front enters its turn
connector. Approach excess = observed road dwell minus its solo dwell;
this excludes source waiting and the connector/downstream route. Also report
time below the existing QUEUED_MPS threshold on that road. Choose the candidate
with the largest median approach excess over the ten seeds; ties choose the
smallest incoming-link ID. A positive median is required for an on-map queue;
if no candidate has one, stop. Do not choose another candidate after validity.

## Validity, before registration

On the selected route, require approach excess >=30 s on >=8/10 seeds at
300 m in SENSOR_ONLY. Report every seed's approach excess, whole-trip on-map
excess, off-map waiting, and solo time separately. "Most delay is off-map"
means summed off-map waiting over the ten seeds exceeds summed positive
whole-trip on-map excess; also report that fraction per seed. Missing entries,
turns or finishes cannot pass. If either check fails, commit the result and
STOP without preregistration or outcome scoring. No origin/demand adjustment.

## Conditional outcome experiment

Only after passing validity and committing a separate dated preregistration
and code freeze: SENSOR_ONLY versus RECORD, labour and denied gym twin, seeds
1–10, ranges 60/150/300 m. Same map, 900 s arrivals, 1250 veh/h corridor and
retained crossing-flow rates, and inclusive 10,000 steps of 0.25 s. No signals,
sirens, queue reordering, model calls, or new motion actions are installed.
Judge, schema, make_way.rs and the v2 patch remain byte-identical.

300 m PASS requires claimant trip-time gain >=15 s on >=7/10 seeds; holding
cars' median extra delay <=10 s; all other cars' p95 <=30 s and max <60 s;
zero collisions/overlaps and all trips finish. Costs use matched arrival-time
loss, not commanded hold duration. Holding cars are distinct cars with an
accepted `hold` event for this claimant; their total and median loss remain
signed. "All other cars" includes holding cars, so also report the disjoint
non-holding group. Empty holder groups have count zero and null summaries;
no holder-cost assertion is inferred from an empty group. Gym must be denied
with zero gain/cost/edits/deliveries/actions. 60/150 m have no benefit/cost bar.
Every trip and unfinished status/final link is retained. No tuning after freeze.

## Reproduce

```sh
bash scripts/phase15c.sh build
bash scripts/phase15c.sh test --release
# Only after committing the code/rule:
bash scripts/phase15c.sh run part=origins
bash scripts/phase15c.sh run part=validity
# Only if validity passes and a dated registration/freeze is committed:
bash scripts/phase15c.sh run part=score
```

Commit order: code -> validity -> preregistration/freeze -> scores -> verification.
A required validity STOP ends this sequence after validity and verification.
