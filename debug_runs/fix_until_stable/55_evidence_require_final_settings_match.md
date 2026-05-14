# Evidence: final artifacts require settings path and Camera.fps to match replay

## Change validated

`generate_final_stability_artifacts.py` now rejects final artifact generation unless the copied `--settings-file` is the same path recorded in replay preflight and its current `Camera.fps` matches preflight `settings_camera_fps`.

This is a final-artifact provenance guard only. It does not change ROS2 replay behavior, parser thresholds, launch behavior, or SLAM configuration.

## Local validation

Syntax and whitespace checks:

```bash
python3 -m py_compile extra_ws/src/ORB_SLAM3_ROS2/tools/generate_final_stability_artifacts.py
git -C extra_ws/src/ORB_SLAM3_ROS2 diff --check -- tools/generate_final_stability_artifacts.py
```

Rejected aggregate whose preflight says `settings_camera_fps=9.0` while the current H30 YAML is still `30.0`:

```text
error: settings Camera.fps differs from replay preflight: current=30.0, preflight=9.0
```

Rejected aggregate whose preflight `settings_file` does not match selected `--settings-file`:

```text
error: settings file does not match replay preflight: selected=/home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml, preflight=/tmp/not_the_replayed_settings.yaml
```

Accepted synthetic aggregate matching the current source H30 YAML and `Camera.fps=30.0`:

```text
wrote final artifacts to /tmp/orb_final_settings_tests/out_current
```

After the planned `Camera.fps: 9` behavior change and ROS2 wrapper replay, final artifacts will therefore fail unless `best_config.yaml` is copied from the exact replayed settings file and that file still contains the replayed FPS value.
