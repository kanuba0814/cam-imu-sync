# Evidence: replay settings path appears in aggregate Markdown

## Change validated

`tools/run_stability_replay.py` now prints these preflight fields in aggregate Markdown:

- `settings_file`
- `qos_profile_overrides_path`
- `replay_duration_sec`
- `rate`
- `play_delay_sec`

This is evidence-only output. It does not change the ROS2 wrapper launch command or any SLAM parameter.

## Local validation

Syntax check:

```bash
python3 -m py_compile extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py
```

Aggregate-render smoke test:

```bash
python3 -c 'import argparse, shutil, sys; from pathlib import Path; sys.path.insert(0, "extra_ws/src/ORB_SLAM3_ROS2/tools"); import run_stability_replay as r; out=Path("/tmp/orb_aggregate_preflight_fields"); shutil.rmtree(out, ignore_errors=True); args=argparse.Namespace(image_topic="/sync/image_raw", imu_topic="/sync/imu", settings_file=str(r.PACKAGE_ROOT / "config" / "Monocular-Inertial" / "rmoncam_h30.yaml"), qos_profile_overrides_path=str(r.PACKAGE_ROOT / "config" / "bag_qos_override.yaml"), rate="1.0", duration="0.0", play_delay="2.0", timeout_sec=210.0); bag=r.read_latest_bag(None, None); preflight=r.preflight_replay(args, bag); r.write_aggregate("preflight_fields", bag, [], out, preflight); print(out / "preflight_fields.md")'
```

Generated Markdown header excerpt:

```text
- selected_image_topic: `/sync/image_raw`
- selected_imu_topic: `/sync/imu`
- ignored_bag_topics: `/image_raw, /imu/data_raw, /imu/raw_hw`
- image_topic_fps_span: `9.274295544564222`
- settings_camera_fps: `30.0`
- settings_file: `/home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml`
- qos_profile_overrides_path: `/home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2/config/bag_qos_override.yaml`
- bag_time_span_sec: `179.792912779`
- replay_duration_sec: `179.792912779`
- required_timeout_sec: `196.792912779`
- timeout_sec: `210.0`
- rate: `1.0`
- play_delay_sec: `2.0`
```

Current source and installed H30 YAML files are identical before the next behavior change:

```text
Camera.fps: 30
LocalMapping.ResetOnSmallMotionBeforeInertialBA2: 0
IMU.Frequency: 100.0
ORBextractor.nFeatures: 1200
```

The next real ROS2 wrapper replay should therefore expose `settings_camera_fps: 9.0` and the same source `settings_file` after the planned one-line H30 YAML change.
