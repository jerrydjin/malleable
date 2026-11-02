# Phase 15 v2 verification — 2 November 2026

The registered NEAR control passes at 300 m on 8/10 seeds. The labour claim fails with zero gain at all ranges. Every v1 file/result and the accepted FAR stop are retained.

Both 120-row matrices retain all seeds, arms, hypothetical sensitivities and per-trip completion/final-link fields. All trips finish in these runs; safety counts are zero. No frozen code changed after registration.

## Commit order

```text
14d1ed9 2026-11-02 09:05:59 +0000 Fix isolated v2 record-host decisions and priority delivery; validate NEAR harness before scores
89616b3 2026-11-02 09:15:54 +0000 Preregister dated v2 NEAR control and labour claim; freeze tested inputs before outcomes
a38931b 2026-11-02 09:22:11 +0000 Score frozen v2 NEAR control: PASS on 8 of 10 seeds at 300 m; retain every sensitivity
bb7746a 2026-11-02 09:24:34 +0000 Score frozen v2 labour claim: retain FAIL with zero gain despite priority edits and deliveries
```

The code commit is the parent of the preregistration; the two score commits follow it. All are dated before Monday 2 November 23:00 UK (GMT).

## Actual test output

Retained `cargo test --offline`: **208 passed, 0 failed, 3 ignored**.

```text
test result: ok. 79 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 38.22s
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.01s
test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.43s
test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.16s
test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.63s
test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.65s
test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 22.89s
test result: ok. 6 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 14.94s
test result: ok. 6 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 1.04s
test result: ok. 3 passed; 0 failed; 3 ignored; 0 measured; 0 filtered out; finished in 2.86s
test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 8.35s
test result: ok. 4 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 12.25s
test result: ok. 5 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
test result: ok. 5 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 2.87s
test result: ok. 8 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 8.24s
test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 79.98s
test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 2.18s
test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 14.96s
test result: ok. 13 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 6.37s
test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 24.57s
test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 14.77s
test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 6.39s
test result: ok. 4 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 69.82s
test result: ok. 6 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 1.34s
test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 41.95s
test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 161.44s
test result: ok. 4 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 11.58s
test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 3.40s
test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.01s
test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.02s
test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
test result: ok. 9 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.06s
test result: ok. 11 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 3.58s
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
```

Corrected host: `bash scripts/phase15-v2.sh test --release`: **89 passed, 0 failed, 0 ignored**.

```text
test result: ok. 81 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 27.46s
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 2.16s
test result: ok. 6 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.09s
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
```

Retained structural finding: `cargo test --offline --example phase15_v2_sites`: **3 passed, 0 failed, 0 ignored**.

```text
test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 4.81s
```

New corrected-host tests:

- `known_remaining_blockage_changes_the_old_route_cost_without_changing_make_way`
- `cached_counts_equal_the_original_per_candidate_counts`
- `granted_record_priority_has_a_merged_edit_and_due_public_deliveries`
- `near_and_labour_harness_validity_before_registration_not_outcome_bars`

The six retained road-record tests also pass against the corrected host, including direct observation of every route change at every range/arm: `no_car_changes_route_before_its_own_sighting_or_edit_delivery`.

The first corrected-host full-suite attempt lacked loopback network permission for the existing HTTP tests. The complete rerun with loopback available passed; no code changed to resolve that environment issue.

## Exact-code validity, committed before registration

```json
{
  "before_turnoff_distinct_cars": 80,
  "before_turnoff_max_simultaneous_cars": 39,
  "generated_code_sha256": "81fb28dba21c3007451bfae4b4922957785f4d652f73bfbf9aefb9bab401bafa",
  "hazard_reroutes": 43,
  "kind": "harness_validity_only",
  "labour_granted": true,
  "leaks": 0,
  "priority_actions": 88,
  "priority_deliveries": 70,
  "priority_edits": 1,
  "public_delivered_cars": 70,
  "route_decision_examples": [
    [
      1005,
      {
        "at_s": 354.5,
        "choice": "Ignore",
        "known_wait_s": 785.5,
        "new_block_s": 777.5,
        "new_free_s": 61.49314886769604,
        "new_remaining_m": 738.8715847608935,
        "old_cost_s": 830.3787809649875,
        "old_free_s": 44.878780964987584,
        "old_remaining_m": 589.2065523694514
      }
    ],
    [
      1009,
      {
        "at_s": 348.75,
        "choice": "Ignore",
        "known_wait_s": 791.25,
        "new_block_s": 787.5,
        "new_free_s": 61.49314886769604,
        "new_remaining_m": 738.875142816838,
        "old_cost_s": 836.1287809649875,
        "old_free_s": 44.878780964987584,
        "old_remaining_m": 589.2101104253959
      }
    ],
    [
      1011,
      {
        "at_s": 240.0,
        "choice": "Reroute([])",
        "known_wait_s": 900.0,
        "new_block_s": 357.5,
        "new_free_s": 61.49314886769604,
        "new_remaining_m": 703.7128685801151,
        "old_cost_s": 944.8787809649875,
        "old_free_s": 44.878780964987584,
        "old_remaining_m": 554.047836188673
      }
    ]
  ],
  "safety": 0,
  "seed": 1,
  "sensor_range_m": 300,
  "true_edit_merged": true,
  "valid": true
}
```

## Preservation and hashes

`python3 scripts/phase15-sam.py --check` exited 0:

```json
{"check": "OK", "image_sha256": "07030ee22246306d776c80c74defe29c214914eac81cb2a7fbaae17b3997e55d", "mask_sha256": "0d42d9b407d9e19cd84049a571e015d18e8b0e25faf879dfd1a7d14b806e1c77"}
```

`bash scripts/phase15-preserve.sh /tmp/phase15-v2-retained-preservation` exited 0:

```text
f562752988892edb19d40dea9b051fc488721aa9a341f1e7c51de5afdb23a9ab  /tmp/phase15-v2-retained-preservation/13i/scores.jsonl
Phase 15 preservation: all cmp OK; protected base files unchanged.
```

All **414 retained files** match `de1b1a2` byte for byte. Both original code freezes still pass (**85/85** and **89/89**); the v2 root freeze passes **143/143**, and the generated-source freeze passes **40/40**. Generated `judge.rs`, `schema.rs` and `make_way.rs` equal the retained originals.

These additional commands exited 0 with no diff:

```sh
git diff --exit-code bc5d51b -- docs/gates maps src/judge.rs src/schema.rs ':(exclude)docs/gates/phase-15*'
git diff --exit-code 11772c2 -- assets/phase15/fallen-tree-a36.jpg assets/phase15/mask.png assets/phase15/sam.json
```

## Byte-for-byte score replays

```sh
cargo run --offline --release --example phase15_gate -- part=tree seed=1 end=10 > /tmp/phase15-v2-retained-15a.jsonl
cmp docs/gates/phase-15a-scores.jsonl /tmp/phase15-v2-retained-15a.jsonl
cargo run --offline --release --example phase15_gate -- part=birth seed=1 end=10 > /tmp/phase15-v2-retained-15b.jsonl
cmp docs/gates/phase-15b-scores.jsonl /tmp/phase15-v2-retained-15b.jsonl
bash scripts/phase15-v2.sh run part=near seed=1 end=10 > /tmp/phase15a-v2-replay.jsonl
cmp docs/gates/phase-15a-v2-scores.jsonl /tmp/phase15a-v2-replay.jsonl
bash scripts/phase15-v2.sh run part=birth seed=1 end=10 > /tmp/phase15b-v2-replay.jsonl
cmp docs/gates/phase-15b-v2-scores.jsonl /tmp/phase15b-v2-replay.jsonl
```

All four commands and comparisons exited 0. Completion markers and SHA-256 values:

```text
v1 tree cmp OK
dc047608a730de9e64ccc9a6130807ab92dc2b3bee1867ab6f9e60998836ffc3  /tmp/phase15-v2-retained-15a.jsonl
v1 birth cmp OK
9cf321a3d134a02cbbd31c5d9462314f6887e98fa5e5ecde72c55d6523a17c1b  /tmp/phase15-v2-retained-15b.jsonl
v2 NEAR cmp OK
19f074f29bdebe72055a88d83a798dacf0efbec551abf5f1e2387d6c8039cf6b  /tmp/phase15a-v2-replay.jsonl
v2 birth cmp OK
2cd107defc6a1dacdaa2857364a9d3212dc2b774f8dd1a2af5828aa33a5fe828  /tmp/phase15b-v2-replay.jsonl
```

Both v2 gate outputs:

```json
{"all_trips_finished":true,"claim_sensor_range_m":300,"control_holding_seeds_300m":8,"coverage_valid":true,"kind":"gate","no_leaks":true,"others_cost_bar_300m":true,"part":"near","pass":true,"safety":true,"seeds":[1,10],"spoof_rejected":true,"true_merges":true,"version":2}
{"all_trips_finished":true,"claim_sensor_range_m":300,"gym_denied_zero_gain_cost":true,"kind":"gate","labour_granted":true,"others_cost_bar_300m":true,"part":"birth","pass":false,"priority_wiring_valid":true,"safety":true,"seeds":[1,10],"version":2,"winning_seeds_300m":0}
```
