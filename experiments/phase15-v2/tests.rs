use malleable::{
    network::Network,
    record::{Arm, Reach, RecordConfig, Reply, Scope},
    rush_hour::{self, Mock, Trip, Truth},
};
#[test]
fn granted_record_priority_has_a_merged_edit_and_due_public_deliveries() {
    let n = Network::town();
    let trips: Vec<_> = (1..=3)
        .map(|car| Trip {
            car,
            rider: 50000 + car,
            route: 0,
            depart_s: car as f64,
            request_s: 1.0,
            reason: if car == 1 {
                "My partner is in active labour"
            } else {
                "commuting"
            }
            .into(),
            truth: Truth::Ordinary,
            destination: "other".into(),
            claim_number: 1,
        })
        .collect();
    let cfg = RecordConfig {
        arm: Arm::Record,
        sensor_range_m: 300.0,
        proposal: None,
        reply: Reply::mock(),
        priority_reach: Reach {
            scope: Scope::City,
            radius_m: 300.0,
        },
    };
    let (_, s, _) = rush_hour::simulate_trips_recorded_v2(1, &Mock, trips, &n, cfg, None).unwrap();
    assert!(s
        .edits
        .iter()
        .any(|e| e.kind == "priority" && e.author_car == 1));
    assert!(!s.deliveries.is_empty());
    assert!(!s.delivered.is_empty());
    for e in &s.events {
        if let Some(issuer) = e.beneficiary {
            assert!(s
                .deliveries
                .iter()
                .any(|d| d.edit_id == format!("priority:{issuer}")
                    && d.car == e.car
                    && d.at_s <= e.at_s));
        }
    }
}

#[allow(dead_code)]
#[path = "../examples/phase15_v2_gate.rs"]
mod gate;
#[test]
fn near_and_labour_harness_validity_before_registration_not_outcome_bars() {
    let v = gate::validity().unwrap();
    assert_eq!(v["true_edit_merged"], true);
    assert!(v["hazard_reroutes"].as_u64().unwrap() >= 1);
    assert!(v["before_turnoff_distinct_cars"].as_u64().unwrap() >= 20);
    assert!(v["before_turnoff_max_simultaneous_cars"].as_u64().unwrap() >= 20);
    assert_eq!(v["labour_granted"], true);
    assert!(v["priority_edits"].as_u64().unwrap() >= 1);
    assert!(v["priority_deliveries"].as_u64().unwrap() >= 1);
    assert_eq!(v["leaks"], 0);
    assert_eq!(v["safety"], 0);
    assert_eq!(v["valid"], true);
}
