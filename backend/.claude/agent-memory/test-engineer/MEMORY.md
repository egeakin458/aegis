# Test Engineer Memory Index

## Schema & Fixture Notes
- [conftest_and_fixtures.md](conftest_and_fixtures.md) — existing conftest.py fixtures: valid_customer_config, valid_finalized_config, sample_clarification_question, sample_clarification_round, sample_run_id, captured_events, mock_anthropic, make_mock_response

## Pipeline & Agent Patterns
- [pipeline_runner_patterns.md](pipeline_runner_patterns.md) — PipelineRunner state machine details, cycle caps, context passing rules, how to mock agents for tests

## Phase 2 Tests
- test_database.py — covers init_db/get_connection/close_db, save_run/get_run/update_run roundtrips, save_event/get_events, ordering, isolation across runs
- test_output_storage.py — covers directory creation, file content, manifest.json fields, nested paths, unsafe path rejection (/ prefix and ..)
