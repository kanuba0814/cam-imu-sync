# Evidence: fixed-bag FPS and settings FPS in replay preflight

## Change under validation

- `extra_ws/src/ORB_SLAM3_ROS2` commit: `f9c06dc debug: record bag and settings FPS in replay preflight`
- File changed:
  - `tools/run_stability_replay.py`

## Purpose

This is a replay-harness evidence change only. It does not change ORB-SLAM3 behavior, wrapper runtime behavior, launch defaults, H30 YAML, parser gates, or replay commands.

The runner now records:

- selected image topic message count
- selected image topic first and last timestamp
- selected image topic span FPS
- selected settings file `Camera.fps`

These values are included in aggregate JSON and Markdown.

## Local validation

Syntax check:

```bash
python3 -m py_compile extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py
```

Default fixed-bag preflight still passes:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --preflight-only --bag-path /home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136
```

Re-rendered an aggregate from the existing `14_revert_preinit_inliers_35` replay logs under `/tmp/orb_aggregate_fps_preflight_test`.

Aggregate JSON now includes:

```json
{
  "pass_count": 0,
  "all_passed": false,
  "image_topic_stats": {
    "topic": "/sync/image_raw",
    "count": 1668,
    "first_ns": 1778574427043606216,
    "last_ns": 1778574606787716374,
    "fps_span": 9.274295544564222
  },
  "settings_camera_fps": 30.0
}
```

Aggregate Markdown now includes:

```text
- image_topic_fps_span: `9.274295544564222`
- settings_camera_fps: `30.0`
- pass_count: `0`
- all_passed: `False`
```

## Interpretation

The replay aggregate now directly exposes the mismatch motivating the next single behavior change: the fixed bag image cadence is about 9.27 Hz while the current H30 settings file still declares `Camera.fps: 30`.

The next behavior change remains:

```yaml
Camera.fps: 9
```

That change still waits for `autoware_env_v2_host` build and three-run ROS2 wrapper replay.
