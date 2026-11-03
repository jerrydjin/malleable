#!/usr/bin/env python3
"""Reproduce the required prior-bar audit; never starts a simulation.

Expected exit code 2 means the user-required STOP was reproduced.
All source snapshots must equal their pinned Git objects before reading bars.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = "e9db1c51eb67b5e5470df82ebdbe6ba7267677e3"
STOP = (
    "STOP: Phase 15c has no outcome preregistration and its conditional "
    "trip-time gain bar is 15 s on 7/10 seeds, not 30 s. The requested "
    "unchanged 30 s on-map gain rationale is contradicted by the pinned "
    "Phase 15c declaration. No SUMO traffic, record arm or scored run was run."
)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def audit():
    sources = json.loads((HERE / "sources.json").read_text())
    for source in sources:
        snapshot = (HERE / source["archived_path"]).read_bytes()
        assert hashlib.sha256(snapshot).hexdigest() == source["sha256"]
        assert snapshot == git("show", source["commit"] + ":" + source["path"])
    declaration = (HERE / sources[0]["archived_path"]).read_text()
    results = (HERE / sources[1]["archived_path"]).read_text()
    gain = re.search(r"claimant trip-time gain >=(\d+) s on >=(\d+)/(\d+) seeds", declaration)
    validity = re.search(r"approach excess >=(\d+) s on >=(\d+)/(\d+) seeds", declaration)
    assert gain and validity
    assert "no 15c preregistration, outcome code freeze, RECORD outcome run or score matrix was created" in results
    paths = git("ls-tree", "-r", "--name-only", sources[0]["commit"]).decode().splitlines()
    preregs = [p for p in paths if "15c" in p and "prereg" in p.lower()]
    assert not preregs
    assert int(gain[1]) != 30
    retained_paths = ["maps/us101.osm", "maps/us101.json", "assets/phase15e/placement.json", "assets/phase15e/volume.json", "experiments/phase15e/traffic.rs"]
    hashes = {}
    for path in retained_paths:
        data = (ROOT / path).read_bytes()
        assert data == git("show", BASE + ":" + path)
        hashes[path] = hashlib.sha256(data).hexdigest()
    assert not git("diff", BASE, "--", "src")
    scores = (ROOT / "docs/gates/phase-16-scores.jsonl").read_text()
    assert scores == ""
    placement = json.loads((ROOT / "assets/phase15e/placement.json").read_text())
    return {
        "phase": "16", "decision": "STOP", "stop": STOP,
        "base_commit": BASE, "prior_phase_commit": sources[0]["commit"],
        "requested_gain_threshold_s": 30,
        "prior_conditional_gain_threshold_s": int(gain[1]),
        "prior_conditional_gain_required_seeds": int(gain[2]),
        "prior_total_seeds": int(gain[3]),
        "prior_baseline_approach_threshold_s": int(validity[1]),
        "prior_baseline_required_seeds": int(validity[2]),
        "prior_outcome_preregistration_paths": preregs,
        "sources": sources, "retained_input_sha256": hashes,
        "retained_placement": {
            "osm_way": placement["tree"]["osm_way"],
            "D_m": placement["tree"]["D_m"],
            "footprint_length_m": placement["footprint_length_m"],
            "start_s": placement["start_s"], "duration_s": placement["duration_s"],
        },
        "sumo_runtime_version": None,
        "setup_status": "installation failed; see setup.log",
        "src_unchanged_from_base": True,
        "scored_rows": len(scores.splitlines()),
        "execution_status": "Stopped during setup/prerequisite audit; map, demand, validity, record and spoof runs not performed",
        "bars": [
            {"bar": bar, "sensor_range_m": radius, "status": "FAIL", "evaluated": False,
             "observed_value": None, "reason": "Not evaluated: prerequisite STOP"}
            for radius in [300, 60, 150] for bar in ["a", "b", "c", "d"]
        ],
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
    raise SystemExit(2)
