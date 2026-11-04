use malleable::{
    negotiate::ScriptedTalk,
    network::{run_priority_town, RoadClass, QUEUED_MPS},
    replay::ReplayArchive,
};
use std::path::Path;

fn recording(name: &str) -> ReplayArchive {
    ReplayArchive::read(
        &Path::new(env!("CARGO_MANIFEST_DIR")).join(format!("recordings/{name}.json")),
    )
    .unwrap()
}

#[test]
fn saved_grant_reaches_future_links_before_arrival_and_has_no_junction_restop() {
    let original = recording("grant");
    let fixed = recording("grant-v2");
    assert_eq!(
        serde_json::to_value(&original.board.reason.as_ref().unwrap().decision).unwrap(),
        serde_json::to_value(&fixed.board.reason.as_ref().unwrap().decision).unwrap(),
        "the saved model reply is reused verbatim"
    );
    assert_eq!(original.reply_seconds, fixed.reply_seconds);
    let town = &fixed.board.town;
    let priority = town.priority.as_ref().unwrap();
    let current = run_priority_town(7, priority.request, true, Box::new(ScriptedTalk));
    assert_eq!(
        serde_json::to_value(&town.frames).unwrap(),
        serde_json::to_value(&current.frames).unwrap(),
        "the new recording contains the executor's actual motion"
    );
    let start = priority.request.at_s as usize;
    assert_eq!(
        serde_json::to_value(&original.board.town.frames[..=start]).unwrap(),
        serde_json::to_value(&town.frames[..=start]).unwrap(),
        "no priority acts before the saved grant"
    );
    let car = |t: usize| {
        town.frames[t]
            .cars
            .iter()
            .find(|c| c.0 == priority.request.car_id)
    };
    let origin = car(start).unwrap().2;
    let route = &town.routes[priority.route.unwrap()];
    let mut starts = Vec::new();
    let mut distance = 0.0;
    for &link in route {
        starts.push(distance);
        distance += town.links[link].len;
    }
    assert!(
        town.frames[start + 1..start + 5].iter().any(|frame| {
            frame.make_way.iter().any(|&(id, beneficiary, ref action)| {
                if beneficiary != priority.request.car_id || action != "clear" {
                    return false;
                }
                let recipient = frame.cars.iter().find(|c| c.0 == id).unwrap();
                let own = &town.routes[recipient.1 as usize];
                let mut offset = recipient.2;
                let link = own
                    .iter()
                    .copied()
                    .find(|&link| {
                        if offset < town.links[link].len {
                            true
                        } else {
                            offset -= town.links[link].len;
                            false
                        }
                    })
                    .unwrap();
                route
                    .iter()
                    .position(|&l| l == link)
                    .is_some_and(|k| starts[k] > origin + 110.0)
            })
        }),
        "the message reaches cars beyond the old local radius before the priority car arrives"
    );

    // The request is made in an existing stationary queue. Once that queue
    // starts moving, every remaining junction must be crossed without requeueing.
    let moving = (start..town.frames.len())
        .find(|&t| car(t).is_some_and(|c| c.3 >= QUEUED_MPS))
        .unwrap();
    for t in moving..town.frames.len() {
        if let Some(c) = car(t) {
            assert!(
                c.3 >= QUEUED_MPS,
                "priority car stopped again at {t}s: {c:?}"
            );
        }
    }
    for (k, &link) in route.iter().enumerate() {
        if town.links[link].class == RoadClass::Connector && starts[k] > origin {
            assert!(
                (moving..town.frames.len())
                    .any(|t| car(t).is_some_and(|c| c.2 >= starts[k] + town.links[link].len)),
                "priority car never cleared connector {link}"
            );
        }
    }
    assert_eq!(town.stats.overlaps + town.stats.crossing_conflicts, 0);
    assert!(priority.time_home_s < original.board.town.priority.unwrap().time_home_s);
}

#[test]
fn saved_denial_has_identical_motion_reply_and_no_priority_signal() {
    let original = recording("deny");
    let fixed = recording("deny-v2");
    assert_eq!(
        serde_json::to_value(original).unwrap(),
        serde_json::to_value(&fixed).unwrap()
    );
    assert!(!fixed.board.reason.unwrap().decision.granted);
    assert!(!fixed.board.town.priority.unwrap().enabled);
    assert!(fixed
        .board
        .town
        .frames
        .iter()
        .all(|f| f.make_way.is_empty()));
}
