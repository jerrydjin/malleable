//! Scene-local mapped evidence and label/reach only; no vehicle or physics API.
use malleable::muse::{self, GeminiChat, TalkKeys};
use malleable::record::{Blocks, Evidence, Reach, Reply, RoadEdit, Scope, Status};
use serde::{Deserialize, Serialize};
use std::time::Instant;

pub const PROPOSAL_LIFETIME_S: f64 = 30.0;
const LABEL_SYSTEM: &str = "Classify the supplied host-mapped stationary-object evidence and choose communication reach. Return only JSON {\"label\":string,\"blocks\":\"road\"|\"lane\"|\"none\",\"reach\":{\"scope\":\"nearby\"|\"route\"|\"city\",\"radius_m\":number},\"rationale\":string}. No status, confirmation, merge, link IDs, motion controls or extra fields. Confidence is a host heuristic, not a calibrated probability. Coordinates are scene-local image coordinates, not a city map. Label and reach never authorize a merge or move a vehicle.";

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Position {
    pub coordinate_system: String,
    pub reference_frame: u32,
    pub x_px: f64,
    pub y_px: f64,
    pub metric_position_m: Option<f64>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct MappingEvidence {
    pub clip: String,
    pub track_id: u32,
    pub lane: String,
    pub position: Position,
    pub confidence: f64,
    pub since_s: f64,
    pub stationary_frames: u32,
    pub required_stationary_frames: u32,
    pub image_sha256: String,
    pub mask_sha256: String,
}

impl MappingEvidence {
    pub fn viewpoint_note(&self) -> &'static str {
        if self.clip == "B" {
            "same source, different viewpoint"
        } else {
            "A/C development clip"
        }
    }

    /// Invalid or unlocalized/shoulder observations produce no hazard proposal.
    pub fn abstention_reason(&self) -> Option<&'static str> {
        if self.lane == "shoulder" || self.lane == "unknown" {
            return Some("not_a_mapped_travel_lane");
        }
        let lane_index = self.lane.strip_prefix("lane_").and_then(|n| n.parse::<u32>().ok());
        if !lane_index.is_some_and(|n| self.lane == format!("lane_{n}")) {
            return Some("invalid_lane");
        }
        if self.clip.trim().is_empty() {
            return Some("missing_clip");
        }
        if self.position.coordinate_system != "road_reference_image"
            || self.position.metric_position_m.is_some()
            || !self.position.x_px.is_finite()
            || !self.position.y_px.is_finite()
            || self.position.x_px < 0.0
            || self.position.y_px < 0.0
        {
            return Some("invalid_or_uncalibrated_position");
        }
        if !self.confidence.is_finite() || !(0.0..=1.0).contains(&self.confidence) {
            return Some("invalid_heuristic_confidence");
        }
        if !self.since_s.is_finite()
            || self.since_s < 0.0
            || !(self.since_s + PROPOSAL_LIFETIME_S).is_finite()
        {
            return Some("invalid_observation_time");
        }
        if self.required_stationary_frames == 0
            || self.stationary_frames < self.required_stationary_frames
        {
            return Some("stationarity_requirement_not_met");
        }
        let valid_hash = |value: &str| {
            value.len() == 64 && value.bytes().all(|c| c.is_ascii_hexdigit())
        };
        if !valid_hash(&self.image_sha256) || !valid_hash(&self.mask_sha256) {
            return Some("invalid_evidence_hash");
        }
        None
    }
}

/// Raw model text and strict parsed output; credentials are never stored here.
#[derive(Clone, Debug, Serialize)]
pub struct LabelOutcome {
    pub source: &'static str,
    pub fallback_reason: Option<String>,
    pub provider: Option<String>,
    pub model_id: Option<String>,
    pub latency_ms: Option<f64>,
    pub raw_reply: Option<String>,
    pub reply: Reply,
    pub model_calls: u32,
}

impl LabelOutcome {
    pub fn fallback(reason: impl Into<String>) -> Self {
        Self {
            source: "fallback",
            fallback_reason: Some(reason.into()),
            provider: None,
            model_id: None,
            latency_ms: None,
            raw_reply: None,
            reply: Reply {
                label: "unknown stationary lane object".into(),
                blocks: Blocks::None,
                reach: Reach { scope: Scope::Nearby, radius_m: 0.0 },
                rationale: "No valid model label/reach reply; retain host mapping as a proposal only.".into(),
            },
            model_calls: 0,
        }
    }
}

pub fn parse_label(raw: &str) -> Result<Reply, String> {
    let reply: Reply = serde_json::from_str(raw.trim()).map_err(|_| "parse".to_string())?;
    reply.validate().map_err(|_| "parse".to_string())?;
    Ok(reply)
}

pub fn label_user(evidence: &MappingEvidence) -> String {
    serde_json::json!({
        "task": "Write only a label and reach for this host-mapped stationary lane object. Do not confirm, merge or move a vehicle.",
        "mapping_evidence": evidence,
        "confidence_kind": "heuristic",
        "map_id": "unlocalized_clip_road",
        "viewpoint_note": evidence.viewpoint_note(),
    }).to_string()
}

/// Development-only deferral is explicit, and never probes credentials or calls
/// the client. Final evidence runs use the default live-label path instead.
pub fn label_for_run(evidence: &MappingEvidence, defer_labels: bool) -> LabelOutcome {
    if defer_labels {
        LabelOutcome::fallback("dev_label_deferred")
    } else {
        live_label(evidence)
    }
}

/// Exactly one completion attempt per eligible observation, through the existing
/// Baseten adapter. Tests never invoke this function or inspect credentials.
pub fn live_label(evidence: &MappingEvidence) -> LabelOutcome {
    if let Some(reason) = evidence.abstention_reason() {
        return LabelOutcome::fallback(reason);
    }
    let key = std::env::var("BASETEN_API_KEY").ok();
    let endpoint = muse::select_talk(TalkKeys {
        baseten: key.as_deref(), merge: None, gemini: None, base: None,
        model: Some(muse::BASETEN_MODEL),
    });
    let Some(endpoint) = endpoint else { return LabelOutcome::fallback("no_key"); };
    let provider = endpoint.provider.clone();
    let model_id = endpoint.model.clone();
    let user = label_user(evidence);
    let chat = GeminiChat::from_endpoint(endpoint);
    let start = Instant::now();
    let completion = chat.complete(LABEL_SYSTEM, &user);
    let mut result = LabelOutcome::fallback("parse");
    result.provider = Some(provider);
    result.model_id = Some(model_id);
    result.latency_ms = Some(start.elapsed().as_secs_f64() * 1000.0);
    result.model_calls = 1;
    match completion {
        Ok(raw) => {
            if let Ok(reply) = parse_label(&raw) {
                result.source = "model";
                result.fallback_reason = None;
                result.reply = reply;
            }
            result.raw_reply = Some(raw);
        }
        Err(reason) => result.fallback_reason = Some(muse::negotiate_reason(&reason)),
    }
    result
}

/// SPEC hazard fields plus explicitly scene-local mapping metadata. Serialize
/// only: model JSON cannot deserialize a status or confirmation into this type.
#[derive(Clone, Debug, Serialize)]
pub struct MappedEdit {
    #[serde(flatten)]
    edit: RoadEdit,
    kind: &'static str,
    map_id: &'static str,
    clip: String,
    viewpoint_note: &'static str,
    track_id: u32,
    lane_blocked: String,
    position: Position,
    confidence: f64,
    confidence_kind: &'static str,
    stationary_frames: u32,
    required_stationary_frames: u32,
    author_note: &'static str,
    reach: Reach,
    label_provenance: LabelOutcome,
}

pub fn propose(evidence: &MappingEvidence, label: LabelOutcome) -> Result<Option<MappedEdit>, String> {
    if evidence.abstention_reason().is_some() {
        return Ok(None);
    }
    label.reply.validate()?;
    let edit = RoadEdit {
        id: format!("phase16d:{}:{}", evidence.clip, evidence.track_id),
        link: 0,
        route: Vec::new(),
        blocks: Blocks::Lane,
        since_s: evidence.since_s,
        author_car: 1,
        evidence: Evidence {
            image_sha256: evidence.image_sha256.clone(),
            mask_sha256: evidence.mask_sha256.clone(),
            label: label.reply.label.clone(),
        },
        status: Status::Proposed,
        confirmations: Vec::new(),
        expires_at: evidence.since_s + PROPOSAL_LIFETIME_S,
        merged_at: None,
    };
    Ok(Some(MappedEdit {
        edit,
        kind: "hazard",
        map_id: "unlocalized_clip_road",
        clip: evidence.clip.clone(),
        viewpoint_note: evidence.viewpoint_note(),
        track_id: evidence.track_id,
        lane_blocked: evidence.lane.clone(),
        position: evidence.position.clone(),
        confidence: evidence.confidence,
        confidence_kind: "heuristic",
        stationary_frames: evidence.stationary_frames,
        required_stationary_frames: evidence.required_stationary_frames,
        author_note: "Scene-local camera observation slot 1, not a localized city-graph vehicle.",
        reach: label.reply.reach.clone(),
        label_provenance: label,
    }))
}

impl MappedEdit {
    /// Only a host-verified independent sensor observation may reach the existing
    /// review method. The batch example has no review input and never calls this.
    /// Another frame/viewpoint from the same camera is not independent sensing.
    pub fn review(&mut self, reviewer: u32, at_s: f64, saw_blockage: bool, independent_sensor: bool) {
        if independent_sensor && at_s.is_finite() {
            self.edit.review(reviewer, at_s, saw_blockage);
        }
    }
}
