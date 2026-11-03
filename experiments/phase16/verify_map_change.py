#!/usr/bin/env python3
"""Reproduce the one expanded-map STOP and verify preserved inputs; no traffic."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "experiments/phase16/map-change"
BASE = "a7337c25fe41565f184b5799731a301988e1e3e7"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    plan = json.loads((OUT / "plan.json").read_text())
    acquisition = json.loads((OUT / "acquisition.json").read_text())
    assert plan["allowed_bbox_expansions"] == 1 and not plan["further_expansion_allowed"]
    assert plan["new_bbox_west_south_east_north"] == [-122.425, 37.738, -122.385, 37.762]
    source = OUT / "us101-expanded.osm.gz"
    assert sha(source.read_bytes()) == acquisition["merged_compressed_sha256"]
    assert sha(gzip.decompress(source.read_bytes())) == acquisition["merged_raw_sha256"]
    for tile in acquisition["tiles"]:
        data = (ROOT / tile["compressed_path"]).read_bytes()
        assert sha(data) == tile["compressed_sha256"]
        raw = gzip.decompress(data)
        assert sha(raw) == tile["raw_sha256"] and len(raw) == tile["raw_bytes"]
    assert not acquisition["tile_duplicate_version_conflicts"]
    for name, expected in plan["fixed_input_sha256"].items():
        assert sha((ROOT / name).read_bytes()) == expected, name
    allowed_changes = {"docs/gates/phase-16-summary.md", "experiments/phase16/README.md", "experiments/phase16/map_gate.py"}
    checked, preserved, src_count = 0, 0, 0
    for entry in git("ls-tree", "-r", "-z", BASE).split(b"\0"):
        if not entry:
            continue
        header, path = entry.split(b"\t", 1)
        mode, kind, expected = header.decode().split()
        name = path.decode()
        assert kind == "blob" and mode != "120000"
        data = (ROOT / name).read_bytes()
        actual = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        checked += 1
        if name not in allowed_changes:
            assert actual == expected, name
            preserved += 1
        if name.startswith("src/"):
            assert actual == expected, name
            src_count += 1
    for commit in ("cafad04f4635a8d8113874555425d525768a8e0d", BASE, "0b18df4", "b223bc28a14e1e7b54b25b827e209adf20b46e3c"):
        git("merge-base", "--is-ancestor", commit, "HEAD")
    blocker_path = "experiments/phase16/map-change/blocker.json"
    assert (ROOT / blocker_path).read_bytes() == git("show", "b223bc28a14e1e7b54b25b827e209adf20b46e3c:" + blocker_path)
    gate_path = OUT / "map-gate.json"
    before = gate_path.read_bytes()
    completed = subprocess.run([sys.executable, "experiments/phase16/map_gate.py", "--expanded"], cwd=ROOT, capture_output=True)
    assert completed.returncode == 2, completed.stderr.decode()
    assert gate_path.read_bytes() == before
    gate = json.loads(before)
    assert gate["map_gate_passed"] and not gate["affected_destination_alternative_gate_passed"]
    assert gate["bbox_west_south_east_north"] == plan["new_bbox_west_south_east_north"]
    for key in ("source_way", "host_edge", "distance_from_exit_retained_m", "source_center_lon_lat",
                "footprint_length_m", "start_s", "duration_s"):
        assert gate["tree"][key] == plan["retained_tree"][key], key
    assert not any(row["non_mainline_incoming_edges"] for row in gate["post_tree_incoming_connections"])
    for row in gate["destinations"]:
        assert not row["bypass_route"]["exists"]
        assert row["bypass_route"]["length_m"] is None and row["bypass_route"]["free_flow_time_s"] is None
    # Native SUMO routing independently checks the positive control's complete
    # length/time, including internal connectors. This starts no vehicle/time-step.
    import sumolib
    net = sumolib.net.readNet(str(OUT / "network/us101.net.xml.gz"), withInternal=True)
    control = gate["destinations"][0]["open_tree_control_route"]
    route, seconds = net.getFastestPath(net.getEdge("8915060"), net.getEdge("28326941"),
                                       vClass="passenger", withInternal=True)
    assert route is not None
    assert [e.getID() for e in route if not e.isSpecial()] == control["edges"]
    assert abs(seconds - control["free_flow_time_s"]) < 1e-9
    assert abs(sum(e.getLength() for e in route) - control["length_m"]) < 1e-6
    spec = importlib.util.spec_from_file_location("raw_audit", ROOT / "experiments/phase16/independent_raw_audit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = json.loads(json.dumps(module.audit(source)))
    retained_raw = json.loads((OUT / "expanded-raw-connectivity.json").read_text())
    # The local absolute path is provenance, not graph semantics in fresh clones.
    raw["source"] = retained_raw["source"]
    assert raw == retained_raw
    assert not raw["any_post_tree_node_reachable"] and not raw["incoming_non_mainline_way_ids"]
    old_path = ROOT / "experiments/phase16/rerun/map-gate.json"
    old = old_path.read_bytes()
    historical = subprocess.run([sys.executable, "experiments/phase16/map_gate.py"], cwd=ROOT, capture_output=True)
    assert historical.returncode == 2 and old_path.read_bytes() == old
    assert not (ROOT / "docs/gates/phase-16-scores.jsonl").read_bytes()
    assert not (ROOT / "docs/gates/phase-16-prereg.md").exists()
    subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
    record = {"passed": True, "expanded_audit_exit": completed.returncode,
              "expanded_audit_byte_exact": True, "historical_narrow_audit_preserved_and_reproduced": True,
              "raw_audit_reproduced": True, "source_tiles_verified": len(acquisition["tiles"]),
              "merged_source_raw_sha256_verified": True, "retained_base_commit": BASE,
              "retained_paths_checked": checked, "retained_paths_unchanged": preserved,
              "allowed_updated_paths": sorted(allowed_changes), "src_files_unchanged": src_count,
              "tree_point_closure_volume_unchanged": True, "bbox_expansions_used": 1,
              "native_control_route_time_s": seconds, "native_control_route_length_m": sum(e.getLength() for e in route),
              "bypass_route_exists": False, "bypass_route_length_m": None, "bypass_free_flow_time_s": None,
              "sumo_traffic_runs": 0, "validity_seeds_run": 0, "record_runs": 0, "spoof_runs": 0, "scored_rows": 0}
    (OUT / "verification.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    main()
