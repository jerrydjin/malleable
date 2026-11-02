STOP — see-only validity fails: spillback on 10/10 seeds and no complete qualifying affected cohort.

# Phase 15e r2 retained validity failure — 2 November 2026

The user-authorized general ring fix passes the map gate, with zero dropped edges. Both US-101 directions keep their OSM lane counts and all 35 ramp segments connect. The earlier STOP commits **7b4fd03** and **8618bfd** remain in history; their notes and v1 failed artifacts are retained.

The fixed placement rule selects southbound **edge 1611**, OSM way **1343758309**, midpoint **1508.352460 m** after its prior exit, in the longest consecutive-exit gap of **1519.980218 m**. The map gate, placement, population and validity observer were committed before this traffic run. Caltrans demand stays **7600 veh/h per direction**, with unchanged local class rates, 900 s arrivals, 300 m sensing and the inclusive 10,000-step horizon.

The all-ten-seed **see-only** gate returns **STOP**. Queues reach the blocked-direction boundary with due demand still off-map on every seed. Every affected cohort is incomplete at the unchanged horizon; consequently **0/10 seeds have a complete qualifying median**, although the finite completions have large measured delays. Those censored summaries do not establish a full-cohort median. There are also nonzero host safety counters and unfinished trips. All zeros, failures, finite values and nulls remain in the raw file.

**No preregistration, RECORD arm, spoof outcome or efficacy score followed this failed validity check.** No placement, demand, horizon, sensor, route or observer adjustment was made after seeing it. This is a failed baseline/harness condition on the declared map and demand, not a measured RECORD-versus-eyesight benefit or loss.

## Every seed, including unfinished trips

The delay median below is **among completed affected trips only**, with its coverage shown explicitly. It is not a qualifying full-cohort estimate. Off-map wait summaries retain observations for affected cars that entered; never-entered trips remain explicit per-trip rows. Safety counters are cumulative host crossing-conflict/overlap observations, not distinct crash counts.

| Seed | Finished / trips | Affected paired / expected | Completed affected median excess s | Affected off-map p95 / max s | First boundary spill s | Spill duration s / peak pending | Collision / overlap / leak counters | Never entered / on-network at end |
|---|---|---|---|---|---|---|---|---|
| 1 | 9804/13034 | 72/1394 | 996.125 | 283.532 / 306.006 | 251.750 | 57.750 / 188 | 0 / 1938 / 0 | 1708 / 1522 |
| 2 | 10680/13034 | 661/1393 | 1408.750 | 790.143 / 919.880 | 251.750 | 50.250 / 153 | 0 / 1934 / 0 | 1585 / 769 |
| 3 | 10681/13034 | 663/1394 | 1404.000 | 808.055 / 965.990 | 251.750 | 47.250 / 234 | 0 / 1934 / 0 | 1585 / 768 |
| 4 | 10683/13034 | 664/1393 | 1401.500 | 808.956 / 962.061 | 257.000 | 49.500 / 142 | 0 / 1938 / 0 | 1585 / 766 |
| 5 | 10704/13063 | 661/1393 | 1408.500 | 809.462 / 945.383 | 240.250 | 49.500 / 188 | 0 / 1941 / 0 | 1590 / 769 |
| 6 | 10678/13034 | 659/1393 | 1401.750 | 809.374 / 974.742 | 254.000 | 53.250 / 216 | 0 / 1934 / 0 | 1585 / 771 |
| 7 | 10703/13063 | 660/1393 | 1410.000 | 801.196 / 981.314 | 240.500 | 49.500 / 211 | 0 / 1943 / 0 | 1590 / 770 |
| 8 | 10704/13069 | 657/1393 | 1405.750 | 800.175 / 960.281 | 241.500 | 51.500 / 236 | 0 / 1941 / 0 | 1592 / 773 |
| 9 | 10697/13063 | 654/1393 | 1409.750 | 802.772 / 909.495 | 254.500 | 50.500 / 125 | 0 / 1939 / 0 | 1590 / 776 |
| 10 | 10699/13063 | 656/1393 | 1409.000 | 806.593 / 964.962 | 253.750 | 48.500 / 242 | 0 / 1943 / 0 | 1590 / 774 |

All **130491 per-trip rows** remain in `assets/phase15e/validity.json`, including entry/home nulls, final links, on-map excess, off-map waiting and status. The exact code/input hashes are embedded in that file and the pre-validity SHA inventory remains unchanged.

All decisions read per-car KnownHazards. No model/API was called and no new physical action was introduced. Zero dropped OSM edges, the passing map gate and the general ring regression do not erase this failed real-traffic validity result. Verification after this STOP is limited to unchanged-byte checks, tests and identical reproduction of the retained failure.
