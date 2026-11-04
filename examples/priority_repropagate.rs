//! Replay the saved grant/deny flags with current route propagation, without a model client.
use malleable::{negotiate::ScriptedTalk, network::run_priority_town, replay::ReplayArchive};
use std::path::Path;

fn main() -> Result<(), String> {
    for name in ["grant", "deny"] {
        let mut archive = ReplayArchive::read(Path::new(&format!("recordings/{name}.json")))?;
        let saved = archive
            .board
            .reason
            .as_ref()
            .ok_or("missing saved decision")?;
        let decision = serde_json::to_value(&saved.decision).map_err(|e| e.to_string())?;
        let old = archive
            .board
            .town
            .priority
            .as_ref()
            .ok_or("missing priority trip")?;
        // These two archives have one model reason reply and deterministic
        // fallback junction dialogue. Never replace a saved model agreement.
        if old.enabled != saved.decision.granted
            || archive
                .board
                .town
                .exchanges
                .iter()
                .any(|ex| ex.source == "model")
        {
            return Err("archive does not match the saved grant/deny replay contract".into());
        }
        let before = old.time_home_s.ok_or("original trip did not finish")?;
        let mut town = run_priority_town(
            7,
            old.request,
            saved.decision.granted,
            Box::new(ScriptedTalk),
        );
        let priority = town.priority.as_mut().ok_or("missing new priority trip")?;
        priority.baseline_time_home_s = old.baseline_time_home_s;
        let after = priority.time_home_s.ok_or("new trip did not finish")?;
        if town.stats.overlaps + town.stats.crossing_conflicts != 0 || priority.route != old.route {
            return Err("regenerated trip violated the safe route contract".into());
        }
        let report = archive.board.reason.as_mut().unwrap();
        report.time_home_s = after;
        report.overlaps = town.stats.overlaps;
        report.crossing_conflicts = town.stats.crossing_conflicts;
        if serde_json::to_value(&report.decision).map_err(|e| e.to_string())? != decision {
            return Err("saved model decision changed".into());
        }
        archive.board.town = town;
        let output = format!("recordings/{name}-v2.json");
        archive.write(Path::new(&output))?;
        println!("{output}: original={before:.2}s fixed={after:.2}s model_calls=0");
    }
    Ok(())
}
