# Phase 16: single authorized expansion stops at missing SB re-entry

The one authorized west/east bbox expansion has now been built and checked.
Original map checks pass; the required surface-to-southbound re-entry beyond
the fixed tree is absent within the unchanged latitude bounds. No second
widening, traffic, validity, record or spoof run followed the failed gate.

Current evidence and commands are in [the summary](../../docs/gates/phase-16-summary.md)
and [map-change/map-gate.json](map-change/map-gate.json). Use `map_gate.py --expanded`
for the expanded audit (expected exit 2), `verify_map_change.py` for offline
preservation/reproduction (expected exit 0), and `report_map_change.py` to
regenerate the current report. Default `map_gate.py` and `report.py` refer to
the historical narrow-map result below. Earlier STOP artifacts remain intact.

## Historical narrow-map result

The updated request corrects the prior gain citation to 15 s on at least 7/10
seeds and authorizes a rerun on this branch. SUMO 1.28.0 installs successfully.
The fixed-box SUMO network passes the stated map gate, but has no route from
the last southbound exit to the retained destination beyond the tree while
avoiding the blocked road. The required affected-trip alternative fails.

No traffic, validity, record or spoof arm was run. No scored result or efficacy
preregistration follows this structural STOP. See the current
[summary](../../docs/gates/phase-16-summary.md) and
[machine-readable gate](rerun/map-gate.json).

All new code stays here. The fixed 15e inputs and every `src/` file remain
unchanged. The original STOP commit, audit, snapshots and setup log are kept;
the exact original [summary](rerun/original-summary.md) and
[README](rerun/original-README.md) are archived.

Install the pinned dependencies into a writable virtual environment:

```sh
python -m venv /tmp/phase16-verify
/tmp/phase16-verify/bin/pip install -r experiments/phase16/rerun/requirements.txt
PATH=/tmp/phase16-verify/bin:$PATH python experiments/phase16/map_gate.py
# Expected exit 2. Add --build to regenerate clipped OSM and the SUMO network.
PATH=/tmp/phase16-verify/bin:$PATH python experiments/phase16/verify_rerun.py
# Expected exit 0; verifies the STOP and preservation, without traffic.
```

The verification command also needs the original pinned 15c evidence commit
in the local Git object database; fetch it with the command below if absent.
`report.py` regenerates only the JSON/Markdown report from the retained gate.

## Original citation STOP (historical)

The requested branch starts at Phase 15e PR #46 head
`e9db1c51eb67b5e5470df82ebdbe6ba7267677e3`. Its setup, placement and closure
files were read first. Their hashes remain in `audit.json`.

The required check of Phase 15c found a different conditional benefit bar and
no outcome preregistration. The brief explicitly requires STOP in that case.
No traffic or scored arm ran. See [the complete summary](../../docs/gates/phase-16-summary.md).

`evidence/` contains byte-exact source snapshots from the pinned Phase 15c
commit; `sources.json` gives their original paths, immutable URLs and hashes.
These are audit evidence, not a claim that Phase 15c files existed on the
requested Phase 15e base. The failed setup attempt is in `setup.log`.

To reproduce the audit in a fresh checkout, fetch the pinned evidence commit:

```sh
git fetch origin 6d8b38c3aa9bbaff670334a694cb011eb1228a16
python experiments/phase16/audit.py > /tmp/phase16-audit.json
# Exit 2 is the expected mandatory STOP; then compare the output:
cmp experiments/phase16/audit.json /tmp/phase16-audit.json
```

The audit starts no simulation. It verifies the source snapshots against their
Git objects, checks the absence of a Phase 15c preregistration path, reproduces
the differing thresholds, and verifies unchanged retained inputs and `src/`.
The empty scores file records zero scored rows. It has no invented per-seed
measurements. No preregistration, record implementation, merge tests or replay
was created after this prerequisite STOP.
