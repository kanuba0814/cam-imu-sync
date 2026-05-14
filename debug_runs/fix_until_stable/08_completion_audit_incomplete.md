# 08 Completion Audit Incomplete

## Objective Restatement

Use `goal/orbDebugGoalV2.md` to continue beyond the old `decision.md` diagnosis. The work is only complete when the fixed sync-only bag has stable ORB-SLAM3 IMU-mode mapping/localization across three offline replays. If the fixed bag still resets, enters `RECENTLY_LOST`, lacks a stable map, or publishes untrustworthy pose, the loop must continue with one minimal explainable code/config change at a time, each source change committed and followed by build plus three-replay validation.

## Prompt-To-Artifact Checklist

| Requirement | Current Evidence | Status |
| --- | --- | --- |
| Use `goal/orbDebugGoalV2.md` as guide | `00_git_status_before.md`, `01_existing_evidence_review.md` quote and follow V2 gates. | partial |
| Do not stop at `decision.md` | `01_existing_evidence_review.md` states old conclusion 8 is insufficient; new wrapper/core/replay commits exist. | done |
| Main bag read from `bags/LATEST_BAG.txt` | `bags/LATEST_BAG.txt` now points to `/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136`; `05_latest_bag_pointer.md` records it. | done |
| Only sync-only topics, no `/image_raw` diagnostics | `h30_bag_replay.launch.py` defaults to `/sync/image_raw` and `/sync/imu`; QoS override only includes `/sync/image_raw`, `/sync/imu`, `/sync/imu_batch`. | done |
| Do not start real camera/IMU/cam_imu_sync | `h30_bag_replay.launch.py` starts only ORB wrapper plus optional `ros2 bag play`; no hardware driver nodes. | done |
| Every source change committed | `libs/ORB_SLAM3`: `a6b6c74`; `ORB_SLAM3_ROS2`: `e626edb`, `0deab31`, `580d492`, `4b7ba06`, `b2de774`, `72bdb1f`. | done |
| Prior evidence reviewed before new tuning | `01_existing_evidence_review.md`. | done |
| Add wrapper queue/timing/IMU window/state/pose/visual logs | `e626edb` implements `[orb_queue]`, `[orb_timing]`, `[orb_imu_window]`, `[orb_state_transition]`, `[orb_pose_gate]`, `[orb_visual_quality]`. | source done, runtime unverified |
| Add safety params with defaults | `imu_mono_realsense.cpp` declares `enable_video_recording=false`, `publish_pose_only_when_tracking_ok=true`, `max_image_queue_size=2`, `max_imu_queue_size=500`, `drop_stale_images=true`, `max_image_age_ms=200`, `debug_runtime_metrics=true`. | source done, runtime unverified |
| Prevent invalid tracking pose publishing | `timer_callback()` gates publish on `has_pose` and OK/OK_KLT when `publish_pose_only_when_tracking_ok=true`; `[orb_pose_gate]` logs decisions. | source done, runtime unverified |
| Bound image and IMU queues | `image_callback()` and `imu_callback()` drop oldest messages beyond configured queue sizes and increment drop counters. | source done, runtime unverified |
| Disable video recording by default | `enable_video_recording=false`; `video_writer_.write()` is guarded by the parameter. | source done, runtime unverified |
| Add repeatable replay launch and tools | `h30_bag_replay.launch.py`, `parse_runtime_orb_log.py`, `run_stability_replay.py`; commits `0deab31`, `b2de774`, `72bdb1f`. | done |
| Build ORB core in container | Not run. Docker API blocked by sandbox/quota. Host `./build.sh` failed due host-only dependency/toolchain issues. | missing |
| Build ROS package in `autoware_env_v2_host` | Not run. Docker API blocked by sandbox/quota. | missing |
| Replay fixed bag 3 times after wrapper fixes | Not run. Docker API blocked by sandbox/quota. | missing |
| Generate `02_replay_baseline_after_wrapper_fixes.md/csv/json` from real replays | Not run. | missing |
| If still unstable, make one evidence-backed next fix | Awaiting first post-wrapper replay evidence. | missing |
| Final `best_config.yaml`, `decision.md`, `stability_report.md` | Not generated; stability not proven. | missing |
| Completion gate: three passing replays | Not satisfied. Old 1200 log still fails with `RECENTLY_LOST`, `reset_count_after_init=27`, `final_keyframes=2`. | missing |

## Current Verified Non-Completion Evidence

The old best diagnostic run still fails:

- `stability_pass: false`
- `ok_ratio_after_init: 0.2658349328214971`
- `reset_count_after_init: 27`
- `reset_delta_last_60_sec: 17`
- `tracking_state: RECENTLY_LOST`
- `final_keyframes: 2`

The new verifier intentionally rejects old logs that lack V2 runtime tags.

## Blocker

The next required command sequence must run inside `autoware_env_v2_host`, but Docker access is currently unavailable from the sandbox:

```text
permission denied while trying to connect to the docker API at unix:///var/run/docker.sock
```

The escalation request was rejected by the platform quota guard. Until container access is restored, build and replay evidence cannot be produced.

## Next Concrete Step Once Unblocked

```bash
docker exec -it autoware_env_v2_host bash
cd /home/gxxl/slam_ws_v2/libs/ORB_SLAM3 && ./build.sh
cd /home/gxxl/slam_ws_v2/extra_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
export ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3
colcon build --packages-select orb_slam3_ros2 --symlink-install
python3 src/ORB_SLAM3_ROS2/tools/run_stability_replay.py \
  --runs 3 \
  --latest-file /home/gxxl/slam_ws_v2/bags/LATEST_BAG.txt \
  --settings-file /home/gxxl/slam_ws_v2/extra_ws/debug_runs/latest/config_variants/rmoncam_h30_nfeatures_1200.yaml \
  --label 02_replay_baseline_after_wrapper_fixes
```

Do not mark the goal complete until those three replays pass every stability gate.
