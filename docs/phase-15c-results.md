FAIL — baseline validity STOP: only 5/10 seeds reach 30 s on the approach; 8/10 were required.

# Phase 15c: fixed-origin baseline finding — 2 November 2026

The origin rule was committed in `26d619b` before any 15c origin diagnostic. It selects **link 493**, edge 261, from node 104 into node 55, turning through connector 1048 onto the unchanged hospital corridor. The route ends at hospital node **4**. The median on-map approach excess is **35.875 s**, but the ≥30 s condition holds on only **5/10 seeds**. All ten seeds remain in the result.

The second stop condition does not fail: **31.599%** of pooled claimant delay is off-map, below a majority. That does not rescue the failed per-seed requirement. The origin rule, map, demand, departure/request times, horizon and sensor range were not adjusted. No alternative origin was substituted.

**STOP:** no 15c preregistration, outcome code freeze, RECORD outcome run or score matrix was created. The priority benefit and cost bars were not tested. 60 m and 150 m sensitivities and the gym outcome matrix were not run, because the required 300 m SENSOR_ONLY baseline failed first. No PASS/FAIL conclusion about priority efficacy is inferred from this harness finding.

## All candidates under the fixed rule

Each legal route uses the retained crossing connector plus the existing hospital-corridor suffix. Every candidate was tested on all ten seeds using SENSOR_ONLY at 300 m, with a solo trip at the same departure/request on the same route. No RECORD benefit comparison was used to choose the origin.

| Incoming link | Edge | Junction | Median approach excess s | Seeds ≥30 s | Median whole-trip on-map excess s | Median off-map wait s | Pooled off-map fraction | Selected |
|---|---|---|---|---|---|---|---|---|
| 9 | 4 | 45 | 17.500 | 0 | 19.250 | 57.201 | 0.758 | false |
| 80 | 42 | 27 | 16.000 | 0 | 28.375 | 29.451 | 0.518 | false |
| 366 | 197 | 54 | 16.000 | 0 | 29.250 | 14.725 | 0.355 | false |
| 386 | 207 | 175 | 5.250 | 0 | 18.750 | 32.475 | 0.644 | false |
| 493 | 261 | 55 | 35.875 | 5 | 48.625 | 22.196 | 0.316 | true |

All **50 candidate/seed baselines finish every trip**, with zero collisions and overlaps. The complete candidate numbers, legal routes, solo traces and per-seed delays are retained in [origin-manifest.json](../assets/phase15c/origin-manifest.json). The independently rerun selected-route rows are in [validity.json](../assets/phase15c/validity.json).

## Selected approach: every seed

Approach excess subtracts solo dwell on the incoming road only. Off-map waiting starts at scheduled departure and ends at actual map entry; it never contributes to approach delay. Whole-trip on-map excess subtracts the same-route solo trip. Queue seconds use the existing speed <1 m/s threshold on that road. No delay is clamped or dropped in the displayed differences.

| Seed | Departure s | Request s | Approach excess s | Queued on approach s | Whole-trip on-map s | Solo on-map s | On-map excess s | Off-map wait s | Off-map fraction | ≥30 s | Finished |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 300.297 | 345.297 | 15.500 | 0.000 | 67.250 | 42.000 | 25.250 | 44.203 | 0.636 | false | 468/468 |
| 2 | 301.074 | 346.074 | 56.250 | 41.750 | 112.250 | 42.000 | 70.250 | 0.176 | 0.003 | true | 467/467 |
| 3 | 301.851 | 346.851 | 56.250 | 41.750 | 112.250 | 42.000 | 70.250 | 0.149 | 0.002 | true | 467/467 |
| 4 | 302.628 | 347.628 | 56.250 | 41.750 | 112.250 | 42.000 | 70.250 | 0.122 | 0.002 | true | 468/468 |
| 5 | 300.525 | 345.525 | 15.500 | 0.000 | 67.250 | 42.000 | 25.250 | 44.225 | 0.637 | false | 468/468 |
| 6 | 301.301 | 346.301 | 56.250 | 41.750 | 112.250 | 42.000 | 70.250 | 0.199 | 0.003 | true | 467/467 |
| 7 | 302.078 | 347.078 | 15.500 | 0.000 | 67.250 | 42.000 | 25.250 | 44.172 | 0.636 | false | 467/467 |
| 8 | 302.855 | 347.855 | 15.500 | 0.000 | 69.000 | 42.000 | 27.000 | 44.145 | 0.620 | false | 473/473 |
| 9 | 300.752 | 345.752 | 56.250 | 41.750 | 112.250 | 42.000 | 70.250 | 0.248 | 0.004 | true | 468/468 |
| 10 | 301.529 | 346.529 | 15.500 | 0.000 | 68.250 | 42.000 | 26.250 | 44.221 | 0.628 | false | 467/467 |

Source admission and motion are the retained v2 implementation. The observer is read-only; judge, schema, make_way.rs, v2 patch and every retained file are unchanged. No signals, sirens, queue reordering or model calls were introduced. The pre-validity input inventory is an execution record, **not an outcome preregistration**.
