#!/usr/bin/env python3
"""Report the structural STOP; never turn an unrun arm into a measured zero."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "experiments/phase16/rerun"


def main():
    gate = json.loads((OUT / "map-gate.json").read_text())
    setup = json.loads((OUT / "setup.json").read_text())
    historical_stop = json.loads((ROOT / "experiments/phase16/audit.json").read_text())["stop"]
    assert gate["decision"] == "STOP"
    assert gate["map_gate_passed"] and not gate["affected_destination_alternative_gate_passed"]
    assert not (ROOT / "docs/gates/phase-16-scores.jsonl").read_bytes()
    required = {
        "a": "affected mean gain >=15 s on >=7/10 seeds; pooled 95% bootstrap CI excludes 0",
        "b": "0 collisions in every arm",
        "c": "spoof merges 0/10",
        "d": "unaffected mean travel time no more than 5% worse than see-only",
    }
    bars = [{"sensor_range_m": radius, "bar": bar, "requirement": text,
             "status": "FAIL", "evaluated": False, "value": None,
             "qualifying_seeds": None, "bootstrap_ci_95_s": None,
             "reason": "Required same-destination bypass absent; no traffic run"}
            for radius in (300, 60, 150) for bar, text in required.items()]
    result = {"decision": "STOP", "stop": gate["stop"], "bars": bars,
              "sumo_version": setup["sumo_version"], "scored_rows": 0,
              "validity_seeds_run": 0, "sumo_traffic_runs": 0,
              "record_runs": 0, "spoof_runs": 0, "model_calls": 0,
              "preregistered": False, "original_stop_commit": setup["stop_commit_preserved"]}
    (OUT / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    table = "\n".join(
        f"| {radius} m {'(primary)' if radius == 300 else '(secondary)'} | FAIL — null; seeds null/10, CI null | FAIL — null collisions | FAIL — null/10 merges | FAIL — null% |"
        for radius in (300, 60, 150))
    tree = gate["tree"]
    summary = f"""# Phase 16 citation-fix rerun: STOP at the required bypass

{gate['stop']}

The corrected gain bar is accepted: **15 s on at least 7/10 seeds**, plus the
new brief's pooled 95% bootstrap confidence interval excluding zero. No score
was seen under either citation. The earlier citation STOP commit
`{setup['stop_commit_preserved']}` remains in history; its exact
[report](../../experiments/phase16/rerun/original-summary.md),
[audit](../../experiments/phase16/audit.json), source snapshots and failed
setup log are retained. The [replacement request](../../experiments/phase16/rerun/rerun-request.txt)
authorizes this rerun; this is a new structural STOP.

## Setup and topology

Runtime: **{setup['sumo_version']}**. Installation succeeded in a writable
virtual environment. [Exact dependencies](../../experiments/phase16/rerun/requirements.txt),
[setup record](../../experiments/phase16/rerun/setup.json), and
[installation log](../../experiments/phase16/rerun/setup.log) are committed.

The unchanged OSM extract was geometrically clipped to exactly
37.738–37.762 latitude, −122.410–−122.400 longitude, then built with
`netconvert`. Clipping uses the unchanged 15e rectangle-clip function;
source OSM attributes and fully retained restriction relations are preserved.
Selecting intersecting OSM ways alone would retain geometry outside the box.
The resulting network has **{gate['network_edges']} edges and {gate['network_nodes']} nodes**.
The [build command/log](../../experiments/phase16/rerun/netconvert-command.json),
[clipping manifest](../../experiments/phase16/rerun/network/clipping.json), and
[SUMO network](../../experiments/phase16/rerun/network/us101.net.xml.gz) are retained.
`netconvert` warnings, including ignored restriction relations, remain in
[the full log](../../experiments/phase16/rerun/netconvert.log).

| Required structural check | Result | Evidence in map-gate.json |
| --- | --- | --- |
| US-101 continuous both ways through the box | PASS | Both directed mainline paths are listed. |
| Last southbound exit connected to surface streets | PASS | Node 729040229, ramp 8915060, nonempty reachable surface set. |
| Fixed tree maps to mainline | PASS | Way {tree['source_way']}, {tree['sumo_edge_lanes']} lanes, projection distance {tree['projection_distance_m']:.6f} m. |
| Every affected through trip has an alternative from that exit | FAIL | Destination 28326941 is unreachable when tree way 1343758309 is excluded. |

The tree remains at the retained geographic midpoint of host edge
{tree['host_edge']}, **{tree['distance_from_exit_retained_m']:.6f} m** after the last exit
under the original placement metric. Its **{tree['footprint_length_m']} m**, all-lane closure
still starts at **{tree['start_s']} s** and lasts **{tree['duration_s']} s**. It was not
relocated to a SUMO distance chosen for a better route.

Exhaustive passenger-edge reachability from the ramp visits
**{gate['reachable_avoiding_tree_count']} edges**, but reaches **0** of the post-tree mainline
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
{table}

No efficacy preregistration, traffic/record implementation, merge/spoof tests,
FCD file or replay was created after this STOP. The board replay format is
documented in `src/replay.rs` and `src/network.rs`; no FCD exists to convert.
All new executable code is under `experiments/phase16/`. Every `src/` file and
the fixed 15e map, placement, volume and closure inputs remain unchanged.

## Citation and verification

> {setup['reason_for_bar_a']}

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
"""
    (ROOT / "docs/gates/phase-16-summary.md").write_text(summary)
    body = f"""The citation-fix rerun accepts the corrected **15 s on at least 7/10 seeds** gain bar. SUMO **1.28.0** installs and the fixed map passes its three structural checks, but the required same-destination surface alternative is absent.

> {gate['stop']}

The exact-box SUMO network keeps both US-101 directions continuous, the last SB ramp (`8915060`) connected to surface streets, and the original five-lane tree way (`1343758309`). From that ramp, exhaustive passenger connectivity cannot reach any of the three post-tree mainline edges while avoiding the tree. The retained 15e graph independently gives the same no-path result even without turn/lane restrictions. The map was not expanded and affected destinations were not substituted.

| Range | a: affected mean gain / pooled 95% CI | b: collisions | c: spoof merges | d: unaffected mean cost |
| --- | --- | --- | --- | --- |
{table}

Every bar is **FAIL — not evaluated** at this prerequisite STOP. Numeric values are **null**. There were **0 traffic runs, 0 validity seeds, 0 record/spoof runs and 0 scored rows**. No preregistration, FCD/replay or merge/spoof tests followed the STOP; no measured zero is invented.

The fixed bbox, OSM extract, tree location (1508.352460 m under the retained placement metric), 8 m all-lane footprint, `[240,1140)` closure and 7600 veh/h/direction remain unchanged. Setup records the new brief's full peak-hour arrival duration; no demand was run. All `src/` files are unchanged. All new executable code is isolated in `experiments/phase16/`.

Evidence: `experiments/phase16/rerun/map-gate.json`, exact clipped OSM/SUMO network, netconvert log, setup/dependency versions, machine-readable `results.json` and `verification.json`; full report `docs/gates/phase-16-summary.md`.

Earlier citation STOP commit `cafad04` and its audit/source/setup artifacts remain intact. Its exact original summary is archived at `experiments/phase16/rerun/original-summary.md`. The original audit reproduces byte for byte; the new static audit reproduces the topology STOP. No traffic efficacy claim is made.

Historical citation STOP (resolved by the updated brief; retained verbatim):

> {historical_stop}

**Handoff:** Jerry reviews PR #48's topology STOP; changing the map extent or affected destination requires a revised experiment before traffic.
"""
    (OUT / "PR_BODY.md").write_text(body)


if __name__ == "__main__":
    main()
