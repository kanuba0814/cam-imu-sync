# Next: Container Replay After Final Gate Hardening

## Current Candidate

- ORB_SLAM3_ROS2 HEAD: `07f23ff test: include H30 config snapshot in final report`
- H30 behavior candidate: `f93a5c7 fix: allow H30 post-init visual dropout survival`
- Replay harness hardening:
  `run_stability_replay.py` launches each ROS2 wrapper replay in its own
  process group and kills the full group on timeout before the next run starts.
  `generate_final_stability_artifacts.py` requires every accepted run to record
  `timed_out: false` and shows each run's pass/timeout values in the final
  report table.
  It also includes a key H30 settings snapshot in the final report so the final
  config is visible without opening `best_config.yaml`.
- Config under test:
  - `Tracking.MinInliersImuMonoPostInit: 0`
  - wrapper pose gate: `min_pose_publish_inliers:=15`
  - wrapper pose gate: `min_pose_publish_tracked_mappoints:=15`
- Fixed bag:
  - `/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136`
- Replay topics:
  - `/sync/image_raw`
  - `/sync/imu`

## Hypothesis

The H30 replay can survive post-init zero-inlier visual dropout internally while
the ROS2 wrapper blocks external odom/tf publication below the 15/15 pose
quality gate. The updated final gates must reject any evidence that is not a
full latest-bag ROS2 wrapper replay with selected image and IMU topic evidence.

## Blocker

Docker escalation is still blocked by the approval retry window observed in the
thread. Do not run host ROS as a substitute; the active ROS 2 environment is
inside `autoware_env_v2_host`.

## Build Command

Run this inside the container after escalation is available:

```bash
docker exec -w /home/gxxl/slam_ws_v2/extra_ws autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 colcon build --packages-select orb_slam3_ros2 --cmake-args -DORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3'
```

## Three-Run Wrapper Replay Command

```bash
docker exec -w /home/gxxl/slam_ws_v2 autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 30_postinit_inliers0_wrapper_pose_gate_full_window --timeout-sec 210 --min-pose-publish-inliers 15 --min-pose-publish-tracked-mappoints 15'
```

Required aggregate:

```text
extra_ws/debug_runs/fix_until_stable/30_postinit_inliers0_wrapper_pose_gate_full_window.json
```

## Acceptance Gate

Do not accept the result unless the aggregate shows:

- `run_count=3`
- `pass_count=3`
- `all_passed=true`
- every run used `ros2 launch orb_slam3_ros2 h30_bag_replay.launch.py`
- every run used `/sync/image_raw` and `/sync/imu`
- every run used `min_pose_publish_inliers:=15`
- every run used `min_pose_publish_tracked_mappoints:=15`
- preflight recorded QoS override topics exactly as `/sync/image_raw`, `/sync/imu`, `/sync/imu_batch`
- `invalid_pose_publish_count=0`
- `reset_count_after_init=0`
- `ok_ratio_after_init >= 0.90`
- `image_to_last_imu_ms.p50` and `p95` within the final gate
- selected image and IMU topic counts/fps spans are present in preflight

## If It Passes

Run the generator command recorded in:

```text
extra_ws/debug_runs/fix_until_stable/155_next_final_artifact_command_postinit0_after_pass.md
```

Then inspect:

```bash
sed -n '1,240p' extra_ws/debug_runs/fix_until_stable/final_stability_report.md
sed -n '1,220p' extra_ws/debug_runs/fix_until_stable/stability_report.md
sed -n '1,220p' extra_ws/debug_runs/fix_until_stable/decision.md
sed -n '1,220p' extra_ws/debug_runs/fix_until_stable/final_patch_summary.md
sed -n '1,220p' extra_ws/debug_runs/fix_until_stable/final_commands.md
cmp -s extra_ws/src/ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml extra_ws/debug_runs/fix_until_stable/best_config.yaml
```

## If It Fails

Do not generate final artifacts. Parse the aggregate and per-run logs first:

```bash
sed -n '1,220p' extra_ws/debug_runs/fix_until_stable/30_postinit_inliers0_wrapper_pose_gate_full_window.md
python3 -m json.tool extra_ws/debug_runs/fix_until_stable/30_postinit_inliers0_wrapper_pose_gate_full_window.json | sed -n '1,260p'
```

Then write the next evidence document and choose exactly one minimal next
change based on the failure mode.
