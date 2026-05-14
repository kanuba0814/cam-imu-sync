# Hypothesis: final artifacts must copy the replayed settings file

## Observation

The final artifact generator copies `--settings-file` to `best_config.yaml`. Before this change, it accepted a passing aggregate even if the selected `--settings-file` did not match aggregate preflight `settings_file`, or if the current file's `Camera.fps` no longer matched `settings_camera_fps` recorded during replay.

That can create false final evidence: a ROS2 wrapper replay could pass with one settings file while `best_config.yaml` is copied from another file or a later-edited file.

## Minimal change

Only strengthen `generate_final_stability_artifacts.py`:

- parse `Camera.fps` from `--settings-file`
- require `--settings-file` to resolve to aggregate preflight `settings_file`
- require current `Camera.fps` to equal aggregate preflight `settings_camera_fps`

Do not change replay, parser gates, launch behavior, or SLAM configuration.

## Expected validation signal

Synthetic final aggregates should be rejected when the copied settings path or `Camera.fps` differs from replay preflight. A synthetic aggregate that matches the current settings file and FPS should still generate final artifacts.
