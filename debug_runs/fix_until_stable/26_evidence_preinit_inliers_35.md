# Evidence: H30 pre-init inlier gate 35

## Change under validation

- `extra_ws/src/ORB_SLAM3_ROS2` commit: `060661e fix: lower H30 preinit inlier gate`
- Config change:
  - `Tracking.MinInliersImuMonoPreInit: 35`

## Validation

Rebuilt `orb_slam3_ros2` in `autoware_env_v2_host`, then ran:

```bash
docker exec -w /home/gxxl/slam_ws_v2 autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 13_preinit_inliers_35 --timeout-sec 180'
```

## Result

- `pass_count`: 0 / 3
- run return codes: 124, 124, 124
- required V2 tags present: true for all three runs
- IMU initialized: true for all three runs
- invalid pose publishes: 0 for all three runs

| Run | OK ratio after init | Reset after init | Final KFs | Median inliers | Median MPs | Max lost streak |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.2251 | 19 | 21 | 8.0 | 0.0 | 0.00s |
| 2 | 0.3369 | 17 | 21 | 32.0 | 0.0 | 0.00s |
| 3 | 0.4668 | 21 | 21 | 37.0 | 0.0 | 0.00s |

## Interpretation

This change is harmful and should be reverted. It eliminates the only good map-point run seen in `12_revert_pre_ba2_recent_loss_reset`; all three runs now have median tracked map points of zero.

The logs show that lower pre-init gating lets weak maps reach IMU initialization earlier, then they immediately fail post-init tracking:

- run 1: `IMU_INIT_SUCCESS` at frame 257, then `imu_mono_low_inliers` with 2 inliers at frame 258
- run 2: `IMU_INIT_SUCCESS` at frame 257, then `imu_mono_low_inliers` with 2 inliers at frame 258
- repeated later resets occur with post-init inliers between 0 and 14

The wrapper remains behavior-preserving: invalid pose publishes stay at zero and queue metrics remain bounded. The failure is internal map quality, not ROS 2 publication or backlog.
