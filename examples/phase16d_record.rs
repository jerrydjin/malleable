//! Label eligible mapped objects and emit proposals; never confirm or move cars.
#[path = "../experiments/phase16d/record_adapter.rs"]
mod record_adapter;

use record_adapter::{label_for_run, propose, MappingEvidence};
use serde::Deserialize;
use serde_json::json;
use std::collections::BTreeSet;
use std::io::{Read, Write};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Input {
    evidence: MappingEvidence,
}

fn main() -> Result<(), String> {
    let mut input_path = "-".to_string();
    let mut output_path = "-".to_string();
    let mut labels_deferred = false;
    for argument in std::env::args().skip(1) {
        if argument == "--defer-labels" {
            labels_deferred = true;
        } else if let Some(path) = argument.strip_prefix("--input=") {
            input_path = path.into();
        } else if let Some(path) = argument.strip_prefix("--output=") {
            output_path = path.into();
        } else {
            return Err("usage: phase16d_record --input=PATH|- --output=PATH|- [--defer-labels]".into());
        }
    }
    let mut bytes = Vec::new();
    if input_path == "-" {
        std::io::stdin().read_to_end(&mut bytes).map_err(|e| e.to_string())?;
    } else {
        bytes = std::fs::read(&input_path).map_err(|e| e.to_string())?;
    }
    let input: Vec<Input> = serde_json::from_slice(&bytes).map_err(|e| format!("mapping input: {e}"))?;
    let mut seen = BTreeSet::new();
    let mut edits = Vec::new();
    let mut abstentions = Vec::new();
    let mut model_calls = 0u32;
    for row in input {
        let evidence = row.evidence;
        let reason = evidence.abstention_reason().map(str::to_string).or_else(|| {
            (!seen.insert((evidence.clip.clone(), evidence.track_id))).then(|| "duplicate_tracked_object".into())
        });
        if let Some(reason) = reason {
            abstentions.push(json!({"clip": evidence.clip, "track_id": evidence.track_id, "reason": reason}));
            continue;
        }
        let label = label_for_run(&evidence, labels_deferred);
        model_calls += label.model_calls;
        let edit = propose(&evidence, label)?.ok_or("eligible mapping unexpectedly abstained")?;
        edits.push(edit);
    }
    let output = json!({
        "version": 1,
        "map_id": "unlocalized_clip_road",
        "model_calls": model_calls,
        "labels_deferred": labels_deferred,
        "edits": edits,
        "abstentions": abstentions,
        "merge_reviews_applied": 0,
        "vehicle_motion_actions": 0,
    });
    let encoded = serde_json::to_string_pretty(&output).map_err(|e| e.to_string())? + "\n";
    if output_path == "-" {
        std::io::stdout().write_all(encoded.as_bytes()).map_err(|e| e.to_string())?;
    } else {
        let path = std::path::Path::new(&output_path);
        if let Some(parent) = path.parent().filter(|p| !p.as_os_str().is_empty()) {
            std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        std::fs::write(path, encoded).map_err(|e| e.to_string())?;
    }
    Ok(())
}
