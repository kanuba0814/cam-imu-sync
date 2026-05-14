# Evidence: final commands must match replay preflight

## Change validated

`generate_final_stability_artifacts.py` now verifies every run command against aggregate preflight and bag metadata before writing final artifacts. The command must include the same bag path, selected topics, settings file, QoS override, rate, and play delay recorded by replay preflight.

This is a final-artifact provenance guard only. It does not change ROS2 replay behavior, parser thresholds, launch behavior, or SLAM configuration.

## Local validation

Syntax and whitespace checks:

```bash
python3 -m py_compile extra_ws/src/ORB_SLAM3_ROS2/tools/generate_final_stability_artifacts.py
git -C extra_ws/src/ORB_SLAM3_ROS2 diff --check -- tools/generate_final_stability_artifacts.py
```

Accepted synthetic aggregate with a full runner-style ROS2 wrapper command:

```text
wrote final artifacts to /tmp/orb_final_command_tests/out_valid
```

Rejected synthetic aggregate whose run command omitted the replay settings file:

```text
error: run 1 command is not the guarded ROS2 wrapper replay path; missing: settings_file:=/home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml
```

Rejected synthetic aggregate whose run command omitted the QoS override:

```text
error: run 2 command is not the guarded ROS2 wrapper replay path; missing: qos_profile_overrides_path:=/home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2/config/bag_qos_override.yaml
```

Rejected synthetic aggregate whose run command used a different bag path:

```text
error: run 3 command is not the guarded ROS2 wrapper replay path; missing: bag_path:=/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136
```

Final artifacts therefore cannot be generated from a command list that does not directly match the guarded fixed-bag ROS2 wrapper replay.
