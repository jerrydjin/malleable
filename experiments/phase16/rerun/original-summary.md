# Phase 16: STOP before SUMO traffic

**STOP: Phase 15c has no outcome preregistration and its conditional trip-time gain bar is 15 s on 7/10 seeds, not 30 s. The requested unchanged 30 s on-map gain rationale is contradicted by the pinned Phase 15c declaration. No SUMO traffic, record arm or scored run was run.**

The brief requires checking Phase 15c and stopping if its gain bar was not
30 s. Its [conditional declaration, line 50](https://github.com/jerrydjin/malleable/blob/6d8b38c3aa9bbaff670334a694cb011eb1228a16/experiments/phase15c/README.md#L50)
requires claimant trip-time gain **≥15 s on ≥7/10 seeds**. Its **30 s on ≥8/10**
condition concerns baseline approach delay
([lines 31–39](https://github.com/jerrydjin/malleable/blob/6d8b38c3aa9bbaff670334a694cb011eb1228a16/experiments/phase15c/README.md#L31)).
The [results, line 9](https://github.com/jerrydjin/malleable/blob/6d8b38c3aa9bbaff670334a694cb011eb1228a16/docs/phase-15c-results.md#L9)
explicitly say no outcome preregistration was created. These are distinct
quantities; the requested rationale cannot be preregistered truthfully.

Byte-exact copies and source hashes are committed under
[experiments/phase16/evidence](../../experiments/phase16/evidence/).
[audit.json](../../experiments/phase16/audit.json) contains every number and
decision reported here. [audit.py](../../experiments/phase16/audit.py)
reproduces the STOP with expected exit status 2. No efficacy conclusion is
drawn from the prerequisite failure.

| Range (m) | Bar a: affected mean gain and CI | Bar b: collisions | Bar c: spoof merges | Bar d: unaffected cost |
|---|---|---|---|---|
| 300 (primary) | FAIL — not evaluated | FAIL — not evaluated | FAIL — not evaluated | FAIL — not evaluated |
| 60 (secondary) | FAIL — not evaluated | FAIL — not evaluated | FAIL — not evaluated | FAIL — not evaluated |
| 150 (secondary) | FAIL — not evaluated | FAIL — not evaluated | FAIL — not evaluated | FAIL — not evaluated |

All observed values are **null**, not measured zeros. FAIL means the requested
bar was not demonstrated because execution stopped. The
[scores JSONL](phase-16-scores.jsonl) has **0 rows**: no seeds, arms or ranges
were run, including see-only validity. No FCD or board replay exists. No
record merge/spoof tests were run because the record implementation was not
reached. A Phase 16 preregistration was not created.

The branch starts at Phase 15e PR #46 head
`e9db1c51eb67b5e5470df82ebdbe6ba7267677e3`. Its unchanged extract, map,
placement, volume and closure-definition file hashes are recorded in the
audit. The retained placement is southbound, **1,508.3524600475923 m** after
the prior exit, with an **8 m** footprint starting at **240 s** for **900 s**.
These are retained input declarations, not SUMO measurements. No Rust file
in `src/` changed.

SUMO runtime version: **unavailable; installation did not complete**. The
already-started pip setup failed on the read-only user site directory;
[setup.log](../../experiments/phase16/setup.log) records the attempt. A package
resolver selection is not reported as a runtime version. No network was built
and the SUMO map gate was not evaluated after the decisive prior-bar mismatch.

Demand source retained from Phase 15e:
[Caltrans 2016 traffic census](https://dot.ca.gov/-/media/dot-media/programs/traffic-operations/documents/census/aadt/tc-2016-aadt-volumes-a11y.pdf),
as recorded in unchanged `assets/phase15e/volume.json`. No volume or closure
was changed. This STOP report provides no evidence for freeway warning efficacy.
