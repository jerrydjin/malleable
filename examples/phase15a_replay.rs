//! One command: replay the scored Phase 15a seed 1 run and write the board recording.
//!
//! Uses the committed replies in `docs/gates/phase-15-model-replies.json`.
//! Does not read `BASETEN_API_KEY` and does not call Muse.
fn main() -> Result<(), String> {
    let mut out = malleable::phase15a_replay::OUT_PATH.to_string();
    for arg in std::env::args().skip(1) {
        if let Some(path) = arg.strip_prefix("out=") {
            if path.is_empty() {
                return Err("out= needs a path".into());
            }
            out = path.to_string();
        } else {
            return Err(format!("unknown argument {arg}"));
        }
    }
    let archive = malleable::phase15a_replay::record_seed1()?;
    let path = std::path::Path::new(&out);
    if let Some(parent) = path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
    }
    archive.write(path)?;
    let shot = archive
        .board
        .phase15a
        .as_ref()
        .ok_or("missing phase 15a replay")?;
    println!("{}", shot.label);
    println!("wrote {}", path.display());
    println!("model calls=0");
    println!("{}", shot.note);
    for beat in &shot.beats {
        println!("{}", beat.text);
    }
    Ok(())
}
