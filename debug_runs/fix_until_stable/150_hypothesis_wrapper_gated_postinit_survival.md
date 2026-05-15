# Hypothesis: Wrapper-Gated Post-Init Map Survival

## Observation

Experiment 26 is still the best current baseline:

- `LocalMapping.ImuMonoInitMinTime: 4.0`
- `Tracking.FramesToResetIMU: 100000`
- `Tracking.ResetActiveMapBeforeInertialBA2: 0`
- no runtime errors
- final KFs and median inliers/MPs are good

It still fails because brief post-init low-inlier windows enter `RECENTLY_LOST`, then reach the about 5-second lost/reset boundary.

The user reminder is important: final operation is through the ROS2 wrapper. Therefore the fix should preserve ROS2 pose trust, not just relax ORB internals.

## Proposed Change

After restoring the 4-second baseline, make one conceptual change:

1. Lower only the H30 post-init internal survival gate:

```yaml
Tracking.MinInliersImuMonoPostInit: 5
```

2. Add ROS2 wrapper publication gating so poses are not published when the debug state has too few inliers or tracked map points, even if ORB's internal tracking state remains OK.

Default wrapper trust gates:

```text
min_pose_publish_inliers=15
min_pose_publish_tracked_mappoints=15
```

## Expected Effect

ORB should keep the map alive through short 5-14 inlier post-init frames instead of entering long `RECENTLY_LOST` windows. The ROS2 wrapper should still block the corresponding low-confidence poses, keeping final publications trustworthy.

Validation should show:

- `reset_count_after_init == 0`
- `reset_delta_last_60_sec == 0`
- `ok_ratio_after_init >= 0.90`
- `invalid_pose_publish_count == 0`
- median inliers and tracked map points still above the final gates

## Validation

Run the normal containerized wrapper replay after the code/config commits:

```bash
docker exec -w /home/gxxl/slam_ws_v2/extra_ws autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 colcon build --packages-select orb_slam3_ros2 --cmake-args -DORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3'
docker exec -w /home/gxxl/slam_ws_v2 autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 29_postinit_inliers5_wrapper_pose_gate_full_window --timeout-sec 210'
```
