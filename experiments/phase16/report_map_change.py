#!/usr/bin/env python3
"""Report the completed single-expansion map gate, without traffic scoring."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "experiments/phase16/map-change"


def main():
    gate = json.loads((OUT / "map-gate.json").read_text())
    plan = json.loads((OUT / "plan.json").read_text())
    raw = json.loads((OUT / "expanded-raw-connectivity.json").read_text())
    execution = json.loads((OUT / "execution.json").read_text())
    assert gate["map_gate_passed"] and not gate["affected_destination_alternative_gate_passed"]
    assert gate["decision"] == "STOP" and not gate["further_expansion_allowed"]
    assert not (ROOT / "docs/gates/phase-16-scores.jsonl").read_bytes()
    bars = [{"range_m": radius, "bar": bar, "status": "FAIL", "evaluated": False,
             "observed_value": None, "qualifying_seeds": None, "bootstrap_ci_95_s": None,
             "reason": "Required bypass absent after the single authorized map expansion"}
            for radius in (300, 60, 150) for bar in ("a", "b", "c", "d")]
    results = {"decision": "STOP", "stop": gate["stop"], "bars": bars,
               "requirements": {"gain_s": 15, "gain_seeds": 7, "total_seeds": 10,
                                "pooled_bootstrap_confidence": 0.95, "ci_must_exclude": 0,
                                "collisions_per_arm": 0, "spoof_merges": 0,
                                "max_unaffected_mean_cost_fraction": 0.05},
               "bbox_expansions_used": 1, "sumo_traffic_runs": 0, "validity_seeds_run": 0,
               "record_runs": 0, "spoof_runs": 0, "scored_rows": 0,
               "preregistered": False, "further_widening_performed": False}
    (OUT / "results.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    table = "\n".join(
        f"| {radius} m {'(primary)' if radius == 300 else '(secondary)'} | FAIL — not measured; null | FAIL — not measured; null | FAIL — not measured; null | FAIL — not measured; null |"
        for radius in (300, 60, 150))
    control = gate["destinations"][0]["open_tree_control_route"]
    summary = f"""# Phase 16: STOP after the single authorized map expansion

{gate['stop']}

The expanded network was acquired, built and checked after runtime recovery.
The original structural checks pass. The added bypass requirement fails:
there is no directed surface-to-US-101 southbound re-entry after the fixed tree
and before the unchanged southern boundary. No traffic was started.

## Map change (pre-traffic)

| Bbox | West longitude | East longitude | South latitude | North latitude |
| --- | --- | --- | --- | --- |
| Previous | -122.410 | -122.400 | 37.738 | 37.762 |
| Authorized and tested | -122.425 | -122.385 | 37.738 | 37.762 |

Reason: **{plan['reason']}** The declaration was committed in `0b18df4`
before any traffic. This is the only bbox change. It was not widened again.
The [plan](../../experiments/phase16/map-change/plan.json) pins the original
tree point, closure and volume hashes. The tree remains at
longitude {gate['tree']['source_center_lon_lat'][0]}, latitude
{gate['tree']['source_center_lon_lat'][1]}, at the original
{gate['tree']['distance_from_exit_retained_m']:.6f} m placement after the last exit
under the retained metric. Its {gate['tree']['footprint_length_m']} m all-lane
closure remains active at [240,1140) s; Caltrans volume stays 7600 veh/h per direction.

OSM acquisition uses tiles inside this same bbox to satisfy the API node limit.
The frozen original OSM entities take precedence in the overlap; added tiles
supply the new geographic coverage. Raw tiles, merge policy, versions and
SHA-256 hashes are in
[acquisition.json](../../experiments/phase16/map-change/acquisition.json).
The merged OSM is geometrically clipped to exactly the authorized bbox before
`netconvert`; full source-way geometry outside it cannot create a bypass.

Runtime: **{execution['sumo_version']}**. The network contains
**{gate['network_edges']} normal road edges**, **{gate['network_internal_edges']} internal connector edges**
and **{gate['network_nodes']} nodes**. The native network, clipping provenance,
exact build command and warnings are retained under
[`experiments/phase16/map-change/`](../../experiments/phase16/map-change/).

## Completed map gate

| Required check | Result | Evidence |
| --- | --- | --- |
| US-101 mainline continuous both ways through the box | PASS | Both directed mainline paths are listed in map-gate.json. |
| Last SB exit ramp connects to surface streets | PASS | Exit node 729040229, ramp 8915060 and reachable surface edges are retained. |
| Unchanged tree point maps to US-101 mainline | PASS | Way 1343758309, five lanes; source point and projection are recorded. |
| Drivable route from the last exit to every affected destination avoids all closed edges | FAIL | No route from ramp 8915060 to retained destination 28326941 avoiding tree edge 1343758309. |

All affected southbound through trips retain the same destination from the
15e chain. Destinations were not changed to make the gate pass. Required route
metrics are explicit:

| Route from last exit to destination 28326941 | Exists | Length (m) | Free-flow time (s) |
| --- | --- | --- | --- |
| Required bypass, tree edge closed | No | null — unavailable | null — unavailable |
| Positive control, tree edge available | Yes | {control['length_m']:.6f} | {control['free_flow_time_s']:.6f} |

Length/time refer to the fastest static passenger route from the start of the
exit ramp through the destination's end, including internal connectors but
excluding signal/traffic waiting. The positive control traverses the tree;
it is not a bypass or a vehicle travel-time observation. Native SUMO routing
independently agrees with its full route, length and free-flow time.

The **missing link is a directed surface-to-SB-mainline incoming connection**
at any post-tree node inside the fixed latitude band. The three post-tree SUMO
edges `1164076368`, `28326944`, `28326941` each have only their preceding
mainline edge as an incoming road. At node `10824617369`, way `1164067021`
is an **outbound US-101 to I-280 South ramp**; it is not a southbound re-entry.
No outside on-ramp is invented or added.

An independent raw-OSM search on the expanded source permits all highway
classes and access values and ignores turn/lane restrictions. It reaches
{raw['reached_nodes_avoiding_tree']} nodes from the last exit without tree way
1343758309, but reaches **0 of {len(raw['post_tree_node_inventory'])} post-tree mainline nodes**.
The complete incoming-way inventory finds **0 non-mainline incoming ways**.
See [native map-gate.json](../../experiments/phase16/map-change/map-gate.json)
and [independent raw connectivity](../../experiments/phase16/map-change/expanded-raw-connectivity.json).
The historical narrow-map search is retained separately and is not used as
proof of the expanded result.

## Traffic and outcome bars

**0 SUMO traffic runs, 0 validity seeds, 0 record runs, 0 spoof runs and
0 scored JSONL rows.** The required map/bypass prerequisite failed before
demand or traffic. There is no measured collision, arrival, teleport,
spillback, gain, confidence interval or unaffected-cost outcome. No validity
retry was used. No efficacy preregistration, record/spoof tests or FCD/replay
was created after this STOP.

Bar a remains affected **mean** gain at least 15 s on at least 7/10 seeds,
with the pooled 95% bootstrap CI excluding zero. This is the corrected 15c
gain citation, [README line 50 at the pinned commit](https://github.com/jerrydjin/malleable/blob/6d8b38c3aa9bbaff670334a694cb011eb1228a16/experiments/phase15c/README.md#L50).
Bar b requires zero collisions in every arm; c requires spoof merges 0/10;
d requires unaffected mean cost no more than 5% worse. Every bar is **FAIL —
not evaluated because the required bypass is absent**. Null is unmeasured.

| Range | a. Mean gain / pooled CI | b. Collisions | c. Spoof merges | d. Unaffected mean cost |
| --- | --- | --- | --- | --- |
{table}

The [results.json](../../experiments/phase16/map-change/results.json) holds
the bars, declared requirements and execution counts. Caltrans 2016 AADT,
printed page 118, Army Street, SF postmile 2.92, ahead peak hour 15200/2,
remains the unchanged [volume source](../../assets/phase15e/volume.json).
No demand or closure tuning was performed.

## Preservation and reproduction

All `src/` files and fixed 15e inputs remain unchanged. All new executable code
is under `experiments/phase16/`. The citation STOP `cafad04`, narrow-map STOP
`a7337c2`, pre-traffic declaration and runtime interruption record `b223bc2`
remain in history. Their evidence files are preserved, including the exact
[previous summary](../../experiments/phase16/map-change/previous-summary.md)
and historical [runtime blocker](../../experiments/phase16/map-change/blocker.json).
The completed recovery/build is recorded in
[execution.json](../../experiments/phase16/map-change/execution.json).

```sh
python -m venv /tmp/phase16-verify
/tmp/phase16-verify/bin/pip install -r experiments/phase16/rerun/requirements.txt
PATH=/tmp/phase16-verify/bin:$PATH python experiments/phase16/map_gate.py --expanded
# Expected exit 2. Add --build to regenerate the clipped OSM/SUMO network.
PATH=/tmp/phase16-verify/bin:$PATH python experiments/phase16/verify_map_change.py
# Expected exit 0. No traffic or model call.
```

[verification.json](../../experiments/phase16/map-change/verification.json)
records input/tile hashes, unchanged retained files, exact native-gate replay,
the independent raw audit and the native routing cross-check. Use
`report_map_change.py` for this report; `report.py` belongs to the historical
narrow-map result.

**Handoff:** Jerry reviews PR #48's completed one-expansion STOP. No further
widening or traffic follows the failed required bypass.
"""
    (ROOT / "docs/gates/phase-16-summary.md").write_text(summary)
    body = f"""The single authorized west/east expansion was acquired, built and tested in SUMO 1.28.0. It passes the original map checks but **still fails the required bypass**.

> {gate['stop']}

**Map change (pre-traffic):** longitude changed from **[-122.410,-122.400]** to **[-122.425,-122.385]**; latitude stays **[37.738,37.762]**. The reason was to include a surface-grid connection to a southbound on-ramp past the tree. The original tree point, 8 m all-lane closure at [240,1140) s, and Caltrans 7600 veh/h/direction remain unchanged. The declaration precedes traffic; no second widening occurred.

The missing link is a **surface-to-US-101 southbound re-entry into the post-tree mainline inside the latitude bounds**. The three downstream edges have only preceding mainline incoming roads. Ramp `1164067021` at node `10824617369` leaves US-101 for I-280 South. Independent expanded raw-OSM connectivity and incoming-way inventory confirm the native SUMO result.

| Route from exit ramp 8915060 to affected destination 28326941 | Length m | Free-flow s |
| --- | --- | --- |
| Required bypass avoiding closed edge 1343758309 | null — no route | null — no route |
| Positive control with tree edge available | {control['length_m']:.6f} | {control['free_flow_time_s']:.6f} |

The control includes internal connectors and traverses the tree; it is not a bypass or measured vehicle time. Its route/length/time agree with native SUMO routing. Every affected through trip retains the original destination.

| Range | a: affected mean gain / pooled CI | b: collisions | c: spoof merges | d: unaffected mean cost |
| --- | --- | --- | --- | --- |
{table}

All outcome values are null, not measured zeros. **0 traffic runs, 0 validity seeds, 0 record/spoof runs and 0 scored rows.** Bar a stays 15 s on >=7/10 seeds plus the required pooled 95% bootstrap CI excluding zero. No efficacy preregistration, merge/spoof tests or FCD/replay followed this structural STOP.

Evidence: `docs/gates/phase-16-summary.md` and `experiments/phase16/map-change/{{plan,acquisition,map-gate,expanded-raw-connectivity,execution,results,verification}}.json`, frozen source tiles, clipped OSM, SUMO network and build log. Earlier STOPs and runtime interruption evidence remain intact. All `src/` files and fixed 15e inputs are unchanged; new code is isolated in `experiments/phase16/`.

Validation: expanded native gate reproduces its STOP; raw audit reproduces the missing re-entry; source/tile hashes and retained bytes verify; positive route cost agrees with SUMO. The runtime interruption is resolved.

**Handoff:** Jerry reviews PR #48's completed one-expansion STOP. No additional widening or traffic is authorized after the failed bypass.
"""
    (OUT / "PR_BODY.md").write_text(body)


if __name__ == "__main__":
    main()
