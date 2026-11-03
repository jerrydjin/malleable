"""Freeze ordering and one-shot behavior in disposable Git repositories only."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import protocol


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


class FreezeProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="phase16d-protocol-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.experiment = self.root / protocol.EXPERIMENT
        self.experiment.mkdir(parents=True)
        self.git("init", "--quiet")
        self.git("config", "user.email", "protocol-tests@example.invalid")
        self.git("config", "user.name", "Phase 16d protocol test")
        (self.root / "STOP.md").write_text("Earlier structural STOP remains stopped.\n")
        self.git("add", "STOP.md")
        self.git("commit", "--quiet", "-m", "retained evidence")
        parent = self.git("rev-parse", "HEAD")
        write_json(self.experiment / "base-preservation.json", {
            "base_commit": parent,
            "files": [{"path": "STOP.md", "sha256": protocol.sha256(self.root / "STOP.md")}],
        })
        for relative in protocol._REQUIRED - {"base-preservation.json"}:
            path = self.experiment / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n" if path.suffix == ".json" else "fixture input\n")
        write_json(self.experiment / "config.json", {"emission": {"consecutive_frames": 6}})
        write_json(self.experiment / "dev-targets.json", {"required_consecutive_frames": 6})
        for relative in ("examples/phase16d_record.rs", "tests/phase16d.rs"):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("// frozen fixture\n")
        self.checkpoint = self.root / "checkpoint.bin"
        self.checkpoint.write_bytes(b"fixture checkpoint bytes; never inference weights")
        self.run = self.experiment / "runs" / "complete-development"
        self.run.mkdir(parents=True)
        self.validation_path = self.experiment / "runtime" / "validation.json"
        self.make_complete_evidence()
        self.commit("code, config and complete fixture evidence")

    def git(self, *arguments):
        return subprocess.run(["git", *arguments], cwd=self.root, capture_output=True,
                              text=True, check=True).stdout.strip()

    def commit(self, message):
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", message)

    def make_complete_evidence(self):
        current = protocol.code_manifest(self.root)
        runtime = self.experiment / "runtime"
        (runtime / "checks-python.log").write_text("Actual fixed clip repeat ... ok\n")
        (runtime / "checks-cargo.log").write_text("test result: ok. 218 passed; 0 failed; 3 ignored;\n")
        write_json(self.validation_path, {
            "code_manifest_sha256": current["sha256"],
            "python": {"status": "PASS", "failed": 0,
                       "outcomes": {protocol.DETERMINISM_TEST: {"status": "PASS"}}},
            "cargo": {"status": "PASS", "failed": 0, "log": "runtime/checks-cargo.log"},
            "sam_determinism": {"status": "PASS", "skipped": 0,
                                "test": protocol.DETERMINISM_TEST, "log": "runtime/checks-python.log"},
        })
        write_json(self.run / "dev-results.json", {
            "all_pass": True,
            "rows": [{"id": name, "pass": True}
                     for name in ("A_red_stationary", "A_white_moving", "B_red_stationary",
                                  "B_white_moving", "C_clear_road")],
            "required_consecutive_frames": 6, "labels_deferred": False,
            "evaluation_plan_sha256": protocol._digest(json.loads((self.experiment / "dev-targets.json").read_text())),
            "input_errors": [], "safety_checks": {"pass": True},
            "clip_checks": {clip: {"pass": True} for clip in ("A", "B", "C")},
        })
        write_json(self.run / "records.json", {
            "labels_deferred": False, "merge_reviews_applied": 0, "vehicle_motion_actions": 0,
        })
        checkpoint_sha = protocol.sha256(self.checkpoint)
        for clip in ("A", "B", "C"):
            write_json(self.run / clip / "tracking.json", {
                "state": "complete", "identity": {"checkpoint_sha256": checkpoint_sha},
                "decoded": {"sampled_frames": 30}, "track_count": 2 if clip != "C" else 0,
                "calls": {"automatic_mask_generation": 3,
                          "propagated_frame_outputs": 30 if clip != "C" else 0},
            })
        write_json(self.run / "run.json", {
            "state": "complete", "phase": "development", "selected_clips": ["A", "B", "C"],
            "code_manifest": current, "completed_tracking_clips": 3,
            "labels_deferred": False, "heldout_opened": False,
            "checkpoint_sha256": checkpoint_sha, "artifact_manifest": [],
        })

    def freeze(self):
        return protocol.freeze(self.root, self.run, self.validation_path)

    def freeze_and_commit(self):
        manifest = self.freeze()
        self.commit("freeze committed before held-out access")
        return manifest

    def test_retained_stop_change_prevents_freeze(self):
        (self.root / "STOP.md").write_text("changed old outcome\n")
        with self.assertRaisesRegex(protocol.ProtocolError, "Retained parent evidence changed"):
            self.freeze()
        self.assertFalse((self.experiment / "FROZEN.md").exists())

    def test_uncommitted_config_cannot_freeze_even_if_validation_is_updated(self):
        (self.experiment / "config.json").write_text('{"tuned":true}\n')
        self.make_complete_evidence()
        with self.assertRaisesRegex(protocol.ProtocolError, "Commit this artifact"):
            self.freeze()

    def test_skipped_actual_tracker_repeat_cannot_be_presented_as_a_pass(self):
        validation = json.loads(self.validation_path.read_text())
        validation["sam_determinism"].update(status="SKIP", skipped=1)
        write_json(self.validation_path, validation)
        self.commit("checkpoint absent; actual repeat explicitly skipped")
        with self.assertRaisesRegex(protocol.ProtocolError, "sam_determinism"):
            self.freeze()

    def test_deferred_label_snapshot_cannot_freeze(self):
        record = json.loads((self.run / "records.json").read_text())
        record["labels_deferred"] = True
        write_json(self.run / "records.json", record)
        self.commit("deferred development labels")
        with self.assertRaisesRegex(protocol.ProtocolError, "final labels"):
            self.freeze()

    def test_manifest_does_not_enumerate_heldout_and_includes_added_code(self):
        directory = self.experiment / "heldout"
        directory.mkdir()
        (directory / "secret-name.mp4").write_bytes(b"unopened fixture")
        original_scandir = protocol.os.scandir

        def guarded_scandir(path):
            if Path(path).is_relative_to(directory):
                self.fail("Frozen-path discovery enumerated held-out contents")
            return original_scandir(path)

        before = protocol.code_manifest(self.root)
        with patch.object(protocol.os, "scandir", guarded_scandir):
            self.assertEqual(before, protocol.code_manifest(self.root))
        (self.experiment / "new_classifier.py").write_text("# newly added code\n")
        self.assertNotEqual(before, protocol.code_manifest(self.root))

    def test_missing_freeze_refuses_before_heldout_directory_enumeration(self):
        with patch.object(Path, "iterdir", side_effect=AssertionError("Premature held-out enumeration")):
            with self.assertRaises(protocol.ProtocolError):
                protocol.prepare_heldout(self.root)

    def test_canonical_export_sidecars_do_not_change_frozen_code_manifest(self):
        before = protocol.code_manifest(self.root)
        for name in ("tracks.csv.json", "edits.jsonl.json", "latest-development.json"):
            write_json(self.experiment / name, {"generated_output": True})
        self.assertEqual(before, protocol.code_manifest(self.root))
        for name in ("tracks.csv.json", "edits.jsonl.json", "latest-development.json"):
            write_json(self.experiment / name, {"generated_output": "another completed run"})
        self.assertEqual(before, protocol.code_manifest(self.root))
        write_json(self.experiment / "configuration" / "tracks.csv.json", {"decision_input": True})
        self.assertNotEqual(before, protocol.code_manifest(self.root))

    def test_freeze_marker_must_be_committed_before_heldout_access(self):
        manifest = self.freeze()
        self.assertEqual(manifest["code_commit"], self.git("rev-parse", "HEAD"))
        with patch.object(Path, "iterdir", side_effect=AssertionError("Premature held-out enumeration")):
            with self.assertRaisesRegex(protocol.ProtocolError, "Commit this artifact"):
                protocol.prepare_heldout(self.root)
        self.commit("freeze")
        self.assertEqual(protocol.prepare_heldout(self.root)["state"], "MISSING")

    def test_freeze_report_copies_parameters_measurements_and_label_provenance(self):
        config = {"emission": {"consecutive_frames": 6}, "frame_stride": 3,
                  "working_width": 640, "motion_lag_frames": 3,
                  "sam": {"model_id": "official fixture architecture", "device": "cpu"},
                  "motion": {"stationary_max_residual_px": 2.0}}
        write_json(self.experiment / "config.json", config)
        self.make_complete_evidence()
        result = json.loads((self.run / "dev-results.json").read_text())
        for row in result["rows"]:
            is_control = row["id"] == "C_clear_road"
            stationary = "red" in row["id"]
            row.update({"target": row["id"], "candidate_count": int(stationary),
                        "edit_count": int(stationary)})
            if not is_control:
                row.update({"expected_class": "STATIONARY" if stationary else "MOVING",
                            "class": "STATIONARY" if stationary else "MOVING",
                            "longest_stationary_run": 9 if stationary else 0,
                            "longest_moving_run": 0 if stationary else 11})
        write_json(self.run / "dev-results.json", result)
        records = json.loads((self.run / "records.json").read_text())
        records["edits"] = [
            {"clip": "A", "track_id": 8, "label_provenance": {
                "source": "model", "fallback_reason": None, "provider": "baseten",
                "model_id": "meta-models/muse-spark-open-1026", "model_calls": 1}},
            {"clip": "B", "track_id": 9, "label_provenance": {
                "source": "fallback", "fallback_reason": "fixture_transport", "provider": "baseten",
                "model_id": "meta-models/muse-spark-open-1026", "model_calls": 1}},
        ]
        write_json(self.run / "records.json", records)
        self.commit("fixture measurements and provenance")
        manifest = self.freeze()
        report = (self.experiment / "FROZEN.md").read_text()
        for value in (manifest["created_at_utc"], manifest["code_commit"],
                      manifest["checkpoint_sha256"], manifest["code_manifest"]["sha256"],
                      "6 consecutive processed frames", '"working_width": 640',
                      '"stationary_max_residual_px": 2.0', "same source, different viewpoint",
                      "| A_red_stationary | STATIONARY | STATIONARY | 9 | 0 | 1 | 1 | PASS |",
                      "| A_white_moving | MOVING | MOVING | 0 | 11 | 0 | 0 | PASS |",
                      "| A | 8 | model | none | baseten | meta-models/muse-spark-open-1026 | 1 |",
                      "| B | 9 | fallback | fixture_transport | baseten | meta-models/muse-spark-open-1026 | 1 |"):
            self.assertIn(value, report)
        self.assertIn("hash of its own commit", report)
        self.assertIn("No held-out result is asserted", report)

    def test_heldout_reservation_is_single_shot_and_binds_input_bytes(self):
        manifest = self.freeze_and_commit()
        directory = self.experiment / "heldout"
        directory.mkdir()
        (directory / "prereg.md").write_text("Supplied fixture preregistration; no scoring inferred.\n")
        clip = directory / "supplied.mp4"
        clip.write_bytes(b"fixture video bytes; never decoded")
        inputs = protocol.prepare_heldout(self.root)
        clip.write_bytes(b"changed after prereg review")
        with self.assertRaisesRegex(protocol.ProtocolError, "inputs changed"):
            protocol.reserve_heldout(self.root, inputs, self.checkpoint)
        self.assertFalse((directory / "ATTEMPTED.json").exists())
        inputs = protocol.prepare_heldout(self.root)
        receipt = protocol.reserve_heldout(self.root, inputs, self.checkpoint)
        self.assertEqual(receipt["attempt"], 1)
        self.assertEqual(receipt["code_commit"], manifest["code_commit"])
        self.assertNotIn("prereg_text", receipt)
        with self.assertRaisesRegex(protocol.ProtocolError, "already reserved"):
            protocol.reserve_heldout(self.root, inputs, self.checkpoint)

    def test_changed_or_new_code_after_freeze_refuses_heldout(self):
        self.freeze_and_commit()
        (self.experiment / "another_algorithm.py").write_text("# post-freeze code\n")
        with self.assertRaisesRegex(protocol.ProtocolError, "Frozen code/config changed"):
            protocol.prepare_heldout(self.root)


if __name__ == "__main__":
    unittest.main()
