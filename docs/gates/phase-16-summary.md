# Phase 16 citation-fix rerun: STOP at the required bypass

STOP: the fixed SUMO map has no passenger-vehicle route from the last southbound exit to the retained destination beyond the tree while avoiding the blocked section. The required affected-trip alternative is absent; no traffic, validity, record or spoof run was started.

The corrected gain bar is accepted: **15 s on at least 7/10 seeds**, plus the
new brief's pooled 95% bootstrap confidence interval excluding zero. No score
was seen under either citation. The earlier citation STOP commit
`cafad04f4635a8d8113874555425d525768a8e0d` remains in history; its exact
[report](../../experiments/phase16/rerun/original-summary.md),
[audit](../../experiments/phase16/audit.json), source snapshots and failed
setup log are retained. The [replacement request](../../experiments/phase16/rerun/rerun-request.txt)
authorizes this rerun; this is a new structural STOP.

## Setup and topology

Runtime: **Eclipse SUMO sumo 1.28.0**. Installation succeeded in a writable
virtual environment. [Exact dependencies](../../experiments/phase16/rerun/requirements.txt),
[setup record](../../experiments/phase16/rerun/setup.json), and
[installation log](../../experiments/phase16/rerun/setup.log) are committed.

The unchanged OSM extract was geometrically clipped to exactly
37.738–37.762 latitude, −122.410–−122.400 longitude, then built with
`netconvert`. Clipping uses the unchanged 15e rectangle-clip function;
source OSM attributes and fully retained restriction relations are preserved.
Selecting intersecting OSM ways alone would retain geometry outside the box.
The resulting network has **1250 edges and 673 nodes**.
The [build command/log](../../experiments/phase16/rerun/netconvert-command.json),
[clipping manifest](../../experiments/phase16/rerun/network/clipping.json), and
[SUMO network](../../experiments/phase16/rerun/network/us101.net.xml.gz) are retained.
`netconvert` warnings, including ignored restriction relations, remain in
[the full log](../../experiments/phase16/rerun/netconvert.log).

| Required structural check | Result | Evidence in map-gate.json |
| --- | --- | --- |
| US-101 continuous both ways through the box | PASS | Both directed mainline paths are listed. |
| Last southbound exit connected to surface streets | PASS | Node 729040229, ramp 8915060, nonempty reachable surface set. |
| Fixed tree maps to mainline | PASS | Way 1343758309, 5 lanes, projection distance 0.006643 m. |
| Every affected through trip has an alternative from that exit | FAIL | Destination 28326941 is unreachable when tree way 1343758309 is excluded. |

The tree remains at the retained geographic midpoint of host edge
1611, **1508.352460 m** after the last exit
under the original placement metric. Its **8 m**, all-lane closure
still starts at **240 s** and lasts **900 s**. It was not
relocated to a SUMO distance chosen for a better route.

Exhaustive passenger-edge reachability from the ramp visits
**1208 edges**, but reaches **0** of the post-tree mainline
edges `1164076368`, `28326944`, `28326941`. The same-destination route with
the tree way available is recorded, showing that the failed bypass test is
not simply a missing destination. An independent search of the retained 15e
directed graph, even ignoring turn and lane restrictions, also cannot reach
that destination without the blocked road. All paths, reachable sets,
coordinates and input hashes are in
[map-gate.json](../../experiments/phase16/rerun/map-gate.json).

Removing the tree way is a static reachability check: an 8 m cut across all
lanes on that way has the same connectivity effect. No closure physics or
vehicle trajectory was simulated. Waiting for reopening is not a surface
alternative. Using a different destination or extending the box would change
the specified experiment, so neither was done.

## Traffic and outcome bars

The demand remains **7600 veh/h per direction**, from Caltrans 2016 AADT,
printed page 118, route 101, SF postmile 2.92, Army Street: ahead peak hour
15200 divided equally. The equal directional split is an assumption, not a
published directional factor. The retained
[volume.json](../../assets/phase15e/volume.json) and
[source row](../../assets/phase15e/volume-source-row.json) are unchanged.
The new brief's peak-hour arrival duration is recorded as 3600 s in setup;
no demand population was materialized after the static alternative failed.

**0 SUMO traffic runs, 0 validity seeds, 0 record runs, 0 spoof runs,
0 model calls and 0 scored JSONL rows.** There is no measured collision,
arrival, teleport, spillback, gain, confidence-interval or unaffected-cost
result. The 8/10 validity requirement was never evaluated. No validity retry
was used; changing a missing route is not a physics-neutral horizon or
insertion fix.

Every bar below is **FAIL — not evaluated because the prerequisite failed**.
Null is unmeasured; it is not an observed zero. Machine-readable rows are in
[results.json](../../experiments/phase16/rerun/results.json).

| Range | a. Mean gain ≥15 s on ≥7/10; CI excludes 0 | b. Zero collisions | c. Spoof merges 0/10 | d. Unaffected cost ≤5% |
| --- | --- | --- | --- | --- |
| 300 m (primary) | FAIL — null; seeds null/10, CI null | FAIL — null collisions | FAIL — null/10 merges | FAIL — null% |
| 60 m (secondary) | FAIL — null; seeds null/10, CI null | FAIL — null collisions | FAIL — null/10 merges | FAIL — null% |
| 150 m (secondary) | FAIL — null; seeds null/10, CI null | FAIL — null collisions | FAIL — null/10 merges | FAIL — null% |

No efficacy preregistration, traffic/record implementation, merge/spoof tests,
FCD file or replay was created after this STOP. The board replay format is
documented in `src/replay.rs` and `src/network.rs`; no FCD exists to convert.
All new executable code is under `experiments/phase16/`. Every `src/` file and
the fixed 15e map, placement, volume and closure inputs remain unchanged.

## Citation and verification

> 15 s on at least 7 of 10 seeds is the phase 15c gain bar (experiments/phase15c/README.md, PR #45), reused unchanged so the freeway is not judged by a looser standard.

The pinned [15c declaration](https://github.com/jerrydjin/malleable/blob/6d8b38c3aa9bbaff670334a694cb011eb1228a16/experiments/phase15c/README.md#L50)
supports that corrected threshold. Its earlier failed baseline does not
establish freeway efficacy. The
[Caltrans primary source](https://dot.ca.gov/-/media/dot-media/programs/traffic-operations/documents/census/aadt/tc-2016-aadt-volumes-a11y.pdf)
is retained by exact row citation above; no new traffic-volume value was used.

Reproduce the static audit (expected exit **2**) with the pinned dependencies:

```sh
python -m venv /tmp/phase16-verify
/tmp/phase16-verify/bin/pip install -r experiments/phase16/rerun/requirements.txt
PATH=/tmp/phase16-verify/bin:$PATH python experiments/phase16/map_gate.py
```

Add `--build` to regenerate the clipped OSM and SUMO network. No command above
runs traffic. The original citation audit still reproduces byte for byte with
expected exit 2; the resumed static audit and preservation checks are recorded
in [verification.json](../../experiments/phase16/rerun/verification.json).

**Handoff:** Jerry reviews PR #48's new topology STOP. A different map extent
or affected destination needs an explicit revised experiment before traffic;
no efficacy inference follows from this graph check.

## Map change (pre-traffic)

The user authorizes one west/east expansion from longitude **−122.410 to −122.400** to **−122.425 to −122.385**; latitude stays **37.738 to 37.762**. The reason is to include a surface-grid connection from the last southbound exit to a southbound US-101 on-ramp past the unchanged tree. The tree point, closure and Caltrans volume stay fixed. This declaration precedes traffic. No second widening is authorized. The expanded-map gate is pending; no traffic runs have begun. The exact declaration and fixed-input hashes are in `experiments/phase16/map-change/plan.json`.
