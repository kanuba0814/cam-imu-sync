# Evidence: keep map through pre-BA2 recent loss

## Change under validation

- `extra_ws/src/ORB_SLAM3_ROS2` commit: `bfca09e fix: keep H30 map through pre-BA2 recent loss`
- Config change:
  - `Tracking.ResetActiveMapBeforeInertialBA2: 0`

## Validation

Rebuilt `orb_slam3_ros2` in `autoware_env_v2_host`, then ran:

```bash
docker exec -w /home/gxxl/slam_ws_v2 autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 11_keep_map_pre_ba2_recent_loss --timeout-sec 180'
```

## Result

- `pass_count`: 0 / 3
- run return codes: 124, 124, 124
- required V2 tags present: true for all three runs
- IMU initialized: true for all three runs
- invalid pose publishes: 0 for all three runs

| Run | OK ratio after init | Reset after init | Final KFs | Median inliers | Median MPs | Max lost streak |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.2566 | 6 | 21 | 30.0 | 0.0 | 5.07s |
| 2 | 0.1803 | 4 | 0 | 0.0 | 0.0 | 5.03s |
| 3 | 0.4541 | 11 | 21 | 35.0 | 0.0 | 5.12s |

## Interpretation

This change is harmful. It reduces immediate active-map resets, but the map is not credible: median tracked map points drops to zero in all three runs, `RECENTLY_LOST` grows to roughly five-second streaks, and `OK` ratio is worse than the previous run with only the small-motion reset disabled.

The previous useful state, `10_disable_small_motion_reset`, had two runs with median tracked map points above 100 and median inliers above 100. Keeping the pre-BA2 map through recent loss destroys that signal and allows long bad-state periods instead of producing stable tracking.

Per the goal rule, this config change should be reverted instead of stacked with further changes.
