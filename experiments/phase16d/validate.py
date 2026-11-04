#!/usr/bin/env python3
"""Record real Python/Cargo check outcomes for the exact freeze inputs."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

from protocol import code_manifest, verify_base_preservation

EXPERIMENT = Path(__file__).resolve().parent
ROOT = EXPERIMENT.parents[1]


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes = {}

    def addSuccess(self, test):
        self.outcomes[test.id()] = {"status": "PASS"}
        super().addSuccess(test)

    def addSkip(self, test, reason):
        self.outcomes[test.id()] = {"status": "SKIP", "reason": reason}
        super().addSkip(test, reason)

    def addFailure(self, test, error):
        self.outcomes[test.id()] = {"status": "FAIL"}
        super().addFailure(test, error)

    def addError(self, test, error):
        self.outcomes[test.id()] = {"status": "ERROR"}
        super().addError(test, error)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cargo", default="cargo")
    parser.add_argument("--prefix", default="validation")
    arguments = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", arguments.prefix):
        parser.error("prefix must be a simple file name")
    verify_base_preservation(ROOT)
    before = code_manifest(ROOT)
    runtime = EXPERIMENT / "runtime"
    python_log = runtime / f"{arguments.prefix}-python.log"
    cargo_log = runtime / f"{arguments.prefix}-cargo.log"
    with python_log.open("w") as stream:
        suite = unittest.defaultTestLoader.discover(str(EXPERIMENT / "tests"))
        result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=RecordedResult).run(suite)
    with cargo_log.open("w") as stream:
        cargo = subprocess.run([arguments.cargo, "test", "--offline"], cwd=ROOT,
                               stdout=stream, stderr=subprocess.STDOUT)
    cargo_sections = re.findall(r"test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored;", cargo_log.read_text())
    actual_name = "test_tracker.ActualTrackingDeterminism.test_fixed_development_clip_first_three_sampled_frames_repeat"
    actual = result.outcomes.get(actual_name, {"status": "MISSING"})
    manifest = {"version": 1, "checked_at_utc": datetime.now(timezone.utc).isoformat(),
                "code_manifest_sha256": before["sha256"],
                "python": {"status": "PASS" if result.wasSuccessful() else "FAIL",
                           "tests": result.testsRun, "passed": sum(r["status"] == "PASS" for r in result.outcomes.values()),
                           "failed": len(result.failures) + len(result.errors), "skipped": len(result.skipped),
                           "log": str(python_log.relative_to(EXPERIMENT)), "outcomes": result.outcomes},
                "sam_determinism": {**actual, "test": actual_name,
                                    "skipped": int(actual["status"] == "SKIP"),
                                    "log": str(python_log.relative_to(EXPERIMENT))},
                "cargo": {"status": "PASS" if cargo.returncode == 0 and cargo_sections else "FAIL",
                          "exit_code": cargo.returncode,
                          "passed": sum(int(r[0]) for r in cargo_sections),
                          "failed": sum(int(r[1]) for r in cargo_sections),
                          "ignored": sum(int(r[2]) for r in cargo_sections),
                          "log": str(cargo_log.relative_to(EXPERIMENT))}}
    if before != code_manifest(ROOT):
        raise RuntimeError("Code/config changed during validation; no validation record was published")
    verify_base_preservation(ROOT)
    for path in (python_log, cargo_log):
        path.write_text(path.read_text().rstrip() + "\n")
    (runtime / "validation.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    print(json.dumps({name: manifest[name] for name in ("code_manifest_sha256", "sam_determinism", "cargo")}))
    return 0 if result.wasSuccessful() and cargo.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
