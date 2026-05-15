# Completion Audit: Current Head Waiting For ROS2 Wrapper Replay

## Objective Restatement

The goal is to fix and validate `ORB_SLAM3_ROS2 + ORB_SLAM3` on the fixed H30
sync-only ROS2 bag. Completion requires a real build and three full ROS2 wrapper
bag replays that satisfy the stability gates. Preflight checks, selftests, and
diagnostic explanations are not sufficient completion evidence.

## Current State

- Checked at: `2026-05-15 13:01:57 JST`
- ORB_SLAM3_ROS2 HEAD: `b9f5b58`
- extra_ws HEAD: `6b0460c`
- ORB_SLAM3 HEAD: `a5ea5b1`
- Fixed bag:
  `/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136`
- Expected aggregate:
  `extra_ws/debug_runs/fix_until_stable/30_postinit_inliers0_wrapper_pose_gate_full_window.json`

## Prompt-To-Artifact Checklist

| Requirement | Current Evidence | Status |
| --- | --- | --- |
| Use the fixed latest H30 sync-only bag | Preflight resolves both latest-bag pointers to `/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136`. | Satisfied for preflight |
| Do not use `/image_raw` or raw IMU topics | Preflight ignores `/image_raw`, `/imu/data_raw`, and `/imu/raw_hw`; replay topics are `/sync/image_raw,/sync/imu`. | Satisfied for preflight |
| Do not launch real camera, IMU, or live cam_imu_sync | `h30_bag_replay.launch.py` launches the ORB wrapper and optional bag play only. | Satisfied by harness |
| Validate ROS2 wrapper path, not standalone ORB | Replay command is `ros2 launch orb_slam3_ros2 h30_bag_replay.launch.py`. | Satisfied by harness |
| Wrapper pose trust gates are explicit | Replay command includes `publish_pose_only_when_tracking_ok:=true`, `min_pose_publish_inliers:=15`, and `min_pose_publish_tracked_mappoints:=15`. | Satisfied by harness |
| Final parser rejects fake or low-quality pose publishes | `9bb9251` rejects low-quality publishes; `b9f5b58` rejects missing/false `has_pose` publishes. | Satisfied by parser gate |
| Final generator rejects incomplete/failing replay evidence | Generator requires latest bag, full-bag start, three passing runs, stable metrics, timeout false, matching wrapper commands, and final artifact metadata. | Satisfied by generator gate |
| Containerized build before replay | No current post-`b9f5b58` `autoware_env_v2_host` build has run. | Missing |
| Consecutive three full wrapper replays | `30_postinit_inliers0_wrapper_pose_gate_full_window.json` does not exist. | Missing |
| Final stability artifacts | `final_stability_report.md`, `best_config.yaml`, `decision.md`, `stability_report.md`, `final_patch_summary.md`, and `final_commands.md` are not present. | Missing |
| Completion declaration | Cannot call `update_goal complete` without the missing build, replay, and final artifacts. | Missing |

## Completion Decision

The goal is not complete. The next concrete action is still the containerized
build and three-run ROS2 wrapper replay recorded in:

```text
extra_ws/debug_runs/fix_until_stable/157_next_container_replay_after_gate_hardening.md
```

Do not treat preflight, selftest, parser gate hardening, or this audit as a
substitute for the required replay aggregate.
