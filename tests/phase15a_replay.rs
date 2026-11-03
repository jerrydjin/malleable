//! The replay must reproduce the retained Phase 15a seed-1 score.
//! Compared with `docs/gates/phase-15a-scores.jsonl` (seed 1, arm RECORD, 300 m).
use malleable::phase15a_replay::{self, LABEL};
use malleable::replay::ReplayArchive;

#[test]
fn phase15a_seed1_replay_matches_scored_gate() {
    let gate = phase15a_replay::gate_seed1_record_row().expect("gate row");
    let dir =
        std::env::temp_dir().join(format!("malleable-phase15a-replay-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let recording = dir.join("phase15a-seed1.json");
    let html = dir.join("phase15a-seed1.html");
    std::env::remove_var("BASETEN_API_KEY");
    std::env::remove_var("MODEL_API_KEY");
    std::env::remove_var("GEMINI_API_KEY");
    std::env::remove_var("MERGE_API_KEY");
    let archive = phase15a_replay::record_seed1().expect("replay of scored run");
    archive.write(&recording).unwrap();
    let shot = archive
        .board
        .phase15a
        .as_ref()
        .expect("phase 15a replay view");
    assert_eq!(shot.label, LABEL);
    assert_eq!(shot.seed, 1);
    assert_eq!(shot.arm, "RECORD");
    assert_eq!(shot.sensor_range_m, 300.0);
    assert_eq!(shot.live_model_calls, 0);
    assert_eq!(shot.gate_file, "docs/gates/phase-15a-scores.jsonl");
    phase15a_replay::scored_row_matches(&shot.scored)
        .expect("replay score row must match docs/gates/phase-15a-scores.jsonl seed 1 arm RECORD sensor_range_m 300 part tree");
    let loaded = ReplayArchive::read(&recording).unwrap();
    phase15a_replay::scored_row_matches(
        &loaded
            .board
            .phase15a
            .as_ref()
            .expect("reloaded phase 15a replay")
            .scored,
    )
    .expect("written recording must still match docs/gates/phase-15a-scores.jsonl");
    assert_eq!(shot.scored["seed"], gate["seed"]);
    assert_eq!(shot.scored["affected"], gate["affected"]);
    assert_eq!(shot.scored["unaffected_costs"], gate["unaffected_costs"]);
    assert_eq!(shot.scored["record"]["edits"], gate["record"]["edits"]);
    let edit = &gate["record"]["edits"][0];
    let author = edit["author_car"].as_u64().unwrap() as u32;
    let confirmation = &edit["confirmations"][0];
    let reviewer = confirmation["car"].as_u64().unwrap() as u32;
    assert_eq!(edit["status"], "Merged");
    assert_eq!(confirmation["saw_blockage"], true);
    assert!(shot.beats.iter().any(|beat| {
        beat.kind == "propose" && beat.car == Some(author) && beat.text.contains(LABEL)
    }));
    assert!(shot.beats.iter().any(|beat| {
        beat.kind == "review"
            && beat.car == Some(reviewer)
            && beat.text.contains("confirms the blockage")
            && beat.text.contains("edit Merged")
            && beat.text.contains(LABEL)
    }));
    assert!(shot.beats.iter().any(|beat| {
        beat.kind == "outcome"
            && beat.text.contains(LABEL)
            && beat
                .text
                .contains(&gate["affected"]["median_s"].to_string())
            && beat
                .text
                .contains(&gate["unaffected_costs"]["mean_s"].to_string())
    }));
    assert_eq!(archive.board.client, LABEL);
    assert!(archive.board.strips.iter().any(|strip| {
        strip.name == LABEL && strip.story == LABEL && strip.caption.contains(LABEL)
    }));
    let exported = std::process::Command::new(env!("CARGO_BIN_EXE_malleable"))
        .args([
            "--replay",
            recording.to_str().unwrap(),
            "--export-replay",
            html.to_str().unwrap(),
            "--headless",
        ])
        .env_remove("BASETEN_API_KEY")
        .output()
        .unwrap();
    assert!(
        exported.status.success(),
        "viewer export failed\n{}",
        String::from_utf8_lossy(&exported.stderr)
    );
    let viewer = String::from_utf8(exported.stdout).unwrap();
    assert!(viewer.contains("model calls=0"));
    assert!(viewer.contains(LABEL));
    let page = std::fs::read_to_string(&html).unwrap();
    assert_eq!(page.matches("<svg ").count(), 1);
    assert!(page.contains(LABEL));
    assert!(page.contains(&format!("\"author_car\":{author}")));
    assert!(page.contains(&format!("\"car\":{reviewer}")));
    assert!(page.contains("confirms the blockage"));
    assert!(page.contains("data-role=\\\"phase15a-label\\\"") || page.contains("phase15a-label"));
    std::fs::remove_dir_all(dir).unwrap();
}
