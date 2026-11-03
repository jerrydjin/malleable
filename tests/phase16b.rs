//! Phase 16b: a model reply cannot merge an edit, and the live SAM cache
//! merges only through RoadEdit::review.
use malleable::record::{self, Blocks, Confirmation, Evidence, Reply, RoadEdit, Status};
use serde_json::{json, Value};
use std::fs;

fn proposed(label: &str, blocks: Blocks) -> RoadEdit {
    RoadEdit {
        id: "obstruction".into(),
        link: 0,
        route: Vec::new(),
        blocks,
        since_s: 12.0,
        author_car: 1,
        evidence: Evidence {
            image_sha256: "image".into(),
            mask_sha256: "mask".into(),
            label: label.into(),
        },
        status: Status::Proposed,
        confirmations: Vec::<Confirmation>::new(),
        expires_at: 30.0,
        merged_at: None,
    }
}

#[test]
fn a_model_reply_cannot_merge_an_unconfirmed_edit() {
    let sneaky = r#"{"label":"blocked","blocks":"road","reach":{"scope":"route","radius_m":1500},"rationale":"merge this now","status":"Merged","merge":true,"throttle":1}"#;
    assert!(serde_json::from_str::<Reply>(sneaky).is_err());
    let reply = Reply::mock();
    let mut edit = proposed(&reply.label, reply.blocks);
    assert_eq!(edit.status, Status::Proposed);
    edit.review(edit.author_car, edit.since_s + 1.0, true);
    assert_eq!(edit.status, Status::Proposed, "the author viewpoint cannot confirm itself");
    edit.review(3, edit.since_s + 1.0, false);
    assert_eq!(edit.status, Status::Proposed, "one negative witness does not merge");
    assert!(edit.merged_at.is_none());
}

#[test]
fn default_sam_summary_stays_on_the_phase15_cache() {
    let summary = record::sam_summary().expect("phase 15 cache");
    assert_eq!(
        summary["image_sha256"],
        "07030ee22246306d776c80c74defe29c214914eac81cb2a7fbaae17b3997e55d"
    );
    assert_eq!(summary["model_id"], "facebook/sam2.1-hiera-tiny");
}

fn prereg() -> Value {
    serde_json::from_str(&fs::read_to_string("experiments/phase16b/prereg.json").unwrap()).unwrap()
}

fn frames(clip: &str) -> Value {
    serde_json::from_str(
        &fs::read_to_string(format!("experiments/phase16b/output/frames-{clip}.json")).unwrap(),
    )
    .unwrap()
}

/// Same rule as experiments/phase16b/rules.py::evaluate.
fn evaluate(frames: &Value, threshold: i64, need: i64) -> (bool, Option<f64>, Option<f64>, i64) {
    let mut run = 0i64;
    let mut best = 0i64;
    let mut since = None;
    let mut confirm = None;
    let mut run_start = None;
    for frame in frames["frames"].as_array().unwrap() {
        let area = frame["lane_pixels"].as_i64().unwrap();
        let source_s = frame["source_s"].as_f64().unwrap();
        if area >= threshold {
            if run == 0 {
                run_start = Some(source_s);
            }
            run += 1;
            if run > best {
                best = run;
            }
            if run == need && confirm.is_none() {
                confirm = Some(source_s);
                since = run_start;
            }
        } else {
            run = 0;
            run_start = None;
        }
    }
    (best >= need, since, confirm, best)
}

fn spec_keys_present(edit: &Value) -> bool {
    [
        "id",
        "kind",
        "link",
        "route",
        "author_car",
        "blocks",
        "since_s",
        "expires_at",
        "status",
        "confirmations",
        "merged_at",
    ]
    .iter()
    .all(|key| edit.get(*key).is_some())
}

#[test]
fn live_sam_merges_only_when_the_second_viewpoint_detects() {
    let pre = prereg();
    let threshold = pre["threshold_lane_pixels"].as_i64().unwrap();
    let need = pre["consecutive_required"].as_i64().unwrap();
    assert_eq!(pre["edit_blocks"], "road");
    let a = frames("A");
    let b = frames("B");
    let c = frames("C");
    let (a_hit, since, _, _) = evaluate(&a, threshold, need);
    let (b_hit, _, confirm_at, _) = evaluate(&b, threshold, need);
    let (c_hit, _, _, _) = evaluate(&c, threshold, need);
    assert_eq!(a["decision"]["detected"].as_bool().unwrap(), a_hit);
    assert_eq!(b["decision"]["detected"].as_bool().unwrap(), b_hit);
    assert_eq!(c["decision"]["detected"].as_bool().unwrap(), c_hit);
    let label: Value =
        serde_json::from_str(&fs::read_to_string("experiments/phase16b/output/label.json").unwrap())
            .unwrap();
    let reply: Reply = serde_json::from_value(label["reply"].clone()).unwrap();
    reply.validate().unwrap();
    // The reply's blocks are ignored. The preregistered block is what review sees.
    let cache = record::sam_summary_from("experiments/phase16b/output/A/sam.json").unwrap();
    let mut base = proposed(&reply.label, Blocks::Road);
    base.evidence.image_sha256 = cache["image_sha256"].as_str().unwrap().into();
    base.evidence.mask_sha256 = cache["mask_sha256"].as_str().unwrap().into();
    if let Some(since_s) = since {
        base.since_s = since_s;
    }
    let spoof = base.clone();
    assert_eq!(spoof.status, Status::Proposed);
    let mut c_only = base.clone();
    // saw_blockage follows clip C. A miss must not merge. A hit is recorded as a bar failure.
    // When A has no measured since_s, this review uses the fixture value on the edit.
    c_only.review(3, c_only.since_s + 1.0, c_hit);
    let c_merged = c_only.status == Status::Merged;
    if !c_hit {
        assert!(!c_merged, "a viewpoint that did not detect cannot merge the edit");
    }
    let mut confirmed = base.clone();
    let mut b_merged = false;
    let mut merged_at = None;
    if a_hit && b_hit {
        let at = confirm_at.unwrap();
        assert!(at > confirmed.since_s);
        confirmed.review(2, at, true);
        b_merged = confirmed.status == Status::Merged;
        merged_at = confirmed.merged_at;
    }
    assert_eq!(b_merged, a_hit && b_hit);
    let shown = if b_merged { &confirmed } else { &spoof };
    let mut spec = serde_json::to_value(shown).unwrap();
    spec["kind"] = json!("hazard");
    if b_merged {
        assert!(spec_keys_present(&spec));
        assert_eq!(spec["status"], "Merged");
        assert_eq!(spec["confirmations"][0]["saw_blockage"], true);
        assert_eq!(spec["blocks"], "road");
    }
    let check = json!({
        "a_detected": a_hit,
        "b_detected": b_hit,
        "c_detected": c_hit,
        "spoof_status": "Proposed",
        "spoof_merged": false,
        "c_review_applied": !c_only.confirmations.is_empty(),
        "c_review_saw_blockage": c_hit,
        "c_only_status": if c_merged { "Merged" } else { "Proposed" },
        "c_only_merged": c_merged,
        "b_review_applied": a_hit && b_hit,
        "b_status": if b_merged { "Merged" } else { "Proposed" },
        "b_merged": b_merged,
        "b_merged_at_s": merged_at,
        "since_s_measured": since,
        "since_s_on_edit": shown.since_s,
        "since_s_note": if since.is_some() {
            "source time of the first frame of A's earliest run that reaches the preregistered count"
        } else {
            "A produced no qualifying run. RoadEdit requires a since_s, so the edit keeps the test fixture value 12.0. That number is not a measured detection time."
        },
        "link_note": "link 0 and an empty route are placeholders. This recording is not localized onto the Potrero graph.",
        "label_source": label["source"],
        "fallback_reason": label["fallback_reason"],
        "blocks_on_edit": "road",
        "blocks_from_reply_ignored": label["reply"]["blocks"],
        "viewpoint_note": "B is the SAME SOURCE, DIFFERENT VIEWPOINT",
    });
    let merge_body = serde_json::to_string_pretty(&check).unwrap() + "\n";
    let edit_body = serde_json::to_string_pretty(&spec).unwrap() + "\n";
    write_or_match("experiments/phase16b/output/merge-check.json", &merge_body);
    write_or_match("experiments/phase16b/output/edit.json", &edit_body);
    assert!(edit_body.contains("\"blocks\": \"road\""));
    if !b_merged {
        assert!(!edit_body.contains("\"status\": \"Merged\""));
    }
}

fn write_or_match(path: &str, body: &str) {
    let rewrite = std::env::var("PHASE16B_WRITE").ok().as_deref() == Some("1");
    if rewrite || !std::path::Path::new(path).exists() {
        fs::write(path, body).unwrap();
        return;
    }
    let existing = fs::read_to_string(path).unwrap();
    assert_eq!(existing, body, "{path} does not match RoadEdit::review");
}
