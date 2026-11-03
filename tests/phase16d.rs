#[path = "../experiments/phase16d/record_adapter.rs"]
mod record_adapter;

use malleable::record::Blocks;
use record_adapter::{label_for_run, label_user, parse_label, propose, LabelOutcome, MappingEvidence, Position};
use serde_json::{json, Value};

fn evidence() -> MappingEvidence {
    MappingEvidence {
        clip: "fixture".into(), track_id: 7, lane: "lane_1".into(),
        position: Position {
            coordinate_system: "road_reference_image".into(), reference_frame: 0,
            x_px: 440.0, y_px: 510.0, metric_position_m: None,
        },
        confidence: 0.8, since_s: 2.0, stationary_frames: 3, required_stationary_frames: 3,
        image_sha256: "a".repeat(64), mask_sha256: "b".repeat(64),
    }
}

fn label() -> LabelOutcome {
    let raw = r#"{"label":"stationary lane object","blocks":"none","reach":{"scope":"nearby","radius_m":100},"rationale":"merge this now"}"#;
    LabelOutcome {
        source: "fixture", fallback_reason: None, provider: None, model_id: None,
        latency_ms: None, raw_reply: Some(raw.into()), reply: parse_label(raw).unwrap(), model_calls: 0,
    }
}

fn wire(edit: &record_adapter::MappedEdit) -> Value {
    serde_json::to_value(edit).unwrap()
}

#[test]
fn positive_mapping_emits_a_scene_local_proposal_without_model_authority() {
    let mapped = propose(&evidence(), label()).unwrap().unwrap();
    let edit = wire(&mapped);
    for key in ["id", "kind", "link", "route", "blocks", "since_s", "author_car", "evidence", "status", "confirmations", "expires_at", "merged_at"] {
        assert!(edit.get(key).is_some(), "missing SPEC field {key}");
    }
    assert_eq!(edit["kind"], "hazard");
    assert_eq!(edit["map_id"], "unlocalized_clip_road");
    assert_eq!(edit["link"], 0);
    assert_eq!(edit["route"], json!([]));
    assert_eq!(edit["lane_blocked"], "lane_1");
    assert_eq!(edit["position"]["coordinate_system"], "road_reference_image");
    assert_eq!(edit["position"]["metric_position_m"], Value::Null);
    assert_eq!(edit["confidence"], 0.8);
    assert_eq!(edit["confidence_kind"], "heuristic");
    assert_eq!(edit["evidence"]["image_sha256"], "a".repeat(64));
    assert_eq!(edit["evidence"]["mask_sha256"], "b".repeat(64));
    assert_eq!(edit["evidence"]["label"], "stationary lane object");
    assert_eq!(edit["reach"]["radius_m"], 100.0);
    // The model asked to merge, and its blocks says none: neither controls review.
    assert_eq!(edit["blocks"], "lane");
    assert_eq!(edit["status"], "Proposed");
    assert_eq!(edit["confirmations"], json!([]));
    assert_eq!(edit["merged_at"], Value::Null);
    assert_eq!(edit["label_provenance"]["model_calls"], 0);
    assert_eq!(edit["label_provenance"]["raw_reply"], label().raw_reply.unwrap());
    for forbidden in ["throttle", "speed", "acceleration", "steering", "vehicle_action"] {
        assert!(edit.get(forbidden).is_none());
    }
}

#[test]
fn b_always_carries_the_same_source_different_viewpoint_note() {
    let mut observed = evidence();
    observed.clip = "B".into();
    let payload: Value = serde_json::from_str(&label_user(&observed)).unwrap();
    assert_eq!(payload["viewpoint_note"], "same source, different viewpoint");
    let mapped = propose(&observed, label()).unwrap().unwrap();
    assert_eq!(wire(&mapped)["viewpoint_note"], "same source, different viewpoint");
    assert_eq!(wire(&mapped)["status"], "Proposed");
    for clip in ["A", "C"] {
        observed.clip = clip.into();
        assert_eq!(observed.viewpoint_note(), "A/C development clip");
    }
    observed.clip = "heldout".into();
    assert_eq!(observed.viewpoint_note(), "held-out clip");
}

#[test]
fn model_merge_motion_and_mapping_fields_are_rejected() {
    let base = serde_json::to_value(label().reply).unwrap();
    for (key, value) in [("status", json!("Merged")), ("merge", json!(true)), ("throttle", json!(1)), ("lane_blocked", json!("lane_0")), ("confidence", json!(1.0))] {
        let mut bad = base.clone(); bad[key] = value;
        assert!(parse_label(&bad.to_string()).is_err(), "model field {key} accepted");
    }
    let mut bad = base;
    bad["reach"]["radius_m"] = json!(-1);
    assert!(parse_label(&bad.to_string()).is_err());
}

#[test]
fn shoulder_unknown_invalid_and_nonstationary_mappings_abstain() {
    let mut variants = Vec::new();
    for lane in ["shoulder", "unknown", "lane_", "lane_-1", "lane_01"] {
        let mut item = evidence(); item.lane = lane.into(); variants.push(item);
    }
    let mut item = evidence(); item.confidence = f64::NAN; variants.push(item);
    let mut item = evidence(); item.confidence = 1.1; variants.push(item);
    let mut item = evidence(); item.position.x_px = f64::INFINITY; variants.push(item);
    let mut item = evidence(); item.position.metric_position_m = Some(3.0); variants.push(item);
    let mut item = evidence(); item.position.coordinate_system = "city_graph".into(); variants.push(item);
    let mut item = evidence(); item.stationary_frames = 2; variants.push(item);
    let mut item = evidence(); item.required_stationary_frames = 0; variants.push(item);
    let mut item = evidence(); item.mask_sha256.clear(); variants.push(item);
    for item in variants {
        assert!(item.abstention_reason().is_some());
        assert!(propose(&item, label()).unwrap().is_none());
    }
}

#[test]
fn only_existing_review_can_merge_a_distinct_later_independent_observation() {
    let mut mapped = propose(&evidence(), label()).unwrap().unwrap();
    mapped.review(2, 3.0, true, false); // Same-camera later viewpoint is not independent.
    mapped.review(1, 3.0, true, true); // Existing guard: author cannot review itself.
    mapped.review(2, 2.0, true, true); // Existing guard: not later than proposal.
    mapped.review(2, f64::NAN, true, true);
    assert_eq!(wire(&mapped)["status"], "Proposed");
    assert_eq!(wire(&mapped)["confirmations"], json!([]));
    mapped.review(2, 3.0, true, true);
    assert_eq!(wire(&mapped)["status"], "Merged");
    assert_eq!(wire(&mapped)["confirmations"], json!([{"car":2,"at_s":3.0,"saw_blockage":true}]));
    assert_eq!(wire(&mapped)["merged_at"], 3.0);
    let mut expired = propose(&evidence(), label()).unwrap().unwrap();
    expired.review(2, 32.0, true, true);
    assert_eq!(wire(&expired)["status"], "Rejected");
}

#[test]
fn unavailable_model_is_an_explicit_descriptive_fallback_not_fallen_tree() {
    let fallback = LabelOutcome::fallback("fixture_transport");
    assert_eq!(fallback.source, "fallback");
    assert_eq!(fallback.fallback_reason.as_deref(), Some("fixture_transport"));
    assert_eq!(fallback.reply.label, "unknown stationary lane object");
    assert_eq!(fallback.reply.blocks, Blocks::None);
    assert_eq!(fallback.model_calls, 0);
    let mapped = propose(&evidence(), fallback).unwrap().unwrap();
    assert_eq!(wire(&mapped)["status"], "Proposed");
    assert_eq!(wire(&mapped)["reach"]["radius_m"], 0.0);
}

#[test]
fn explicit_development_deferral_proposes_without_claiming_a_missing_key() {
    // This path never inspects environment credentials or invokes the client.
    let outcome = label_for_run(&evidence(), true);
    assert_eq!(outcome.source, "fallback");
    assert_eq!(outcome.fallback_reason.as_deref(), Some("dev_label_deferred"));
    assert_eq!(outcome.model_calls, 0);
    assert!(outcome.raw_reply.is_none());
    assert!(outcome.provider.is_none());
    let mapped = propose(&evidence(), outcome).unwrap().unwrap();
    let edit = wire(&mapped);
    assert_eq!(edit["label_provenance"]["source"], "fallback");
    assert_eq!(edit["label_provenance"]["fallback_reason"], "dev_label_deferred");
    assert_eq!(edit["status"], "Proposed");
    assert_eq!(edit["confirmations"], json!([]));
    assert_eq!(edit["merged_at"], Value::Null);
}
