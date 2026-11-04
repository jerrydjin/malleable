# Malleable

Our goal: an ambulance gets a clear road ahead of it because cars share a live road record, with robotaxi fleets as the first buyers. In simulation, a road edit merges only after [a second car confirms it](docs/gates/phase-15a-scores.jsonl#L10), and a spoofed edit never merged in any of the [10 scored seeds of the Phase 15a gate](docs/gates/phase-15a-scores.jsonl). We have not shown that any vehicle arrives faster; see Limits.

AVs read and write the road record the way coding agents commit to a codebase. Edits are commits, a second car's confirmation is review, and conflicting claims are merge conflicts. This is the protocol analogy; fleet deployment and general conflict resolution are not built. See the [implemented protocol](docs/SPEC.md).

## What the evidence shows

- **Propose, confirm, merge with a set reach.** [PR #50](https://github.com/jerrydjin/malleable/pull/50) plays the original [seed 1 RECORD gate row](docs/gates/phase-15a-scores.jsonl#L10): a car proposes, a second car confirms from its simulated sensor, then the edit merges. The cached model reply sets [route reach, radius 1500 m](docs/gates/phase-15-model-replies.json). Play the [committed replay](recordings/phase15a-seed1.json); do not regenerate it.
- **A spoofed edit does not merge in the scored matrix.** [`spoof_merged: false` and `spoof_caused_reroutes: 0` hold for seeds 1–10 in the original Phase 15a gate](docs/gates/phase-15a-scores.jsonl). This does not establish trust for real fleets or independent cameras.
- **The Meta LLM picks label, reach and who gets priority; it never touches physics.** [Recorded label/reach](docs/gates/phase-15-model-replies.json), [live grant/deny evidence](docs/gates/phase-c-reasons.jsonl), and the [policy adapter](src/reason.rs) show that boundary. [`RoadEdit::review`](src/record.rs) is the hazard merge authority; the [host](src/record_host.rs) and [physical executor](src/make_way.rs) retain movement control. The scored Phase 15 priority grants use Mock, not live LLM decisions.

## Where Meta models sit

**SAM 2.1 is the eyes:** its committed masks provide visual evidence. **The Meta LLM (Muse, via Baseten) writes label and reach and decides grant/deny.** Muse is Meta's LLM; the project is Malleable. The [Phase 16b gate](docs/gates/phase-16b-summary.md) records live SAM and a live Baseten label/reach reply from a numerical SAM summary, not from images. Reach is reply metadata; the model cannot merge an edit or move a car.

In Phase 16b, **B is same source, different viewpoint**. It is not independent corroboration. The label sits on the white trailer, not the crash; the trust rule was not tested because A failed detection and B review was never applied. See [bars and caveats](docs/gates/phase-16b-summary.md), [merge check](experiments/phase16b/output/merge-check.json), and [retained overlay](experiments/phase16b/overlays/B.mp4).

## Quickstart and recording order

Requires Rust/Cargo, Bash and a browser. From the repository root:

```bash
cargo build --release
cargo test
bash scripts/demo.sh --dry-run
bash scripts/demo.sh
```

The player prints a browser URL. In the script, press Enter in the terminal after each shot; it closes that viewer and pauses before the next. A failed command exits non-zero. Standalone viewer commands stay open until Ctrl-C.

Shot A — play the saved trust loop:

```bash
cargo run --release -- --replay recordings/phase15a-seed1.json
```

Shot B — the existing live grant/deny board, when `BASETEN_API_KEY` is set:

```bash
cargo run --release -- --board
```

Submit `My passenger has severe chest pain`, then `I want coffee before it gets cold`. Inspect the source/provider and the actual grant/deny; report a fallback or unexpected decision plainly. This is a demo, not new scored evidence. Keep the key in the environment; never print it.

Without the key, the script prints a notice and plays these saved shots in order, pausing between them:

```bash
cargo run --release -- --replay recordings/grant.json
cargo run --release -- --replay recordings/deny.json
```

The [demo runbook](docs/DEMO-RUNBOOK.md) has narration, stopping instructions and evidence boundaries. Do not run experiment runners, regenerate recordings, or rescore gates for this presentation.

## Scoreboard

The [full scoreboard](docs/SCOREBOARD.md) retains the earlier zeros, negative outcomes, FAILs and STOPs.

| Evidence | Result |
| --- | --- |
| Phase 15a replay — [PR #50](https://github.com/jerrydjin/malleable/pull/50), [seed 1 original gate](docs/gates/phase-15a-scores.jsonl#L10) | Edit merged after second-car confirmation; **0.0 s** affected median gain; **300 m bar not met — FAIL**. |
| Phase 16b — [committed gate](docs/gates/phase-16b-summary.md) | **b/c/f PASS; a/d/e FAIL.** Label sits on the white trailer, not the crash. B is same source, different viewpoint. No B review or merge; trust rule not tested. |
| Phase 16d held-out — [PR #51](https://github.com/jerrydjin/malleable/pull/51) | Preregistered, frozen before the held-out run, single attempt on 300 frames: **0 edits**, no truck-body hit — **FAIL**. Dev 5/5 passed; the held-out result did not transfer. |

## Limits — what is not proven

- **No faster-arrival claim from the replay.** [Seed 1](docs/gates/phase-15a-scores.jsonl#L10) has **0.0 s** gain and **0 reroutes** before or after sighting. Its **0 collisions, 0 overlaps and 0 leaks** describe that simulation only. The [original matrix](docs/gates/phase-15a-scores.jsonl#L121) is **FAIL**, with **0 winning seeds** at its declared range.
- **Priority is not demonstrated arrival benefit.** Both [original labour](docs/gates/phase-15b-scores.jsonl) and [corrected labour](docs/gates/phase-15b-v2-scores.jsonl) **FAIL**: **0 s** gain; denied gym controls have **0 gain and cost**. Grants in those matrices are Mock. The [corrected NEAR control](docs/gates/phase-15a-v2-scores.jsonl) is a separate control PASS, not the replay or an efficacy win.
- **Phase 16b FAILs a/d/e.** [The gate](docs/gates/phase-16b-summary.md) records A's failed detection, no B review, no merge, **0 confirmations**, and status `Proposed`. C has **0/15** positive frames. A spoof not merging here does not test the trust rule. The label targets the white trailer rather than the crash; localization and detection time remain unmeasured.
- **Historical STOPs remain visible.** [SAM acquisition](docs/phase-15a-blocked.md) and [footage acquisition](experiments/phase16b/STOP.md) stopped on unavailable inputs/access; supplied evidence later allowed continuation. [FAR geometry](docs/phase-15-v2-feasibility.md) still **STOPPED**: no qualifying FAR tree on the unchanged map.
- **Earlier failures still count.** [Full scoreboard](docs/SCOREBOARD.md): queue-yield cost passes with **[0 s gain](docs/gates/phase-13f-summary.json)** do not prove benefit; envelope and universal-exclusion claims **FAIL**; diversion and bypass controls **FAIL** on safety; guarded broadcast/envelope arms **FAIL** on costs; signal arms **FAIL** on completion/costs. The labour follow-up and freeway baseline **STOPPED** on validity and overflow/incompletion/overlaps, respectively; no record efficacy score followed.
- Real fleet integration, authenticated independent observations, general merge-conflict resolution, and clinical outcomes are not proven. The [Phase 16d held-out run](https://github.com/jerrydjin/malleable/pull/51) **FAILED (0 edits)**, so perception of a stopped hazard on unseen footage is not shown.
