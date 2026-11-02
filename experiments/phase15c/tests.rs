#[path = "../examples/phase15c_gate.rs"]
#[allow(dead_code)]
mod gate;
#[test]
fn all_five_candidates_keep_legal_turns_and_hospital_destination() {
    let w = gate::retained::build().unwrap();
    let c = gate::candidates(&w).unwrap();
    assert_eq!(c.len(), 5);
    assert_eq!(
        c.iter().map(|x| x.incoming).collect::<Vec<_>>(),
        vec![9, 80, 366, 386, 493]
    );
    for c in c {
        assert_eq!(w.net.links[*c.route.last().unwrap()].to, 4);
        let mut n = w.net.clone();
        n.register_experiment_route(c.route).unwrap();
    }
}
#[test]
fn origin_change_keeps_all_ids_departures_requests_and_other_routes() {
    let w = gate::retained::build().unwrap();
    for c in gate::candidates(&w).unwrap() {
        for seed in 1..=10 {
            let (old, p) = gate::retained::population(seed, &w, true);
            let (n, a, q) = gate::population(seed, &w, &c, true).unwrap();
            let (_, b, g) = gate::population(seed, &w, &c, false).unwrap();
            assert_eq!(p, q);
            assert_eq!(p, g);
            assert_eq!(old.len(), a.len());
            let routes = n.routes();
            let old_routes = w.net.routes();
            for ((old, a), b) in old.iter().zip(&a).zip(&b) {
                assert_eq!(
                    (old.car, old.depart_s, old.request_s),
                    (a.car, a.depart_s, a.request_s)
                );
                assert_eq!(
                    (a.car, a.route, a.depart_s, a.request_s),
                    (b.car, b.route, b.depart_s, b.request_s)
                );
                if a.car != p {
                    assert_eq!(routes[a.route].2.links, old_routes[old.route].2.links);
                } else {
                    assert_eq!(routes[a.route].2.links, c.route);
                    assert_eq!(a.destination, "hospital");
                    assert_eq!(b.destination, "hospital");
                }
            }
        }
    }
}
#[test]
fn observer_starts_on_actual_entry_after_real_source_waiting() {
    use malleable::{
        network::Network,
        record::{Arm, Reach, RecordConfig, Reply, Scope},
        rush_hour::{self, Mock, Trip, Truth},
    };
    let n = Network::town();
    let approach = n.routes()[0].2.links[0];
    let trips: Vec<_> = (1..=15)
        .map(|car| Trip {
            car,
            rider: car + 50000,
            route: 0,
            depart_s: 0.,
            request_s: 0.,
            reason: "commuting".into(),
            truth: Truth::Ordinary,
            destination: "other".into(),
            claim_number: 1,
        })
        .collect();
    let cfg = RecordConfig {
        arm: Arm::SensorOnly,
        sensor_range_m: 300.,
        proposal: None,
        reply: Reply::mock(),
        priority_reach: Reach {
            scope: Scope::Nearby,
            radius_m: 500.,
        },
    };
    let (r, s, trace) =
        rush_hour::simulate_trips_phase15c(1, &Mock, trips, &n, cfg, 15, approach).unwrap();
    let entered = s.entered[&15];
    assert!(entered > 1., "test must exercise real off-map waiting");
    assert_eq!(trace.approach_enter_s, Some(entered));
    assert!(trace.dwell_s().unwrap() <= r.home[&15] - entered);
    assert_eq!(r.home.len(), 15);
}
