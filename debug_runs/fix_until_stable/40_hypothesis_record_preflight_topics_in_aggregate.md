# Hypothesis: record replay preflight topics in aggregate evidence

## Observation

`run_stability_replay.py` now rejects forbidden selected topics before launch, but the aggregate JSON/Markdown does not yet record the preflight evidence. A reviewer can see the replay command uses `/sync/image_raw` and `/sync/imu`, but the summary artifact itself does not list:

- bag topics discovered during preflight
- selected replay topics
- ignored raw topics such as `/image_raw`
- settings and QoS override files checked before launch

The goal requires the fixed sync-only replay contract to be explicit and verifiable, especially because the fixed bag also contains `/image_raw`.

## Minimal change

Change only replay-harness evidence output:

- make `preflight_replay()` return structured metadata
- include that metadata in aggregate JSON
- include selected topics and ignored bag topics in aggregate Markdown
- keep `--preflight-only` behavior
- keep existing replay command, parser gates, H30 YAML, ORB code, and launch defaults unchanged

## Expected validation

Local validation should show:

- default fixed-bag preflight still passes
- aggregate JSON contains `preflight.selected_topics`, `preflight.bag_topics`, and `preflight.ignored_bag_topics`
- aggregate Markdown shows selected topics `/sync/image_raw`, `/sync/imu`
- known failed `14_revert_preinit_inliers_35` summaries remain `pass_count=0` and `all_passed=false`

The next behavioral step remains `Camera.fps: 9` when containerized replay is available.
