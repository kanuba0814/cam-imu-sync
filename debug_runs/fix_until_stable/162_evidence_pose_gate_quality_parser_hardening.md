# Evidence: Runtime Pose Gate Quality Parser Hardening

## Change

- `parse_runtime_orb_log.py` now counts a published pose as invalid when the
  `[orb_pose_gate]` line reports:
  - a non-OK tracking state
  - a non-`ok` gate reason
  - missing or non-finite pose quality fields
  - `num_inliers < 15`
  - `num_tracked_mappoints < 15`
- `selftest_final_stability_gates.py` now includes synthetic pose-gate log cases
  for OK quality publishes, low-inlier publishes, low-map-point publishes,
  RECENTLY_LOST publishes, blocked low-quality poses, and missing-quality
  publishes.

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

This is harness-only hardening. It does not change ORB-SLAM3 or wrapper runtime
behavior, but it prevents the final evidence parser from accepting a low-quality
ROS2 pose publish as valid.

## Actual Log Spot Check

After the parser hardening commit, the previous experiment 29 logs were
reparsed with the new code:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py \
  extra_ws/debug_runs/fix_until_stable/29_postinit_inliers5_wrapper_pose_gate_full_window_run01.log
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py \
  extra_ws/debug_runs/fix_until_stable/29_postinit_inliers5_wrapper_pose_gate_full_window_run02.log
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py \
  extra_ws/debug_runs/fix_until_stable/29_postinit_inliers5_wrapper_pose_gate_full_window_run03.log
```

Result summary:

| Run | Stability pass | Invalid pose publishes | Reset after init | OK ratio |
| ---: | --- | ---: | ---: | ---: |
| 1 | `true` | `0` | `0` | `0.9143192488262911` |
| 2 | `false` | `0` | `1` | `0.600451467268623` |
| 3 | `false` | `0` | `0` | `0.8645598194130926` |

The hardened parser does not change the known experiment 29 diagnosis: wrapper
pose publication was not the remaining failure cause; the remaining failures
were stability metrics such as reset-after-init and OK ratio.
