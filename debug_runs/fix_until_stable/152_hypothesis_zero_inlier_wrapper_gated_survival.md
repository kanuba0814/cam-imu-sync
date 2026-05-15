# Hypothesis: Zero-Inlier Wrapper-Gated Post-Init Survival

## Observation

Experiment 29 improved the system from 0/3 to 1/3 full-bag ROS2 wrapper replay passes:

- The ROS2 wrapper blocked low-confidence pose publication.
- No invalid poses were published.
- No runtime errors occurred.
- One run passed all final stability gates.

The two failing runs still spend too much time in `RECENTLY_LOST` after IMU initialization. The failure windows include long zero-inlier stretches, so lowering the post-init gate from 5 to 3 or 1 is unlikely to be enough.

## Proposed Change

Make one H30 config-only change:

```yaml
Tracking.MinInliersImuMonoPostInit: 0
```

Keep the ROS2 wrapper trust gates unchanged:

```text
min_pose_publish_inliers=15
min_pose_publish_tracked_mappoints=15
```

## Expected Effect

ORB should keep the current inertial map alive through brief post-init visual dropouts instead of transitioning into long `RECENTLY_LOST` spans and reset/reinit cycles. The ROS2 wrapper should still suppress external pose output whenever visual support is below the 15/15 publication gate.

The result is acceptable only if the full ROS2 wrapper replay shows:

- `pass_count == 3`
- `reset_count_after_init == 0`
- `reset_delta_last_60_sec == 0`
- `ok_ratio_after_init >= 0.90`
- `invalid_pose_publish_count == 0`
- median inliers and tracked map points remain above the final gates

## Validation

Run the normal containerized wrapper replay after the config commit:

```bash
docker exec -w /home/gxxl/slam_ws_v2/extra_ws autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 colcon build --packages-select orb_slam3_ros2 --cmake-args -DORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3'
docker exec -w /home/gxxl/slam_ws_v2 autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 30_postinit_inliers0_wrapper_pose_gate_full_window --timeout-sec 210'
```
