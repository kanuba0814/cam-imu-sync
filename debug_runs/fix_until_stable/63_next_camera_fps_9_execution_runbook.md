# Next Execution Runbook: H30 Camera.fps 9

## Current blocker

Do not apply the behavior change until Docker execution in `autoware_env_v2_host` is available. The next step requires immediate containerized build and three full fixed-bag ROS2 wrapper replays.

Current source state before this runbook:

```text
extra_ws/src/ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml
Camera.fps: 30
LocalMapping.ResetOnSmallMotionBeforeInertialBA2: 0
IMU.Frequency: 100.0
ORBextractor.nFeatures: 1200
```

## One allowed behavior change

Change only:

```yaml
Camera.fps: 9
```

Do not change ORBextractor, IMU, queue, pose gate, reset, or inlier parameters in the same commit.

Commit in the wrapper repo:

```bash
git -C /home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2 diff -- config/Monocular-Inertial/rmoncam_h30.yaml
git -C /home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2 add config/Monocular-Inertial/rmoncam_h30.yaml
git -C /home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2 commit -m "fix: match H30 camera fps to fixed bag"
```

## Required container build

Run inside `autoware_env_v2_host`:

```bash
docker exec -w /home/gxxl/slam_ws_v2/extra_ws autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 colcon build --packages-select orb_slam3_ros2 --cmake-args -DORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3'
```

## Required three-run replay

Run the fixed bag through the ROS2 wrapper only:

```bash
docker exec -w /home/gxxl/slam_ws_v2 autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 15_camera_fps_9 --timeout-sec 210'
```

The runner must report preflight fields showing:

```text
selected_image_topic: /sync/image_raw
selected_imu_topic: /sync/imu
settings_file: /home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml
settings_camera_fps: 9.0
timeout_sec: 210.0
```

## Result inspection

Inspect:

```bash
sed -n '1,80p' /home/gxxl/slam_ws_v2/extra_ws/debug_runs/fix_until_stable/15_camera_fps_9.md
python3 -m json.tool /home/gxxl/slam_ws_v2/extra_ws/debug_runs/fix_until_stable/15_camera_fps_9.json | sed -n '1,160p'
```

Pass requires all three runs to satisfy the guarded stability gates. At minimum, check:

```text
all_passed: true
pass_count: 3
returncode: 0 for every run
reset_count_after_init: 0 for every run
ok_ratio_after_init >= 0.90 for every run
final_keyframes >= 20 for every run
median_tracked_map_points_after_init >= 80 for every run
median_inliers_after_init >= 50 for every run
invalid_pose_publish_count: 0 for every run
```

## If it fails

Write evidence for `15_camera_fps_9`, keep the commit only if the result improves toward the gates and the change remains explainable. If it does not improve, revert or mark the change failed before testing another hypothesis.

The goal is complete only after a passing three-run aggregate produces final `best_config.yaml`, `decision.md`, `stability_report.md`, `final_stability_report.md`, `final_patch_summary.md`, and `final_commands.md`.
