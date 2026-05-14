# Evidence: full-bag replay timeout guard

## Change under validation

- `extra_ws/src/ORB_SLAM3_ROS2` commit: `a148096 test: guard replay timeout against full bag duration`
- File changed:
  - `tools/run_stability_replay.py`

## Purpose

This is a replay-harness safety change only. It does not change ORB-SLAM3 behavior, wrapper runtime behavior, launch defaults, H30 YAML, parser stability gates, or replay metrics.

The runner now:

- computes full bag time span from rosbag2 sqlite timestamps
- exposes `bag_time_span_sec`, `replay_duration_sec`, `required_timeout_sec`, `timeout_sec`, `rate`, and `play_delay_sec` in preflight metadata
- passes `play_delay:=...` explicitly to `h30_bag_replay.launch.py`
- rejects `--timeout-sec` values that are too short for the requested replay duration, rate, and play delay

## Local validation

Syntax check:

```bash
python3 -m py_compile extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py
```

Low-timeout preflight:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --preflight-only --bag-path /home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136 --timeout-sec 180
```

Result:

```text
run_stability_replay.py: error: preflight failed: timeout too low for replay: timeout_sec=180.000, required_timeout_sec>=196.793
```

Sufficient-timeout preflight:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --preflight-only --bag-path /home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136 --timeout-sec 210
```

Result:

```text
preflight passed for /home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136
```

Re-rendered an aggregate from the existing `14_revert_preinit_inliers_35` replay logs under `/tmp/orb_aggregate_timeout_preflight_test`.

Aggregate JSON contains:

```json
{
  "pass_count": 0,
  "all_passed": false,
  "bag_time_span_sec": 179.792912779,
  "required_timeout_sec": 196.792912779,
  "timeout_sec": 210.0,
  "play_delay_sec": 2.0,
  "rate": 1.0
}
```

Aggregate Markdown includes:

```text
- bag_time_span_sec: `179.792912779`
- required_timeout_sec: `196.792912779`
- timeout_sec: `210.0`
- pass_count: `0`
- all_passed: `False`
```

## Interpretation

The previous `--timeout-sec 180` command was too short for a full fixed-bag replay with the launch delay and shutdown margin. The next real ROS2 wrapper replay should use at least `--timeout-sec 210`.

The next behavior change remains:

```yaml
Camera.fps: 9
```

That change still waits for `autoware_env_v2_host` build and three-run ROS2 wrapper replay.
