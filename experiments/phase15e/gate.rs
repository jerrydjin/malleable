use malleable::{network::Network, road_map::RoadMap};
use serde_json::{json, Value};
fn load() -> Result<(RoadMap, Value), String> {
    let map = RoadMap::read("maps/us101.json")?;
    let meta = serde_json::from_slice(
        &std::fs::read("assets/phase15e/import-manifest.json").map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    Ok((map, meta))
}
fn map_check() -> Result<Value, String> {
    let (map, meta) = load()?;
    let mut main = Vec::new();
    let mut ramps = Vec::new();
    let mut bad_lanes = Vec::new();
    let mut dangling = Vec::new();
    for m in meta["edges"].as_array().unwrap() {
        let e = &map.edges[m["edge"].as_u64().unwrap() as usize];
        let h = m["osm_tags"]["highway"].as_str().unwrap();
        if h == "motorway"
            && m["osm_tags"]["ref"]
                .as_str()
                .is_some_and(|r| r.contains("101"))
        {
            let osm_lanes = m["osm_tags"]["lanes"]
                .as_str()
                .and_then(|s| s.parse::<u8>().ok());
            if osm_lanes != Some(e.lanes) {
                bad_lanes.push(e.id);
            }
            main.push(json!({"edge":e.id,"osm_way":m["osm_way"],"from":e.from,"to":e.to,"from_lat":map.nodes[e.from].location.lat,"to_lat":map.nodes[e.to].location.lat,"lanes":e.lanes,"osm_lanes":osm_lanes,"length_m":e.length_m}));
        }
        if h == "motorway_link" {
            let entry = m["boundary_entry"] == true
                || map.edges.iter().any(|x| x.to == e.from && x.id != e.id);
            let exit = m["boundary_exit"] == true
                || map.edges.iter().any(|x| x.from == e.to && x.id != e.id);
            if !entry || !exit {
                dangling.push(e.id);
            }
            ramps.push(json!({"edge":e.id,"osm_way":m["osm_way"],"entry_connected_or_boundary":entry,"exit_connected_or_boundary":exit,"lanes":e.lanes}));
        }
    }
    let north = main
        .iter()
        .any(|e| e["to_lat"].as_f64() > e["from_lat"].as_f64());
    let south = main
        .iter()
        .any(|e| e["to_lat"].as_f64() < e["from_lat"].as_f64());
    let physical = Network::from_road_map_full_lanes(&map);
    let (error, inventory, short) = match physical {
        Ok(net) => {
            let inventory:Vec<_>=map.edges.iter().filter(|e|e.class==malleable::network::RoadClass::Motorway || e.class==malleable::network::RoadClass::Ramp).map(|e|json!({"edge":e.id,"declared_lanes":e.lanes,"physical_lanes":net.links.iter().filter(|l|!l.is_connector() && l.edge==e.id).count()})).collect();
            let short: Vec<_> = net
                .links
                .iter()
                .filter(|l| {
                    !l.is_connector()
                        && l.len
                            <= malleable::world::CAR_LENGTH_M + malleable::world::MIN_GAP_M + 0.51
                })
                .map(|l| json!({"link":l.id,"edge":l.edge,"len_m":l.len}))
                .collect();
            (None, inventory, short)
        }
        Err(e) => (Some(e), Vec::new(), Vec::new()),
    };
    let physical_lanes = error.is_none()
        && inventory
            .iter()
            .all(|r| r["declared_lanes"] == r["physical_lanes"]);
    let valid = north && south && bad_lanes.is_empty() && dangling.is_empty() && physical_lanes;
    Ok(
        json!({"kind":"map_validity_before_simulation","nodes":map.nodes.len(),"edges":map.edges.len(),"us101_mainline":main,"ramps":ramps,"both_directions":north&&south,"bad_osm_lane_counts":bad_lanes,"dangling_ramps":dangling,"full_physical_lane_inventory":inventory,"physical_lane_counts_match":physical_lanes,"physical_geometry_error":error,"short_host_roads":short,"valid":valid,"decision":if valid{"CONTINUE_TO_PLACEMENT"}else{"STOP"}}),
    )
}
fn main() -> Result<(), String> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if let Some(p) = args.iter().find_map(|a| a.strip_prefix("default-import=")) {
        let xml = std::fs::read_to_string(p).map_err(|e| e.to_string())?;
        let map = malleable::osm::import(&xml)?;
        print!(
            "{}\n",
            serde_json::to_string_pretty(&map).map_err(|e| e.to_string())?
        );
        return Ok(());
    }
    match args
        .iter()
        .find_map(|a| a.strip_prefix("part="))
        .unwrap_or("map-check")
    {
        "map-check" => println!("{}", map_check()?),
        _ => {
            return Err("Only map-check/default-import available before map validity passes".into())
        }
    }
    Ok(())
}
