# Phase 16: STOP after the single authorized map expansion

STOP: the single authorized east-west expansion still has no drivable bypass from exit ramp 8915060 to affected destination 28326941 while avoiding tree edge 1343758309. No southbound on-ramp joins the post-tree mainline inside latitude 37.738 to 37.762; ramp 1164067021 leaves US-101 for I-280 South and is not a re-entry. No further widening or traffic, validity, record or spoof run was performed.

The expanded network was acquired, built and checked after runtime recovery.
The original structural checks pass. The added bypass requirement fails:
there is no directed surface-to-US-101 southbound re-entry after the fixed tree
and before the unchanged southern boundary. No traffic was started.

## Map change (pre-traffic)

| Bbox | West longitude | East longitude | South latitude | North latitude |
| --- | --- | --- | --- | --- |
| Previous | -122.410 | -122.400 | 37.738 | 37.762 |
| Authorized and tested | -122.425 | -122.385 | 37.738 | 37.762 |

Reason: **Widen west and east only so the surface grid can connect the last southbound exit to a US-101 southbound on-ramp beyond the unchanged tree; verify the connection rather than assume it exists.** The declaration was committed in `0b18df4`
before any traffic. This is the only bbox change. It was not widened again.
The [plan](../../experiments/phase16/map-change/plan.json) pins the original
tree point, closure and volume hashes. The tree remains at
longitude -122.40814970805161, latitude
37.73936974950687, at the original
1508.352460 m placement after the last exit
under the retained metric. Its 8 m all-lane
closure remains active at [240,1140) s; Caltrans volume stays 7600 veh/h per direction.

OSM acquisition uses tiles inside this same bbox to satisfy the API node limit.
The frozen original OSM entities take precedence in the overlap; added tiles
supply the new geographic coverage. Raw tiles, merge policy, versions and
SHA-256 hashes are in
[acquisition.json](../../experiments/phase16/map-change/acquisition.json).
The merged OSM is geometrically clipped to exactly the authorized bbox before
`netconvert`; full source-way geometry outside it cannot create a bypass.

Runtime: **Eclipse SUMO sumo 1.28.0**. The network contains
**5007 normal road edges**, **12626 internal connector edges**
and **2487 nodes**. The native network, clipping provenance,
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
| Positive control, tree edge available | Yes | 2279.760000 | 103.438250 |

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
15732 nodes from the last exit without tree way
1343758309, but reaches **0 of 10 post-tree mainline nodes**.
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
| 300 m (primary) | FAIL — not measured; null | FAIL — not measured; null | FAIL — not measured; null | FAIL — not measured; null |
| 60 m (secondary) | FAIL — not measured; null | FAIL — not measured; null | FAIL — not measured; null | FAIL — not measured; null |
| 150 m (secondary) | FAIL — not measured; null | FAIL — not measured; null | FAIL — not measured; null | FAIL — not measured; null |

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
