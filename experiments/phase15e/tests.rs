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
