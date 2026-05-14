# Evidence: revert pre-BA2 reset-policy toggle

## Change under validation

- `extra_ws/src/ORB_SLAM3_ROS2` commit: `6878dbe Revert "fix: keep H30 map through pre-BA2 recent loss"`
- Remaining H30 reset-policy config:
  - `LocalMapping.ResetOnSmallMotionBeforeInertialBA2: 0`
- Removed failed config:
  - `Tracking.ResetActiveMapBeforeInertialBA2: 0`

## Validation

Rebuilt `orb_slam3_ros2` in `autoware_env_v2_host`, then ran:

```bash
docker exec -w /home/gxxl/slam_ws_v2 autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 12_revert_pre_ba2_recent_loss_reset --timeout-sec 180'
```

## Result

- `pass_count`: 0 / 3
- run return codes: 124, 124, 124
- required V2 tags present: true for all three runs
- IMU initialized: true for all three runs
- invalid pose publishes: 0 for all three runs
- image buffer max: 1 for all three runs

| Run | OK ratio after init | Reset after init | Final KFs | Median inliers | Median MPs | Max lost streak |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.3697 | 15 | 21 | 46.0 | 0.0 | 0.00s |
| 2 | 0.6197 | 16 | 21 | 130.0 | 132.0 | 0.00s |
| 3 | 0.2921 | 10 | 21 | 34.0 | 0.0 | 0.00s |

## Interpretation

The revert fixed the harmful long `RECENTLY_LOST` behavior from run `11`: max lost streak is now zero in all three runs, and one run recovered high map-point and inlier medians. The system is still far from the goal because reset count remains high and only one of three runs keeps a populated map.

The dominant remaining pattern is pre-IMU-init map deletion on borderline inlier counts, followed by later post-init low-inlier resets. Examples:

- run 1: `imu_mono_low_inliers_before_imu_init` with 46 inliers, then active-map reset
- run 2: `imu_mono_low_inliers_before_imu_init` with 44 and 41 inliers, then active-map reset
- run 3: `imu_mono_low_inliers_before_imu_init` with 40, 36, and 37 inliers, then active-map reset

The wrapper path is included in this validation. Pose publishing remains gated (`invalid_pose_publish_count=0`), and queue/latency metrics do not point to a ROS 2 synchronization or backlog problem.
