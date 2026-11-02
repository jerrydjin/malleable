# Phase 15c verification — 2 November 2026

**STOP: baseline validity fails, 5/10 qualifying seeds; 8/10 were required.** The fixed origin is retained. No outcome preregistration, RECORD outcome, gym outcome matrix or scores were created. No origin/demand changes followed this finding.

## Ordered commits

Actual `git log --reverse --format='%h %ad %s' --date=iso e4ba2a6..HEAD` before this verification commit:

```text
26d619b 2026-11-02 11:38:41 +0000 Implement isolated 15c labour gate and fixed baseline-only origin rule before diagnostics
2a5231b 2026-11-02 11:41:01 +0000 Retain 15c validity STOP: fixed best approach reaches 30 s delay on only 5 of 10 seeds
```

The next commit adds this verification record. Rerunning that command includes its hash/timestamp; the PR body contains the complete final list. Code precedes all candidate diagnostics. Validity follows, and the required STOP omits preregistration/scoring. All commits were made on Monday 2 November, before 23:00 UK (GMT).

## Every retained file is byte-identical

Command: `python3 experiments/phase15c/verify.py`. This compares every tracked file at the exact base commit with its Git blob, checks that all changes are additions in allowed 15c paths, and compares the generated protected sources with their retained originals.

```json
{"all_changes_additive_in_15c_paths": true, "base_commit": "e4ba2a6e9555f99baec8dfaf1ea9c5a6a7766b50", "byte_identical": true, "generated_protected_sources_identical": true, "retained_files": 433}
```

The complete [retained-file SHA-256 manifest](../assets/phase15c/retained-files.sha256) has **433/433 OK**. Judge, schema, make_way.rs, the v2 patch, all earlier results, scenarios, maps, model-reply cache and SAM files are included.

## Input hashes recorded before validity

The [442-file pre-validity inventory](../assets/phase15c/pre-validity-inputs.sha256) and [44-file generated build inventory](../assets/phase15c/generated-code.sha256) were committed with the code before diagnostics. Both match exactly after the STOP and replays. This input inventory is an execution record, **not an outcome preregistration or an assertion that validity passed**.

```text
sha256sum -c assets/phase15c/pre-validity-inputs.sha256: 442 OK
sha256sum -c assets/phase15c/retained-files.sha256: 433 OK
generated build SHA-256 checks: 44 OK
retained Phase 15a freeze: 85 OK
retained Phase 15b freeze: 89 OK
retained Phase 15 v2 freeze: 143 OK
```

Inventory hashes:

```text
a6e3d25ede6248f6027ad011bb2f6716dae4936ff31fffb11290a35dc77f0c4c  assets/phase15c/pre-validity-inputs.sha256
dd9ef1bd02a812a938460a17dda3196d35231a3b817420dd50586ff84f897832  assets/phase15c/generated-code.sha256
db6a5aad7ed57c4669df589adc9fe2ee73f464c76140c24937305d2abc4cc9ed  assets/phase15c/retained-files.sha256
```

`python3 scripts/phase15-sam.py --check` exited 0:

```json
{"check": "OK", "image_sha256": "07030ee22246306d776c80c74defe29c214914eac81cb2a7fbaae17b3997e55d", "mask_sha256": "0d42d9b407d9e19cd84049a571e015d18e8b0e25faf879dfd1a7d14b806e1c77"}
```

## Replays and the forbidden outcome gate

No score replay exists because validity requires stopping before any outcome score. In its place, **all 50 candidate/seed SENSOR_ONLY baselines and the independent ten-seed selected validity reproduce byte for byte**:

```sh
bash scripts/phase15c.sh run part=origins > /tmp/phase15c-origins-replay.json
cmp assets/phase15c/origin-manifest.json /tmp/phase15c-origins-replay.json
bash scripts/phase15c.sh run part=validity > /tmp/phase15c-validity-replay.json
cmp assets/phase15c/validity.json /tmp/phase15c-validity-replay.json
```

Both commands and comparisons exited 0. Actual completion output and hashes:

```text
All candidate diagnostics and selected validity replay: cmp OK
162f0a09bae8fd21358b13afc25f73f60ba5e8718997d536de0e59fee85027be  /tmp/phase15c-origins-replay.json
2b734939b8c2b98190ef0b20cdfcbe1ebb4dc31acb51da74b0fe0bb1e6ad7035  /tmp/phase15c-validity-replay.json
```

The explicit score-guard check exited 1 and emitted **zero score bytes**, before any scoring simulation:

```text
    Finished `release` profile [optimized] target(s) in 0.02s
     Running `target/phase15c/release/examples/phase15c_gate part=score`
fatal: path 'docs/gates/phase-15c-code-freeze.sha256' does not exist in 'HEAD'
Error: "committed passing validity and preregistration required before scoring"
```

## Full test output

The retained suite passes **208 tests**, with **0 failures and 3 existing live tests ignored**. The isolated build passes **92 tests**, with **0 failures**. The final targeted run confirms the three 15c regressions against the exact generated code. No test required a model/API call.

New tests:

- `all_five_candidates_keep_legal_turns_and_hospital_destination`
- `origin_change_keeps_all_ids_departures_requests_and_other_routes`
- `observer_starts_on_actual_entry_after_real_source_waiting`

The observer regression exercises real source waiting and checks its entry timestamp against the host receipt, rather than treating departure as map entry. The population regression covers all five candidate routes and seeds 1–10, including the same-route gym twin. The retained leak/spoof and corrected-host priority-delivery tests also pass.

### cargo test --offline

```text
warning: unused import: `NET_DT_S`
 --> examples/phase13g_gate.rs:4:77
  |
4 |     network::{BroadcastConfig, MakeWayMode, Network, ScheduledCar, TownSim, NET_DT_S},
  |                                                                             ^^^^^^^^
  |
  = note: `#[warn(unused_imports)]` (part of `#[warn(unused)]`) on by default

warning: `malleable` (example "phase13g_gate") generated 1 warning (run `cargo fix --example "phase13g_gate" -p malleable` to apply 1 suggestion)
    Finished `test` profile [unoptimized + debuginfo] target(s) in 0.07s
     Running unittests src/lib.rs (target/debug/deps/malleable-ae6f8c692db9e574)

running 79 tests
test board_server::tests::asynchronous_reply_is_replayed_before_the_yield ... ok
test board_server::tests::successive_priority_calls_keep_both_agreements_when_replies_overlap ... ok
test demo::tests::a_delivered_reply_starts_dialogue_without_the_approach_hold ... ok
test board_server::tests::recording_saves_the_received_model_words_and_reply_time ... ok
test demo::tests::a_failed_state_poll_retains_a_gate_report ... ok
test demo::tests::clock_is_continuous_and_freezes_on_the_final_reason_under_two_minutes ... ok
test demo::tests::http_request_headers_tolerate_a_scheduling_pause ... ok
test demo::tests::real_http_gate_prefetches_event_zero_and_posts_are_idempotent ... ok
test demo::tests::trickled_http_bytes_cannot_extend_the_poll_deadline ... ok
test demo::tests::watchdog_publishes_without_polls_and_discards_a_client_ignoring_its_deadline ... ok
test demo::tests::weak_request_clock_shows_both_refusals_without_another_negotiation ... ok
test judge::tests::collision_or_incomplete_is_red ... ok
test judge::tests::main_then_ramp_is_unfair ... ok
test judge::tests::meter_overlap_counts_when_cells_differ ... ok
test judge::tests::shared_cell_counts_as_a_collision ... ok
test judge::tests::side_by_side_upstream_is_not_a_collision ... ok
test judge::tests::zipper_snapshot_is_green ... ok
test muse::tests::baseten_api_key_selects_the_hackathon_model ... ok
test muse::tests::baseten_base_uses_the_openai_shape_and_the_named_model ... ok
test muse::tests::client_selection_follows_the_key ... ok
test muse::tests::completion_text_ignores_reasoning_content ... ok
test muse::tests::completion_text_reads_openai_and_gemini_bodies ... ok
test muse::tests::http_marker_keeps_the_status_and_drops_the_body ... ok
test muse::tests::missing_markers_are_an_error_string ... ok
test muse::tests::negotiate_reason_is_a_token_without_the_key ... ok
test muse::tests::rust_deadline_kills_a_process_that_does_not_have_a_provider_timer ... ok
test negotiate::tests::a_car_with_no_neighbor_merges_alone ... ok
test negotiate::tests::a_fallback_reason_is_a_token_and_does_not_carry_the_key ... ok
test negotiate::tests::a_transport_error_uses_the_scripted_exchange ... ok
test negotiate::tests::accept_follows_the_turn_the_peer_already_spoke ... ok
test negotiate::tests::fallback_matches_local_negotiate_when_the_reply_is_unusable ... ok
test negotiate::tests::live_clearing_and_proceeding_lines_preserve_the_spoken_order ... ok
test negotiate::tests::mock_prompt_is_symbolic_and_the_recorded_reply_is_obeyed ... ok
test negotiate::tests::model_formatting_and_long_lines_are_repaired_without_changing_roles ... ok
test negotiate::tests::natural_proceed_heading_and_holding_lines_keep_their_actual_roles ... ok
test negotiate::tests::one_retry_recovers_parse_and_transport_errors_with_remaining_budget ... ok
test negotiate::tests::parse_diagnostics_are_redacted_and_bounded ... ok
test negotiate::tests::prompt_contains_no_canned_example_sentence ... ok
test negotiate::tests::recorded_gemini_body_parses_to_a_model_decision ... ok
test negotiate::tests::speech_has_eight_words_at_most_and_no_numbers_units_or_telemetry ... ok
test negotiate::tests::spoken_yield_and_go_roles_cannot_be_reversed ... ok
test negotiate::tests::trimming_preserves_a_role_after_a_long_preamble ... ok
test network::fleet_release_tests::denial_or_revocation_releases_every_held_vehicle_within_one_tick ... ok
test network::junction::tests::advance_warning_reacts_then_holds_cross_traffic_without_a_speed_command ... ok
test network::junction::tests::local_hearing_hold_budget_and_late_braking_decline ... ok
test network::junction::tests::occupied_crossing_is_never_revoked ... ok
test network::junction::tests::opted_in_receiver_still_declines_self_expired_and_physics ... ok
test network::junction::tests::topology_blocks_forced_return_but_accepts_real_hampshire_bypass ... ok
test network::record_host::tests::road_obstacle_spans_cover_every_parallel_but_lane_obstacles_do_not ... ok
test network::tests::ease_off_releases_when_the_ambulance_passes_the_conflict ... ok
test network::tests::fallback_log_prints_the_reason_token ... ok
test network::tests::gap_shift_moves_the_car_without_the_pullover_brake ... ok
test network::tests::town_has_junctions_and_trips ... ok
test osm::tests::area_centroid_ignores_vertex_density_and_ring_direction ... ok
test prefs::tests::fair_sentences_are_balanced ... ok
test prefs::tests::priority_sentences_favor_one_approach ... ok
test prefs::tests::structured_line_wins_over_fair_english ... ok
test rush_hour::live_batch_tests::batch_identities_and_reversed_roles_cannot_cross_assign_priority ... ok
test rush_hour::live_batch_tests::contemporaneous_conflicts_are_batched_and_only_rejected_items_retry ... ok
test rush_hour::live_batch_tests::expired_global_budget_still_grants_medical_fallback_and_blocks_injection ... ok
test rush_hour::live_batch_tests::slow_provider_cannot_exceed_shared_run_budget ... ok
test slot::tests::a_car_ahead_of_the_open_lane_is_not_shifted_into_it ... ok
test slot::tests::a_car_not_yet_on_the_stretch_is_kept_off ... ok
test slot::tests::a_follower_eases_off_rather_than_closing_on_a_waiting_ambulance ... ok
test slot::tests::a_follower_who_would_fill_the_hole_is_not_gap_shifted ... ok
test slot::tests::a_queue_spilled_upstream_is_the_open_lane_and_is_not_asked ... ok
test slot::tests::gap_shift_is_preferred_over_ease_off_when_both_would_clear ... ok
test slot::tests::only_a_car_inside_the_slot_is_asked_and_the_gap_wins ... ok
test slot::tests::the_blocked_lane_puts_the_slot_on_the_open_lane ... ok
test world::tests::ascii_names_the_open_road_the_wreck_and_the_jam ... ok
test world::tests::ascii_reads_as_a_ramp_merge ... ok
test world::tests::ascii_shows_the_car_inside_the_gate ... ok
test world::tests::dumb_equal_holds_the_gore ... ok
test world::tests::fog_hides_the_tail_and_shows_the_other_mouth ... ok
test world::tests::queues_are_meters_and_side_by_side_do_not_overlap ... ok
test world::tests::selfish_fronts_overlap_in_the_gore ... ok
test world::tests::surge_keeps_both_approaches_nonempty ... ok
test world::tests::zipper_respects_accel_gaps_and_gets_home ... ok
test demo::tests::fast_provider_phases_stay_inside_their_budgets ... ok

test result: ok. 79 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 37.91s

     Running unittests src/main.rs (target/debug/deps/malleable-d600360b545b55a8)

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

     Running tests/admission.rs (target/debug/deps/admission-aaa00be846df3e9d)

running 1 test
test mid_link_admission_overlaps_unless_occupants_are_checked ... ok

test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.02s

     Running tests/board.rs (target/debug/deps/board-32a1c27480cc75b0)

running 3 tests
test cli_labels_the_stub_scripted ... ok
test help_points_at_the_board_without_fakeecho ... ok
test board_dinner_is_red_red_green ... ok

test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 1.68s

     Running tests/boxed_in.rs (target/debug/deps/boxed_in-c4182516a685b0fb)

running 1 test
test boxed_rule_is_fixed_and_typical_demand_is_separate ... ok

test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.18s

     Running tests/corridor_demand.rs (target/debug/deps/corridor_demand-1e739bbf7bd511f1)

running 2 tests
test invalid_profiles_fail_before_demand_or_simulation ... ok
test cited_sf_profile_uses_the_fixed_potrero_route_and_counted_arrival_rate ... ok

test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.91s

     Running tests/demo.rs (target/debug/deps/demo-ca3996f2009f2751)

running 2 tests
test missing_live_credentials_still_write_exactly_one_failed_gate_line ... ok
test demo_is_one_continuous_town_and_ends_on_hospital_priority ... ok

test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.96s

     Running tests/driving_actions.rs (target/debug/deps/driving_actions-f6cc0a6c2107e495)

running 2 tests
test gap_acceptance_has_no_overlap_even_with_braking_followers ... ok
test rerouting_finishes_at_original_sink_and_scores_repeat_bit_for_bit has been running for over 60 seconds
test rerouting_finishes_at_original_sink_and_scores_repeat_bit_for_bit ... ok

test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 62.83s

     Running tests/fleet_interface.rs (target/debug/deps/fleet_interface-847e3bb05bed2da3)

running 6 tests
test expired_and_not_yet_issued_requests_are_ignored ... ok
test hold_is_capped_including_cumulative_time_and_invalid_values ... ok
test ignore_is_always_allowed_and_every_vehicle_has_one_ordered_action ... ok
test physics_rejection_cannot_be_overridden_by_a_fleet_action ... ok
test replay_drops_scheduled_deliveries_after_revocation ... ok
test message_wire_and_delivery_log_round_trip_and_replay ... ok

test result: ok. 6 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 32.00s

     Running tests/incidents.rs (target/debug/deps/incidents-bf7820360b707c9b)

running 6 tests
test activation_allows_existing_occupants_to_clear_but_stops_followers ... ok
test cars_stop_for_the_obstacle_and_resume_after_its_fixed_end ... ok
test incident_metadata_never_enters_the_model_request ... ok
test a_grant_cannot_bypass_the_block_and_all_lane_changes_remain_physical ... ok
test invalid_and_duplicate_physical_inputs_are_rejected ... ok
test incident_metadata_roundtrips_and_bad_replay_references_fail ... ok

test result: ok. 6 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 1.40s

     Running tests/live_adapter.rs (target/debug/deps/live_adapter-f3bdaffc3ca0aa8d)

running 6 tests
test curl_timeout_obeys_remaining_deadline_without_starting_another_request ... ok
test live_merge_and_hospital_dialogue_varies_without_changing_order ... ignored, six genuine Baseten exchanges to check merge/hospital wording variation
test non_cooperative_provider_finishes_with_three_logged_fallbacks ... ignored, real-time watchdog gate with three non-cooperative exchanges, approximately 111 seconds
test slow_first_http_reply_completes_the_demo_with_three_model_exchanges ... ignored, real-time three-scene HTTP gate, approximately 105 seconds
test curl_adapter_recovers_a_parse_failure_and_a_transport_failure ... ok
test two_transport_errors_back_off_and_recover_inside_one_budget ... ok

test result: ok. 3 passed; 0 failed; 3 ignored; 0 measured; 0 filtered out; finished in 3.25s

     Running tests/live_prefetch.rs (target/debug/deps/live_prefetch-85a3f0eece73c1ce)

running 2 tests
test prefetch_contains_only_independent_claims_and_preserves_causal_history ... ok
test score_counts_each_fallback_cause_without_changing_mock_wire_bytes ... ok

test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 13.65s

     Running tests/make_way.rs (target/debug/deps/make_way-d75a7ac84d5abade)

running 4 tests
test lookahead_reaches_the_queue_on_a_long_motorway_link ... ok
test pullover_rejoins_when_the_emergency_is_ahead_and_does_not_wait_out_the_queue ... ok
test relays_pay_the_hop_delay_and_full_share_connects_everyone ... ok
test the_same_layer_clears_a_different_graph_without_a_collision ... ok

test result: ok. 4 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

     Running tests/map_board.rs (target/debug/deps/map_board-1353b940c898967d)

running 1 test
test loaded_map_demo_reason_and_saved_replay_preserve_projected_motion ... ok

test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 17.19s

     Running tests/negotiate.rs (target/debug/deps/negotiate-4db1d975a7b53692)

running 5 tests
test decide_reads_the_neighbor_and_the_heard_turn ... ok
test both_merge_holds_the_gore_instead_of_colliding ... ok
test symmetric_dinner_negotiates_without_a_collision ... ok
test two_cars_exchange_yield_and_merge_then_clear_the_gore ... ok
test every_jam_clears_the_gore_without_a_collision ... ok

test result: ok. 5 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.01s

     Running tests/network.rs (target/debug/deps/network-fd2dd583b6b43b21)

running 5 tests
test crossing_paths_never_hold_cars_at_once ... ok
test routes_follow_the_roads ... ok
test one_merge_speaks_and_the_yielder_waits ... ok
test rush_hour_queues_form_and_drain ... ok
test the_town_is_deterministic ... ok

test result: ok. 5 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 2.67s

     Running tests/osm_import.rs (target/debug/deps/osm_import-2843ddd61a7e4061)

running 8 tests
test deterministic_import_filters_access_and_keeps_largest_directed_component ... ok
test directional_lane_tags_and_missing_geometry_are_handled_explicitly ... ok
test distinct_roundabout_halves_are_not_mistaken_for_reverse_carriageways ... ok
test hospital_closed_way_uses_area_centroid_independent_of_vertex_density ... ok
test importer_cli_writes_exact_format_and_rejects_bad_usage ... ok
test real_potrero_junction_keeps_positive_connectors_and_hospital_area ... ok
test sub_car_length_spans_are_removed_before_retaining_drivable_routes ... ok
test committed_sf_extract_imports_with_the_verified_hospital ... ok

test result: ok. 8 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 9.34s

     Running tests/payoff.rs (target/debug/deps/payoff-ccb723f8ee33430a)

running 3 tests
test demo_reason_require_live_does_not_print_a_mock_rush_hour_table ... ok
test boxed_grant_is_at_least_twenty_seconds_sooner_and_shown_on_the_board has been running for over 60 seconds
test reason_cli_uses_the_boxed_corridor_and_a_scripted_grant has been running for over 60 seconds
test reason_cli_uses_the_boxed_corridor_and_a_scripted_grant ... ok
test boxed_grant_is_at_least_twenty_seconds_sooner_and_shown_on_the_board ... ok

test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 64.16s

     Running tests/priority.rs (target/debug/deps/priority-858946dd911925de)

running 3 tests
test a_model_must_acknowledge_the_priority_before_clearing_its_path ... ok
test two_relayed_agreements_get_the_same_car_home_sooner_without_collisions ... ok
test priority_board_keeps_the_sticky_scores_and_reports_the_paired_baseline ... ok

test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 4.25s

     Running tests/propagation.rs (target/debug/deps/propagation-5715844336423c91)

running 2 tests
test invalid_propagation_configuration_is_rejected ... ok
test bulletins_follow_grants_and_relay_causally_without_self_holds ... ok

test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 24.36s

     Running tests/reasons.rs (target/debug/deps/reasons-5774869e83a64fdc)

running 13 tests
test a_bad_first_reply_can_recover_within_one_shared_budget ... ok
test fallback_covers_plausible_medical_claims_and_critical_negative_signs ... ok
test injected_controls_bad_ids_and_contradictory_or_long_speech_fail_closed ... ok
test live_first_person_movement_is_accepted_without_changing_or_reversing_words ... ok
test cli_requires_a_live_source_and_rejects_reason_mode_conflicts ... ok
test offline_policy_handles_urgent_and_routine_reasons_without_secret_access ... ok
test real_http_input_reaches_the_policy_and_safe_trip_and_rejects_cross_origin_injection ... ok
test realistic_replies_parse_and_generic_lines_do_not ... ok
test reason_debug_redacts_long_tokens_and_never_prints_a_key ... ok
test reasons_are_bounded_data_and_obvious_injections_never_reach_a_model ... ok
test seizure_parse_failure_grants_safe_priority_and_never_claims_to_be_live ... ok
test speech_answers_the_actual_reason_and_polite_refusals_keep_the_spoken_roles ... ok
test mock_reason_table_changes_only_existing_safe_precedence ... ok

test result: ok. 13 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 5.60s

     Running tests/recording.rs (target/debug/deps/recording-556f2aff9349237c)

running 1 test
test typed_reason_can_be_saved_and_exported_without_new_decisions ... ok

test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 29.61s

     Running tests/replay.rs (target/debug/deps/replay-703b88a84a368c4d)

running 3 tests
test replay_rejects_unknown_versions_broken_routes_and_missing_acknowledgements ... ok
test replay_text_stays_data_inside_the_page ... ok
test replay_preserves_every_storys_exact_motion_words_reasons_and_source ... ok

test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 10.03s

     Running tests/rider_history.rs (target/debug/deps/rider_history-64da645ff4a70442)

running 3 tests
test completed_history_catches_third_claims_without_revealing_future_outcomes ... ok
test instructions_in_current_claim_or_history_and_future_evidence_are_blocked ... ok
test history_mode_and_counterfactual_keep_exactly_the_same_demand ... ok

test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 5.73s

     Running tests/road_map.rs (target/debug/deps/road_map-2774483ceeda1ed5)

running 4 tests
test another_lat_lon_graph_honors_direction_lanes_speed_and_length ... ok
test checked_in_town_export_loads_and_matches_current_export ... ok
test malformed_maps_fail_before_simulation ... ok
test exported_native_map_preserves_geometry_routes_and_scores_bit_for_bit has been running for over 60 seconds
test exported_native_map_preserves_geometry_routes_and_scores_bit_for_bit ... ok

test result: ok. 4 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 81.86s

     Running tests/road_record.rs (target/debug/deps/road_record-16f01c68b4b50104)

running 6 tests
test edit_needs_a_later_distinct_sensor_witness_and_two_negatives_reject_spoof ... ok
test model_reply_cannot_inject_motion_controls ... ok
test blocked_road_covers_parallel_clones_but_legacy_lane_validation_stays_strict ... ok
test route_decision_source_has_no_ground_truth_or_reachability_guard ... ok
test spoof_is_rejected_without_delivery_knowledge_or_reroutes ... ok
test no_car_changes_route_before_its_own_sighting_or_edit_delivery ... ok

test result: ok. 6 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 2.47s

     Running tests/road_record_birth.rs (target/debug/deps/road_record_birth-431072822961afbb)

running 3 tests
test granted_priority_is_a_record_but_denied_gym_has_no_edit_or_action ... ok
test unfinished_never_departed_never_entered_and_on_network_are_retained ... ok
test birth_twins_preserve_every_trip_and_declared_cross_flow ... ok

test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 26.48s

     Running tests/rush_board.rs (target/debug/deps/rush_board-741edc564c41577a)

running 2 tests
test dense_replay_preserves_measured_motion_and_causal_bulletins ... ok
test typed_rider_is_unknown_then_actual_completed_gym_trips_catch_third_claim has been running for over 60 seconds
test typed_rider_is_unknown_then_actual_completed_gym_trips_catch_third_claim ... ok

test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 82.69s

     Running tests/rush_hour.rs (target/debug/deps/rush_hour-8fb2e73e8920d296)

running 4 tests
test paired_score_uses_median_gain_signed_cost_and_nearest_rank_p95 ... ok
test pool_is_fixed_with_repeated_riders_and_hidden_truth ... ok
test wrong_policy_identity_is_rejected_before_it_can_affect_a_car ... ok
test fcfs_is_deterministic_and_keyword_uses_identical_demand ... ok

test result: ok. 4 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 7.91s

     Running tests/scale_sweep.rs (target/debug/deps/scale_sweep-42e321f6e74f33ec)

running 2 tests
test reruns_score_identically ... ok
test sticky_board_holds_at_fleet_scale ... ok

test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 1.64s

     Running tests/signals.rs (target/debug/deps/signals-2ebd937a6d2323b2)

running 2 tests
test cited_intervals_follow_the_preregistered_tables ... ok
test a_red_approach_holds_an_ordinary_car_and_releases_a_stopped_ambulance ... ok

test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.01s

     Running tests/slot.rs (target/debug/deps/slot-0261732bbecd3fcc)

running 2 tests
test only_a_car_in_the_slot_is_messaged_and_a_bystander_is_not ... ok
test dont_enter_keeps_a_joiner_off_the_stretch_until_the_ambulance_has_passed ... ok

test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.01s

     Running tests/slot_cited.rs (target/debug/deps/slot_cited-d74b73ca035edb2d)

running 2 tests
test cited_policies_keep_speed_band_and_exclude_the_operative_nine_metre_pocket ... ok
test cited_existing_gap_is_checked_separately_from_road_reserve_and_legacy_stays_40m ... ok

test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

     Running tests/slot_v2.rs (target/debug/deps/slot_v2-1240ff42504451b8)

running 3 tests
test moving_or_distant_predecessors_and_bystanders_are_not_queue_conflicts ... ok
test v2_extracts_only_the_nearest_real_queue_conflict_even_when_the_return_hole_may_fill ... ok
test v2_keeps_the_connector_stopping_room_and_requires_a_parallel ... ok

test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

     Running tests/sticky_fail.rs (target/debug/deps/sticky_fail-bcebfd14cf9f1815)

running 9 tests
test follow_plan_without_a_broadcast_does_not_clear_the_jam ... ok
test priority_plan_gets_home_and_stays_unfair ... ok
test reversed_queue_is_rejected_and_brakes_are_rejected ... ok
test mid_run_rewrite_stays_green ... ok
test selfish_ignores_a_broadcast_plan ... ok
test show_dinner_path_reads_wreck_jam_and_clear ... ok
test show_unfair_clear_does_not_print_green ... ok
test structured_bias_in_the_prompt_overrides_fair_english ... ok
test sticky_fail_baseline_red_and_plan_green ... ok

test result: ok. 9 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.03s

     Running tests/stories.rs (target/debug/deps/stories-ba64e4309f18456b)

running 11 tests
test a_chain_contains_three_real_cars_and_relays_the_same_detected_emergency ... ok
test a_counter_offer_needs_explicit_acceptance_and_a_bounded_delay ... ok
test an_accepted_counter_offer_waits_for_the_actual_crossing_before_priority ... ok
test detected_emergency_clears_the_route_without_a_rider_request ... ok
test denial_does_not_extend_the_weak_physical_priority_slot ... ok
test every_chain_participant_must_acknowledge_and_only_a_mouth_car_can_yield ... ok
test hospital_wins_simultaneous_requests_in_either_input_order ... ok
test repeated_weak_requests_stop_winning_even_with_new_ids_and_cars ... ok
test sustained_distress_detects_an_emergency_but_noise_and_missing_samples_do_not ... ok
test hospital_decision_is_carried_into_the_physical_yields ... ok
test valid_offer_delays_share_the_same_safety_governed_forecast ... ok

test result: ok. 11 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 1.85s

   Doc-tests malleable

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
```

### bash scripts/phase15c.sh test --release

```text
    Blocking waiting for file lock on build directory
   Compiling malleable v0.1.0 (/tmp/malleable-phase15c-build)
    Finished `release` profile [optimized] target(s) in 2m 19s
     Running unittests src/lib.rs (target/phase15c/release/deps/malleable-74e3ac266e331a8f)

running 81 tests
test board_server::tests::asynchronous_reply_is_replayed_before_the_yield ... ok
test board_server::tests::recording_saves_the_received_model_words_and_reply_time ... ok
test board_server::tests::successive_priority_calls_keep_both_agreements_when_replies_overlap ... ok
test demo::tests::a_delivered_reply_starts_dialogue_without_the_approach_hold ... ok
test demo::tests::clock_is_continuous_and_freezes_on_the_final_reason_under_two_minutes ... ok
test demo::tests::a_failed_state_poll_retains_a_gate_report ... ok
test demo::tests::http_request_headers_tolerate_a_scheduling_pause ... ok
test demo::tests::real_http_gate_prefetches_event_zero_and_posts_are_idempotent ... ok
test demo::tests::trickled_http_bytes_cannot_extend_the_poll_deadline ... ok
test demo::tests::watchdog_publishes_without_polls_and_discards_a_client_ignoring_its_deadline ... ok
test demo::tests::weak_request_clock_shows_both_refusals_without_another_negotiation ... ok
test judge::tests::collision_or_incomplete_is_red ... ok
test judge::tests::main_then_ramp_is_unfair ... ok
test judge::tests::meter_overlap_counts_when_cells_differ ... ok
test judge::tests::shared_cell_counts_as_a_collision ... ok
test judge::tests::side_by_side_upstream_is_not_a_collision ... ok
test judge::tests::zipper_snapshot_is_green ... ok
test muse::tests::baseten_api_key_selects_the_hackathon_model ... ok
test muse::tests::baseten_base_uses_the_openai_shape_and_the_named_model ... ok
test muse::tests::client_selection_follows_the_key ... ok
test muse::tests::completion_text_ignores_reasoning_content ... ok
test muse::tests::completion_text_reads_openai_and_gemini_bodies ... ok
test muse::tests::http_marker_keeps_the_status_and_drops_the_body ... ok
test muse::tests::missing_markers_are_an_error_string ... ok
test muse::tests::negotiate_reason_is_a_token_without_the_key ... ok
test muse::tests::rust_deadline_kills_a_process_that_does_not_have_a_provider_timer ... ok
test negotiate::tests::a_car_with_no_neighbor_merges_alone ... ok
test negotiate::tests::a_fallback_reason_is_a_token_and_does_not_carry_the_key ... ok
test negotiate::tests::a_transport_error_uses_the_scripted_exchange ... ok
test negotiate::tests::accept_follows_the_turn_the_peer_already_spoke ... ok
test negotiate::tests::fallback_matches_local_negotiate_when_the_reply_is_unusable ... ok
test negotiate::tests::live_clearing_and_proceeding_lines_preserve_the_spoken_order ... ok
test negotiate::tests::mock_prompt_is_symbolic_and_the_recorded_reply_is_obeyed ... ok
test negotiate::tests::model_formatting_and_long_lines_are_repaired_without_changing_roles ... ok
test negotiate::tests::natural_proceed_heading_and_holding_lines_keep_their_actual_roles ... ok
test negotiate::tests::one_retry_recovers_parse_and_transport_errors_with_remaining_budget ... ok
test negotiate::tests::parse_diagnostics_are_redacted_and_bounded ... ok
test negotiate::tests::prompt_contains_no_canned_example_sentence ... ok
test negotiate::tests::recorded_gemini_body_parses_to_a_model_decision ... ok
test negotiate::tests::speech_has_eight_words_at_most_and_no_numbers_units_or_telemetry ... ok
test negotiate::tests::spoken_yield_and_go_roles_cannot_be_reversed ... ok
test negotiate::tests::trimming_preserves_a_role_after_a_long_preamble ... ok
test network::fleet_release_tests::denial_or_revocation_releases_every_held_vehicle_within_one_tick ... ok
test network::junction::tests::advance_warning_reacts_then_holds_cross_traffic_without_a_speed_command ... ok
test network::junction::tests::local_hearing_hold_budget_and_late_braking_decline ... ok
test network::junction::tests::occupied_crossing_is_never_revoked ... ok
test network::junction::tests::opted_in_receiver_still_declines_self_expired_and_physics ... ok
test network::junction::tests::topology_blocks_forced_return_but_accepts_real_hampshire_bypass ... ok
test network::record_host::tests::road_obstacle_spans_cover_every_parallel_but_lane_obstacles_do_not ... ok
test network::record_host::v2_cost_tests::known_remaining_blockage_changes_the_old_route_cost_without_changing_make_way ... ok
test network::record_host::v2_count_tests::cached_counts_equal_the_original_per_candidate_counts ... ok
test network::tests::ease_off_releases_when_the_ambulance_passes_the_conflict ... ok
test network::tests::fallback_log_prints_the_reason_token ... ok
test network::tests::gap_shift_moves_the_car_without_the_pullover_brake ... ok
test network::tests::town_has_junctions_and_trips ... ok
test osm::tests::area_centroid_ignores_vertex_density_and_ring_direction ... ok
test prefs::tests::fair_sentences_are_balanced ... ok
test prefs::tests::priority_sentences_favor_one_approach ... ok
test prefs::tests::structured_line_wins_over_fair_english ... ok
test rush_hour::live_batch_tests::batch_identities_and_reversed_roles_cannot_cross_assign_priority ... ok
test rush_hour::live_batch_tests::contemporaneous_conflicts_are_batched_and_only_rejected_items_retry ... ok
test rush_hour::live_batch_tests::expired_global_budget_still_grants_medical_fallback_and_blocks_injection ... ok
test rush_hour::live_batch_tests::slow_provider_cannot_exceed_shared_run_budget ... ok
test slot::tests::a_car_ahead_of_the_open_lane_is_not_shifted_into_it ... ok
test slot::tests::a_car_not_yet_on_the_stretch_is_kept_off ... ok
test slot::tests::a_follower_eases_off_rather_than_closing_on_a_waiting_ambulance ... ok
test slot::tests::a_follower_who_would_fill_the_hole_is_not_gap_shifted ... ok
test slot::tests::a_queue_spilled_upstream_is_the_open_lane_and_is_not_asked ... ok
test slot::tests::gap_shift_is_preferred_over_ease_off_when_both_would_clear ... ok
test slot::tests::only_a_car_inside_the_slot_is_asked_and_the_gap_wins ... ok
test slot::tests::the_blocked_lane_puts_the_slot_on_the_open_lane ... ok
test world::tests::ascii_names_the_open_road_the_wreck_and_the_jam ... ok
test world::tests::ascii_reads_as_a_ramp_merge ... ok
test world::tests::ascii_shows_the_car_inside_the_gate ... ok
test world::tests::dumb_equal_holds_the_gore ... ok
test world::tests::fog_hides_the_tail_and_shows_the_other_mouth ... ok
test world::tests::queues_are_meters_and_side_by_side_do_not_overlap ... ok
test world::tests::selfish_fronts_overlap_in_the_gore ... ok
test world::tests::surge_keeps_both_approaches_nonempty ... ok
test world::tests::zipper_respects_accel_gaps_and_gets_home ... ok
test demo::tests::fast_provider_phases_stay_inside_their_budgets ... ok

test result: ok. 81 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 28.97s

     Running unittests src/main.rs (target/phase15c/release/deps/malleable-209e40989e1b4330)

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

     Running tests/phase15_v2.rs (target/phase15c/release/deps/phase15_v2-f504529ec6da5805)

running 2 tests
test granted_record_priority_has_a_merged_edit_and_due_public_deliveries ... ok
test near_and_labour_harness_validity_before_registration_not_outcome_bars ... ok

test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 11.42s

     Running tests/phase15c.rs (target/phase15c/release/deps/phase15c-839c2853acab347f)

running 3 tests
test observer_starts_on_actual_entry_after_real_source_waiting ... ok
test all_five_candidates_keep_legal_turns_and_hospital_destination ... ok
test origin_change_keeps_all_ids_departures_requests_and_other_routes has been running for over 60 seconds
test origin_change_keeps_all_ids_departures_requests_and_other_routes ... ok

test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 99.37s

     Running tests/road_record.rs (target/phase15c/release/deps/road_record-6e2688d2a5c18b1e)

running 6 tests
test blocked_road_covers_parallel_clones_but_legacy_lane_validation_stays_strict ... ok
test edit_needs_a_later_distinct_sensor_witness_and_two_negatives_reject_spoof ... ok
test model_reply_cannot_inject_motion_controls ... ok
test route_decision_source_has_no_ground_truth_or_reachability_guard ... ok
test spoof_is_rejected_without_delivery_knowledge_or_reroutes ... ok
test no_car_changes_route_before_its_own_sighting_or_edit_delivery ... ok

test result: ok. 6 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.20s

   Doc-tests malleable

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
```

### Final exact-code targeted run

```text
   Compiling malleable v0.1.0 (/tmp/malleable-phase15c-build)
    Finished `release` profile [optimized] target(s) in 9.76s
     Running tests/phase15c.rs (target/phase15c/release/deps/phase15c-839c2853acab347f)

running 3 tests
test observer_starts_on_actual_entry_after_real_source_waiting ... ok
test all_five_candidates_keep_legal_turns_and_hospital_destination ... ok
test origin_change_keeps_all_ids_departures_requests_and_other_routes has been running for over 60 seconds
test origin_change_keeps_all_ids_departures_requests_and_other_routes ... ok

test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 79.46s
```
