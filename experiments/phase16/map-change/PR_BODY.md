The single authorized west/east expansion was acquired, built and tested in SUMO 1.28.0. It passes the original map checks but **still fails the required bypass**.

> STOP: the single authorized east-west expansion still has no drivable bypass from exit ramp 8915060 to affected destination 28326941 while avoiding tree edge 1343758309. No southbound on-ramp joins the post-tree mainline inside latitude 37.738 to 37.762; ramp 1164067021 leaves US-101 for I-280 South and is not a re-entry. No further widening or traffic, validity, record or spoof run was performed.

**Map change (pre-traffic):** longitude changed from **[-122.410,-122.400]** to **[-122.425,-122.385]**; latitude stays **[37.738,37.762]**. The reason was to include a surface-grid connection to a southbound on-ramp past the tree. The original tree point, 8 m all-lane closure at [240,1140) s, and Caltrans 7600 veh/h/direction remain unchanged. The declaration precedes traffic; no second widening occurred.

The missing link is a **surface-to-US-101 southbound re-entry into the post-tree mainline inside the latitude bounds**. The three downstream edges have only preceding mainline incoming roads. Ramp `1164067021` at node `10824617369` leaves US-101 for I-280 South. Independent expanded raw-OSM connectivity and incoming-way inventory confirm the native SUMO result.

| Route from exit ramp 8915060 to affected destination 28326941 | Length m | Free-flow s |
| --- | --- | --- |
| Required bypass avoiding closed edge 1343758309 | null — no route | null — no route |
| Positive control with tree edge available | 2279.760000 | 103.438250 |

The control includes internal connectors and traverses the tree; it is not a bypass or measured vehicle time. Its route/length/time agree with native SUMO routing. Every affected through trip retains the original destination.

| Range | a: affected mean gain / pooled CI | b: collisions | c: spoof merges | d: unaffected mean cost |
| --- | --- | --- | --- | --- |
| 300 m (primary) | FAIL — not measured; null | FAIL — not measured; null | FAIL — not measured; null | FAIL — not measured; null |
| 60 m (secondary) | FAIL — not measured; null | FAIL — not measured; null | FAIL — not measured; null | FAIL — not measured; null |
| 150 m (secondary) | FAIL — not measured; null | FAIL — not measured; null | FAIL — not measured; null | FAIL — not measured; null |

All outcome values are null, not measured zeros. **0 traffic runs, 0 validity seeds, 0 record/spoof runs and 0 scored rows.** Bar a stays 15 s on >=7/10 seeds plus the required pooled 95% bootstrap CI excluding zero. No efficacy preregistration, merge/spoof tests or FCD/replay followed this structural STOP.

Evidence: `docs/gates/phase-16-summary.md` and `experiments/phase16/map-change/{plan,acquisition,map-gate,expanded-raw-connectivity,execution,results,verification}.json`, frozen source tiles, clipped OSM, SUMO network and build log. Earlier STOPs and runtime interruption evidence remain intact. All `src/` files and fixed 15e inputs are unchanged; new code is isolated in `experiments/phase16/`.

Validation: expanded native gate reproduces its STOP; raw audit reproduces the missing re-entry; source/tile hashes and retained bytes verify; positive route cost agrees with SUMO. The runtime interruption is resolved.

**Handoff:** Jerry reviews PR #48's completed one-expansion STOP. No additional widening or traffic is authorized after the failed bypass.
