# 02 Wrapper Runtime Metrics Hypothesis

## Hypothesis

The previous `nFeatures=1200` run still reset and ended `RECENTLY_LOST`, but the logs did not contain queue age, per-frame processing time, bounded queue behavior, or pose-publish gating evidence. Before tuning ORB parameters again, the wrapper must expose whether the failure is caused by stale-frame backlog, slow tracking, bad IMU windows, or false pose publication during invalid tracking states.

## Minimal Change

Preserve the existing ORB core diagnostics and add wrapper-side runtime observability plus safety controls:

- `[orb_queue]` 1 Hz queue/drop/FPS/processed-age metrics.
- `[orb_timing]` per-frame cv_bridge, wait, track, video, total, and image-age metrics.
- `[orb_imu_window]` per-frame IMU window timing.
- `[orb_state_transition]` tracking/IMU/reset/map changes.
- `[orb_pose_gate]` pose publish allow/deny decisions.
- `[orb_visual_quality]` features, inliers, tracked map points, keyframes, and matches.
- `enable_video_recording=false` by default.
- `publish_pose_only_when_tracking_ok=true` by default.
- bounded image and IMU queues with controlled drop counters.
- stale image dropping when processing age exceeds `max_image_age_ms`.

## Commits

- `libs/ORB_SLAM3` commit `a6b6c74`: `debug: add ORB-SLAM3 tracking mapping reset reason diagnostics`
- `extra_ws/src/ORB_SLAM3_ROS2` commit `e626edb`: `debug: add ORB runtime queue timing IMU window and pose logs`
- `extra_ws/src/ORB_SLAM3_ROS2` commit `0deab31`: `test: add repeatable offline ORB stability replay harness`
- `extra_ws/src/ORB_SLAM3_ROS2` commit `580d492`: `chore: preserve H30 sync launch and config diagnostics`

## Validation Plan

Required next commands, inside `autoware_env_v2_host`:

```bash
cd /home/gxxl/slam_ws_v2/libs/ORB_SLAM3
./build.sh
```

```bash
cd /home/gxxl/slam_ws_v2/extra_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
export ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3
colcon build --packages-select orb_slam3_ros2 --symlink-install
```

```bash
cd /home/gxxl/slam_ws_v2/extra_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
python3 src/ORB_SLAM3_ROS2/tools/run_stability_replay.py \
  --runs 3 \
  --bag-path /home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136 \
  --settings-file /home/gxxl/slam_ws_v2/extra_ws/debug_runs/latest/config_variants/rmoncam_h30_nfeatures_1200.yaml \
  --label 02_replay_baseline_after_wrapper_fixes
```

## Blocker

Container validation is currently blocked outside the codebase: Docker API access failed from the sandbox with `permission denied`, and the escalation request was rejected by the platform quota guard. No replay result has been accepted yet.
