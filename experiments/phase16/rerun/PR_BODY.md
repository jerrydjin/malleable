The citation-fix rerun accepts the corrected **15 s on at least 7/10 seeds** gain bar. SUMO **1.28.0** installs and the fixed map passes its three structural checks, but the required same-destination surface alternative is absent.

> STOP: the fixed SUMO map has no passenger-vehicle route from the last southbound exit to the retained destination beyond the tree while avoiding the blocked section. The required affected-trip alternative is absent; no traffic, validity, record or spoof run was started.

The exact-box SUMO network keeps both US-101 directions continuous, the last SB ramp (`8915060`) connected to surface streets, and the original five-lane tree way (`1343758309`). From that ramp, exhaustive passenger connectivity cannot reach any of the three post-tree mainline edges while avoiding the tree. The retained 15e graph independently gives the same no-path result even without turn/lane restrictions. The map was not expanded and affected destinations were not substituted.

| Range | a: affected mean gain / pooled 95% CI | b: collisions | c: spoof merges | d: unaffected mean cost |
| --- | --- | --- | --- | --- |
| 300 m (primary) | FAIL — null; seeds null/10, CI null | FAIL — null collisions | FAIL — null/10 merges | FAIL — null% |
| 60 m (secondary) | FAIL — null; seeds null/10, CI null | FAIL — null collisions | FAIL — null/10 merges | FAIL — null% |
| 150 m (secondary) | FAIL — null; seeds null/10, CI null | FAIL — null collisions | FAIL — null/10 merges | FAIL — null% |

Every bar is **FAIL — not evaluated** at this prerequisite STOP. Numeric values are **null**. There were **0 traffic runs, 0 validity seeds, 0 record/spoof runs and 0 scored rows**. No preregistration, FCD/replay or merge/spoof tests followed the STOP; no measured zero is invented.

The fixed bbox, OSM extract, tree location (1508.352460 m under the retained placement metric), 8 m all-lane footprint, `[240,1140)` closure and 7600 veh/h/direction remain unchanged. Setup records the new brief's full peak-hour arrival duration; no demand was run. All `src/` files are unchanged. All new executable code is isolated in `experiments/phase16/`.

Evidence: `experiments/phase16/rerun/map-gate.json`, exact clipped OSM/SUMO network, netconvert log, setup/dependency versions, machine-readable `results.json` and `verification.json`; full report `docs/gates/phase-16-summary.md`.

Earlier citation STOP commit `cafad04` and its audit/source/setup artifacts remain intact. Its exact original summary is archived at `experiments/phase16/rerun/original-summary.md`. The original audit reproduces byte for byte; the new static audit reproduces the topology STOP. No traffic efficacy claim is made.

Historical citation STOP (resolved by the updated brief; retained verbatim):

> STOP: Phase 15c has no outcome preregistration and its conditional trip-time gain bar is 15 s on 7/10 seeds, not 30 s. The requested unchanged 30 s on-map gain rationale is contradicted by the pinned Phase 15c declaration. No SUMO traffic, record arm or scored run was run.

**Handoff:** Jerry reviews PR #48's topology STOP; changing the map extent or affected destination requires a revised experiment before traffic.
