# Evidence: Final Gate Wrapper Hardening

## Scope

This evidence documents final-gate hardening performed while Docker wrapper
replay validation was blocked by the approval retry window. These changes do not
alter ORB-SLAM3 tracking behavior or H30 tuning. They only make the replay
harness and final artifact generator reject incomplete final evidence.

## Findings

1. `image_to_last_imu_ms.p50` was present in final-report metrics but was not a
   hard final gate. The goal requires `p50/p95` to have no abnormal jump.
2. The H30 post-init inlier relaxation depends on the ROS2 wrapper pose gate,
   but the replay harness did not explicitly pass
   `min_pose_publish_inliers:=15` and
   `min_pose_publish_tracked_mappoints:=15`.
3. Preflight recorded selected image topic stats, but did not record selected
   IMU topic stats. Final evidence should reject a replay aggregate that lacks
   recorded IMU topic evidence.

## Commits

- `20e2fff test: gate H30 IMU window median timing`
  - Adds `image_to_last_imu_ms.p50 <= 20ms` to parser stability pass and final
    artifact gates.
  - Adds a final gate selftest negative case for p50 jump.
- `80567ea test: require explicit H30 wrapper pose gates`
  - Adds explicit replay launch args:
    `min_pose_publish_inliers:=15` and
    `min_pose_publish_tracked_mappoints:=15`.
  - Makes the final generator reject aggregates that omit or alter those args.
- `be3fd27 test: require H30 replay IMU topic evidence`
  - Adds `imu_topic_stats` to replay preflight metadata.
  - Makes the final generator reject missing, empty, or non-spanning IMU topic
    evidence.
- `fc7d5b0 test: report H30 replay topic evidence`
  - Adds selected image/IMU topic counts and fps spans to the final stability
    report.
  - Extends the final gate selftest to require those report fields.
- `aa165dc test: report H30 backlog gate in final metrics`
  - Adds `controlled_backlog_pass` to the final replay metrics table as
    `Backlog pass`.
  - Extends the final gate selftest to require that report column.
- `1f33d11 test: cover H30 final stability metric failures`
  - Adds negative final-gate selftests for OK ratio, lost streak, last-60 reset,
    keyframes, map points, inliers, stale image age, queue growth, and backlog
    failure.

## Validation

Commands run from `/home/gxxl/slam_ws_v2`:

```bash
python3 -m py_compile \
  extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py \
  extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py \
  extra_ws/src/ORB_SLAM3_ROS2/tools/generate_final_stability_artifacts.py \
  extra_ws/src/ORB_SLAM3_ROS2/tools/selftest_final_stability_gates.py
```

Result: passed.

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py \
  --runs 1 \
  --label 30_postinit_inliers0_wrapper_pose_gate_full_window \
  --timeout-sec 210 \
  --preflight-only
```

Result:

```text
preflight: ignoring non-replay bag topics: /image_raw, /imu/data_raw, /imu/raw_hw
preflight passed for /home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136
replay_topics: /sync/image_raw,/sync/imu
start_offset_sec: 0.0
```

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/selftest_final_stability_gates.py
```

Result:

```text
preflight: ignoring non-replay bag topics: /image_raw, /imu/data_raw, /imu/raw_hw
final stability gate selftest passed
```

## Remaining Gap

No real ROS2 wrapper aggregate exists yet for:

```text
extra_ws/debug_runs/fix_until_stable/30_postinit_inliers0_wrapper_pose_gate_full_window.json
```

The goal is not complete until the containerized wrapper build succeeds and the
fixed H30 sync-only bag passes 3 full `orb_slam3_ros2` replay runs under these
gates.
