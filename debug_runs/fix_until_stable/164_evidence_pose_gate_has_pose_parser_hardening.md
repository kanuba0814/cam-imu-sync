# Evidence: Runtime Pose Gate Has-Pose Parser Hardening

## Change

- `parse_runtime_orb_log.py` now counts `publish_pose=1` as invalid when
  `[orb_pose_gate]` reports missing/false `has_pose`.
- `selftest_final_stability_gates.py` now includes a synthetic
  `has_pose=0 publish_pose=1` case.

## Verification

Run from `/home/gxxl/slam_ws_v2`:

```bash
python3 -m py_compile \
  extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py \
  extra_ws/src/ORB_SLAM3_ROS2/tools/selftest_final_stability_gates.py \
  extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py \
  extra_ws/src/ORB_SLAM3_ROS2/tools/generate_final_stability_artifacts.py
```

Result: passed.

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/selftest_final_stability_gates.py
```

Result:

```text
preflight: ignoring non-replay bag topics: /image_raw, /imu/data_raw, /imu/raw_hw
final stability gate selftest passed
```

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py \
  extra_ws/debug_runs/fix_until_stable/29_postinit_inliers5_wrapper_pose_gate_full_window_run01.log |
  rg '"(invalid_pose_publish_count|stability_pass|reset_count_after_init|ok_ratio_after_init)"'
```

Result:

```text
  "invalid_pose_publish_count": 0,
  "ok_ratio_after_init": 0.9143192488262911,
  "reset_count_after_init": 0,
  "stability_pass": true,
```

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py \
  --runs 1 \
  --label 30_postinit_inliers0_wrapper_pose_gate_full_window \
  --timeout-sec 210 \
  --min-pose-publish-inliers 15 \
  --min-pose-publish-tracked-mappoints 15 \
  --preflight-only
```

Result:

```text
preflight: ignoring non-replay bag topics: /image_raw, /imu/data_raw, /imu/raw_hw
preflight passed for /home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136
replay_topics: /sync/image_raw,/sync/imu
start_offset_sec: 0.0
```

## Conclusion

This is final-evidence hardening only. It does not change runtime ORB behavior,
but it closes another path where a final replay aggregate could otherwise hide
a stale or missing-pose publication bug.
