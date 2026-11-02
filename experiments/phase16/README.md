# Phase 16: required prior-bar STOP

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
