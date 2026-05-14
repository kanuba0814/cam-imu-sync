# Hypothesis: record replay settings path in aggregate Markdown

## Observation

The replay aggregate JSON already records preflight metadata such as:

- selected sync-only topics
- ignored non-replay topics
- `/sync/image_raw` bag FPS
- `Camera.fps` from the settings file
- replay timeout requirements

The aggregate Markdown did not show the exact `settings_file`, QoS override path, replay duration, rate, or play delay. That makes the next ROS2 wrapper replay harder to audit by eye, especially because direct `ros2 launch` defaults use the installed package share config while `run_stability_replay.py` explicitly passes the source-tree H30 YAML.

## Minimal change

Only extend `tools/run_stability_replay.py` aggregate Markdown output to include:

- `settings_file`
- `qos_profile_overrides_path`
- `replay_duration_sec`
- `rate`
- `play_delay_sec`

Do not change launch behavior, replay timing, parser gates, or SLAM configuration.

## Expected validation signal

A local aggregate-render test should show the source H30 YAML path and timing fields in the Markdown header, while preflight still reports the fixed bag `/sync/image_raw` rate and ignores non-replay `/image_raw` topics.
