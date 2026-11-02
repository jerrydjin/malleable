use malleable::{network::Network, road_map::RoadMap};
#[test]
fn full_lane_inventory_is_opt_in_and_matches_five_lane_osm_metadata() {
    let map:RoadMap=serde_json::from_str(r#"{"version":1,"origin":[0,0],"nodes":[{"id":0,"lat":0,"lon":0,"demand_per_s":0.1},{"id":1,"lat":0,"lon":0.01,"sink_weight":1}],"edges":[{"id":0,"from":0,"to":1,"lanes":5,"speed_limit_mps":29,"length_m":1000,"one_way":true,"class":"motorway"}]}"#).unwrap();
    assert!(map.validate().is_err());
    assert!(map.validate_full_lanes().is_ok());
    let n = Network::from_road_map_full_lanes(&map).unwrap();
    assert_eq!(
        n.links
            .iter()
            .filter(|l| !l.is_connector() && l.edge == 0)
            .count(),
        5
    );
    assert_eq!(n.sources.len(), 5);
    assert_eq!(n.sinks.len(), 5);
    assert!(n.routes().iter().all(|(_, _, r)| r.links.len() == 1));
}
#[test]
fn default_validation_still_rejects_more_than_two_lanes() {
    let mut map = Network::town().to_road_map();
    map.edges[0].lanes = 3;
    assert!(map.validate().is_err());
    assert!(Network::from_road_map(&map).is_err());
}
#[test]
fn default_imports_are_byte_identical_to_retained_before_outputs() {
    let manifest: serde_json::Value = serde_json::from_str(
        &std::fs::read_to_string("assets/phase15e/default-import-before.json").unwrap(),
    )
    .unwrap();
    for (index, row) in manifest.as_array().unwrap().iter().enumerate() {
        let map =
            malleable::osm::import(&std::fs::read_to_string(row["osm"].as_str().unwrap()).unwrap())
                .unwrap();
        let bytes = format!("{}\n", serde_json::to_string_pretty(&map).unwrap());
        assert_eq!(
            bytes.len() as u64,
            row["default_json_bytes"].as_u64().unwrap()
        );
        let path = std::env::temp_dir().join(format!(
            "phase15e-default-import-{}-{index}.json",
            std::process::id()
        ));
        std::fs::write(&path, bytes).unwrap();
        assert_eq!(
            malleable::record::sha256(path.to_str().unwrap()).unwrap(),
            row["default_json_sha256"].as_str().unwrap()
        );
        std::fs::remove_file(path).unwrap();
    }
}
#[path = "../examples/phase15e_traffic.rs"]
#[allow(dead_code)]
mod traffic;
#[test]
fn freeway_population_keeps_cited_flow_and_all_lane_paths_are_legal() {
    let w = traffic::build().unwrap();
    assert_eq!(w.through.len(), 2);
    for variants in &w.through {
        assert_eq!(variants.len(), 60);
        for &id in variants {
            let p = &w.routes[id];
            for pair in p.windows(2) {
                if w.net.links[pair[0]].is_connector() {
                    assert_eq!(w.net.links[pair[0]].via.unwrap().1, pair[1]);
                } else {
                    assert!(w.net.moves_from(pair[0]).contains(&pair[1]));
                }
            }
        }
    }
    for seed in 1..=10 {
        let p = traffic::population(seed, &w);
        assert_eq!(p.iter().filter(|t| t.mainline).count(), 3800);
        assert_eq!(
            p.iter()
                .map(|t| t.car)
                .collect::<std::collections::BTreeSet<_>>()
                .len(),
            p.len()
        );
        assert!(p.iter().all(|t| t.depart_s >= 0. && t.depart_s < 900.));
        assert!(p.iter().any(|t| t.affected));
    }
}
#[test]
fn stationary_queue_at_entry_with_unentered_demand_is_detected_as_off_map_spillback() {
    use malleable::{incident::LaneIncident, network::Network, record::Replies, road_map::RoadMap};
    let m:RoadMap=serde_json::from_str(r#"{"version":1,"origin":[0,0],"nodes":[{"id":0,"lat":0,"lon":0,"demand_per_s":0.1},{"id":1,"lat":0,"lon":0.002,"sink_weight":1}],"edges":[{"id":0,"from":0,"to":1,"lanes":1,"speed_limit_mps":20,"length_m":200,"one_way":true,"class":"motorway"}]}"#).unwrap();
    let net = Network::from_road_map_full_lanes(&m).unwrap();
    let roads = net.routes();
    let routes = roads
        .iter()
        .map(|(_, _, r)| r.links.clone())
        .collect::<Vec<_>>();
    let source = routes[0][0];
    let incident = LaneIncident {
        version: 1,
        id: "spillback-test".into(),
        kind: "blocked_road".into(),
        map: "synthetic".into(),
        edge: 0,
        from_node: 0,
        to_node: 1,
        lane: 0,
        position_m: 20.,
        length_m: 8.,
        start_s: 240.,
        duration_s: 900.,
        rationale: "test observer against actual stationary entry queue".into(),
    };
    let w = traffic::World {
        net,
        routes,
        through: vec![vec![0]],
        local: Vec::new(),
        blocked_edge: 0,
        blocked_link: source,
        incident,
        replies: Replies::read("docs/gates/phase-15-model-replies.json").unwrap(),
    };
    let p = (1..=20)
        .map(|car| traffic::Input {
            car,
            route: 0,
            depart_s: 240. + car as f64 * 0.1,
            mainline: true,
            affected: true,
            source,
        })
        .collect::<Vec<_>>();
    let r = traffic::simulate(1, &w, &p, true).unwrap();
    assert!(r.spill.seconds > 0.);
    assert!(r.spill.peak_pending > 0);
    assert!(r.spill.first_at_s.unwrap() >= 240.);
    assert!(r.snapshot.entered[&20] > p[19].depart_s + 30.);
    assert_eq!(r.home.len(), 20);
}
