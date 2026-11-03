#!/usr/bin/env python3
"""Verify preservation and reproduce both STOP audits without running traffic."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "experiments/phase16/rerun"
STOP = "cafad04f4635a8d8113874555425d525768a8e0d"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    git("merge-base", "--is-ancestor", STOP, "HEAD")
    assert git("branch", "--show-current").decode().strip() == "phase-16-sumo"
    archived = {
        "docs/gates/phase-16-summary.md": "original-summary.md",
        "experiments/phase16/README.md": "original-README.md",
    }
    files = []
    source_count = 0
    entries = [entry for entry in git("ls-tree", "-r", "-z", STOP).split(b"\0") if entry]
    for entry in entries:
        header, name = entry.split(b"\t", 1)
        mode, kind, expected = header.decode().split()
        assert kind == "blob" and mode != "120000", "unexpected retained path type"
        path = os.fsdecode(name)
        data = (ROOT / path).read_bytes()
        actual = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        if path in archived:
            original = (OUT / archived[path]).read_bytes()
            assert hashlib.sha1(f"blob {len(original)}\0".encode() + original).hexdigest() == expected
            status = "original archived byte-exact; current report updated"
        else:
            assert actual == expected, f"retained file changed: {path}"
            status = "unchanged"
        if path.startswith("src/"):
            source_count += 1
        files.append({"path": path, "status": status, "current_sha256": hashlib.sha256(data).hexdigest()})
    original = subprocess.run([sys.executable, "experiments/phase16/audit.py"], cwd=ROOT, capture_output=True)
    assert original.returncode == 2, original.stderr.decode()
    assert original.stdout == (ROOT / "experiments/phase16/audit.json").read_bytes()
    before = (OUT / "map-gate.json").read_bytes()
    resumed = subprocess.run([sys.executable, "experiments/phase16/map_gate.py"], cwd=ROOT, capture_output=True)
    assert resumed.returncode == 2, resumed.stderr.decode()
    assert before == (OUT / "map-gate.json").read_bytes(), "static audit did not reproduce byte-exactly"
    gate = json.loads(before)
    assert gate["map_gate_passed"] and not gate["affected_destination_alternative_gate_passed"]
    assert all(c["continuous"] for c in gate["mainline_chains"])
    assert gate["destinations"][0]["path_via_ramp_before_closure"] is not None
    assert gate["destinations"][0]["path_avoiding_tree"] is None
    assert not gate["reachable_post_tree_mainline"]
    assert not gate["independent_retained_graph_confirmation"]["destination_reachable"]
    assert not any(gate["independent_retained_graph_confirmation"]["post_tree_road_origins_reachable"].values())
    assert not (ROOT / "docs/gates/phase-16-scores.jsonl").read_bytes()
    assert not (ROOT / "docs/gates/phase-16-prereg.md").exists()
    assert not git("diff", STOP, "--", "src/")
    for entry in gate["retained_input_sha256"].items():
        path, expected = entry
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected
    subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
    result = {
        "passed": True, "original_stop_commit": STOP, "original_stop_is_ancestor": True,
        "original_tracked_files_checked": len(files),
        "original_files_unchanged": sum(f["status"] == "unchanged" for f in files),
        "original_reports_archived_byte_exact": len(archived), "src_files_unchanged": source_count,
        "original_citation_audit_exit": original.returncode, "original_audit_byte_exact": True,
        "resumed_map_audit_exit": resumed.returncode, "resumed_audit_byte_exact": True,
        "positive_connectivity_check": "same destination reachable from exit when tree way is available",
        "negative_connectivity_check": "same destination and all three downstream mainline edges unreachable when tree way is excluded",
        "independent_relaxed_graph_confirms_no_path": True,
        "scored_rows": 0, "sumo_traffic_runs": 0, "model_calls": 0,
        "record_merge_spoof_tests": "not created or run after structural STOP",
        "files": files}
    (OUT / "verification.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "files"}, sort_keys=True))


if __name__ == "__main__":
    main()
