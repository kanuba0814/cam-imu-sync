# Evidence: disable H30 small-motion reset loop

## Change under validation

- `extra_ws/src/ORB_SLAM3_ROS2` commit: `9a7ca4c fix: disable H30 small-motion reset loop`
- Config change:
  - `LocalMapping.ResetOnSmallMotionBeforeInertialBA2: 0`

## Validation

Rebuilt `orb_slam3_ros2` in `autoware_env_v2_host`, then ran:

```bash
docker exec -w /home/gxxl/slam_ws_v2 autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 10_disable_small_motion_reset --timeout-sec 180'
```

## Result

- `pass_count`: 0 / 3
- run return codes: 124, 124, 124
- required V2 tags present: true for all three runs
- IMU initialized: true for all three runs
- invalid pose publishes: 0 for all three runs

| Run | OK ratio after init | Reset after init | Final KFs | Median inliers | Median MPs | Img buf max |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.5988 | 14 | 21 | 105.0 | 108.5 | 1.0 |
| 2 | 0.3923 | 16 | 0 | 48.0 | 0.0 | 1.0 |
| 3 | 0.5821 | 12 | 21 | 105.0 | 106.0 | 1.0 |

## Interpretation

This change was useful but not sufficient. Runs 1 and 3 now keep populated maps when they are in `OK` state, with median tracked map points above 100 and median inliers above 100. The failure is now dominated by repeated `OK -> RECENTLY_LOST -> NOT_INITIALIZED` transitions and active-map resets.

The reset source is no longer the `LocalMapping` small-motion guard. The logs now point to the `Tracking` reset policy:

- `IMU is not or recently initialized. Reseting active map...`
- `TRACK_LOCAL_MAP_FAILED reason=imu_mono_low_inliers`
- `ACTIVE_MAP_RESET reason=active_map_reset`

Because this fixed low-motion bag does not accumulate enough inertial time for BA2, `Tracking.ResetActiveMapBeforeInertialBA2` remains a reset trigger after short visual drops.
