# Phase 15 v2 preregistration — 2 November 2026

Registered before any v2 outcome score. Fix/test commit: `14d1ed97ffdf0b370fd34b19cbf84e3bfac65154`.
`gates/phase-15-v2-code-freeze.sha256` pins every retained and new code/input
file, and `assets/phase15/v2-generated-code.sha256` pins the complete generated
v2 crate. The gate verifies both manifests and requires this registration to
be committed before outcome runs. The NEAR matrix is scored first, then birth.

## Post-v1 disclosure and retained findings

The v1 harness problems were found **after v1 scoring**, including the supplied
seed-1, 300 m diagnosis for car 1146 (old free-flow 57.6 s, detour 74.2 s) and
the absent priority entries/public deliveries. All v1 source, inputs,
preregistrations, code freezes, scores and FAIL results remain byte-identical.
They are retained historical results, not evidence that a valid v2 hypothesis
was tested. No v1 result has been silently replaced.

The accepted FAR stop at `de1b1a2` is unchanged: no expected corridor edge has
its LAST TURN-OFF over 300 m upstream of the tree. No FAR scenario, map edit
or relaxed selection rule is introduced. The new user instruction explicitly
accepts **NEAR edge 15**, last turn-off **node 55**, **D = 85.1188329873662 m**,
as the control; labour is the claim. The retained structural audit and its
witnesses remain in the repository.

## V2 harness changes, fixed before this registration

V2 is an isolated build from the retained v1 sources plus the committed patch.
The root source tree remains unchanged; only the new v2 runner/gate opts into
the corrected record host. `make_way.rs`, judge and schema are unchanged in
both retained and generated code.

The old route's decision cost includes the car's **known remaining blockage**:
free-flow plus `max(expires_at - now, 0)`, only after its own knowledge timestamp.
It never consults incidents to obtain that cost. During pre-registration
validity testing, this time correction alone still produced no reroute because
the inherited emergency-yield **1.25 distance ceiling** vetoed a time-favourable
NEAR detour (703.7 m versus 554.0 m). V2 therefore adds a record-host-only
known-closure exception: compare the detour time plus the same occupancy delay
with the known old-route time and existing 3 s slack. Actual physical distances
are retained, not inflated. All route connectivity, same-current-link/sink,
claim and receiver safety constraints remain. Unknown/future/expired hazards
cannot supply a wait allowance. Other phases' make-way decisions are untouched.

Route-count/path caching is computation only: it preserves the original
per-candidate route counts, invalidates when occupied-link counts change and
after serial reroutes, and keys shortest paths by current link, sink and
KnownHazards. Equivalence is regression-tested. The six retained road-record regressions, including per-tick own-sight/receipt-before-reroute checks at all ranges and arms, also pass against the corrected host. The physical obstacle remains
an all-lane host blockage, including parallel clones, with unchanged existing
activation-clearance semantics. No model supplies motion controls.

A granted RECORD labour claim now creates a merged `kind: priority` edit with
author, route, issue/expiry time and chosen reach. Due per-edit/per-car receipts
populate `record.deliveries` and `record.delivered`; these receipts and the
merged edit are prerequisites for accepted RECORD lane changes and bounded
holds. SENSOR_ONLY uses local visibility and the existing Mock precedence;
it does not publish shared-record receipts. Priority evidence is the host
grant, not SAM imagery. The 3 s hold budget and original safe pull-over/rejoin
mechanism remain. No signal, siren, slot, Potrero queue-reordering or junction
layer is installed. KnownHazards alone drives hazard reroutes; ground truth
is confined to host physics and the range-checked physical sensor boundary.

## Validity checks, not outcome bars

Before registration, the exact-code **seed 1, 300 m RECORD** diagnostic passes:

- True NEAR edit merges and **43 hazard_reroute events** occur (required >=1).
- **80 distinct qualifying affected cars** are observed on-map, retaining the
  blocked edge on their route, before the last turn-off during the incident;
  **39 are simultaneously present** (both exceed 20).
- Labour is granted; **1 priority edit**, **70 due deliveries** and 88 accepted
  priority action records are present (required >=1 edit and >=1 delivery).
- Zero observed collisions/overlaps or leak violations in that diagnostic.

Qualifying coverage requires actual entry after start_s and an observation
while the car is physically on-map, still has the blocked edge on its remaining
route, is before the last turn-off, and time is in [start_s, expires_at).
The incident's unique and peak-simultaneous counts are both reported. Node
passing is observed at the corridor-node midpoint (including actual alternate
connectors leaving that node). A car diverting before reaching the node can
have a null passing time; null is never interpreted as zero.

These checks were diagnostic harness runs only, with no paired benefit
comparison, benefit-bar evaluation or parameter tuning. Initial validity
attempts exposed the distance-ceiling problem described above. The final
artifact `assets/phase15/v2-harness-validity.json` is bound to the exact
generated-code hash. Validity tests and outcome bars remain distinct; coverage
and wiring diagnostics will also be reported for every matrix row.

## Inputs and arms — unchanged limits

Map **maps/sf-zsfg.json**, cited Potrero **1,250 veh/h**, **900 s arrivals**,
300 s warm-up, original seeded departure/ID phase and 45 s request offset,
**seeds 1–10**, and original **10,000 steps at 0.25 s** (inclusive boundary,
last possible time 2500.25 s). Nothing extends that horizon. All v1 SAM photo,
mask and metadata stay byte-identical; no SAM is regenerated.

Run every arm at **60, 150 and 300 m**, using the same unoccluded straight-line
radius from the front to the footprint (or local priority issuer). **300 m**
is the control/claim range, citing [Waymo's published up-to-300-m lidar range](https://support.google.com/waymo/answer/9190838)
and its [2020 fifth-generation description](https://waymo.com/blog/2020/03/introducing-5th-generation-waymo-driver/).
**60 and 150 m are hypothetical sensitivities with no outcome bar.**

NEAR uses the unchanged centred eight-metre footprint on edge 15, start **240 s**
and **900 s hypothetical duration**. The new scenario and accepted-site manifest
are committed before registration. Every cited corridor trip is ordinary in
this tree experiment, preserving its ID/departure/request times. Arms:
SENSOR_ONLY, RECORD, diagnostic RECORD_CITY, and SPOOF. The spoof has identical
evidence/footprint/timing but no physical incident and compares to its own
identical-demand no-incident SENSOR_ONLY world. No proposal-only reroute is
allowed. A second distinct car must confirm the footprint from its own sensor
at a strictly later time; two negative reviewers or pending expiry reject it.

The model replies are the unchanged v1 recording, with source **model**:
route/1500 m for the tree and nearby/500 m for priority. SENSOR_ONLY learns
hazards only by own sight. Merged reach uses the existing 240 s lookahead,
10x message speed, 0.1 s hop delay and connected share 1.0. Host receipt timing
precedes actions. City is diagnostic only. Admission and lane inventory are
identical in paired arms. No API or Python call occurs during scoring; Python
only materializes the isolated build before registration/building.

Birth retains the complete v1 declaration/populations: one first corridor trip
departing at/after 300 s says **My partner is in active labour**, versus its
same-ID/time/route **I'm late for the gym** twin. The existing Mock policy
supplies grant/deny (source **mock**); the model supplies reach, not the grant.
Five identical crossing flows use the unchanged 13i class rule and seeded
phase, for 900 s of arrivals. SENSOR_ONLY and RECORD run both twins at all
three ranges. No tree is installed in these birth worlds.

## Estimands, coverage and reporting

Affected NEAR cohort: original route contains the blocked edge, and **paired
SENSOR_ONLY actual entry is after start_s**. Use that fixed baseline cohort,
not a treatment-dependent selection. Gain = baseline arrival minus arm arrival.
Unfinished or unentered trips remain in every row; missing arrivals/delays
are null and cannot complete a paired estimate. Unaffected losses compare all
other cars' arrival times. Empty groups are null with explicit count zero.
No seed is dropped. Every trip records completed/never-departed/never-entered/
on-network status and an on-network final link. Total delay includes source
waiting; on-map delay begins at actual entry, both versus a solo no-incident
trip on the identical host. Cost extrema retain negatives.

For every NEAR seed, range and arm report: original and observed blocked-route
cars; unique and simultaneous pre-turn-off coverage; edit merge time;
per-car last-turn-off passing time and signed merge-minus-pass time;
reroutes before/after own sight; total/on-map delays and RECORD_CITY costs.
No missing pass or censored completion is removed or recoded as zero.

For birth, one claimant per seed means its within-seed median is that paired
arrival gain. Report gain mean/min/max at every range across seeds, all others'
mean/p95/max per seed/range, and crossing-route cars separately. Report the
actual priority edits, due receipts and accepted actions for every seed/range.
Gym must have no gain/cost/action. The complete arrays remain in JSONL.

## Outcome bars — at 300 m, exactly as requested

**15a NEAR control:** absolute affected median gain **<10 s on >=8/10 seeds**;
unaffected/others **p95 loss <=30 s and maximum <60 s per seed**; true edit
merges **10/10**, spoof merges **0/10**. Preserve the original zero-collision,
zero-overlap, zero-spoof-reroute and zero-leak constraints across every range,
seed and arm. Report PASS only if all specified control/cost/merge/safety
conditions hold. RECORD_CITY is diagnostic, with no outcome bar.

**15b labour claim:** her gain **>0 s on >=8/10 seeds**; labour granted 10/10;
gym twin denied with **zero gain and zero cost**; others **p95 <=30 s and max
<60 s per seed**. Retain zero collisions/overlaps at every range. All ranges'
gym results are retained. No benefit bar is applied to 60 or 150 m.

No new numerical outcome bar is inferred from the validity checks. Full-pair
coverage is required to evaluate a seed's control/benefit/cost result; incomplete
rows are reported and do not count as successful paired results. Overall
completion, coverage and priority-wiring diagnostics are explicit output fields.

## Commit order, immutability and reproduction

1. Fixes, tests, NEAR input and exact-code validity artifacts: `14d1ed97ffdf0b370fd34b19cbf84e3bfac65154`.
2. This separate dated preregistration and root/generated code-freeze manifests.
3. Only then score NEAR first and commit its raw stdout/results; then score
   birth and commit its raw stdout/results. Do not edit frozen code in between.

```sh
bash scripts/phase15-v2.sh build
bash scripts/phase15-v2.sh run part=near seed=1 end=10
bash scripts/phase15-v2.sh run part=birth seed=1 end=10
```

No tuning after this registration. A bug requiring code changes needs a new
dated preregistration revision, retaining this one and explaining why; rerun
all ten seeds/ranges. Retain all zeros, negatives, unfinished trips and FAILs.
The FAR stop and all v1 files/results remain unchanged. Freeze deadline:
**Monday 2 November 2026, 23:00 UK (GMT)**.
