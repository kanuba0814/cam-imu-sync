# Evidence: g2o C++11 ABI rebuild

## Change under validation

- `libs/ORB_SLAM3` commit: `444696b fix: build g2o with C++11 to match ORB`
- Rebuilt in `autoware_env_v2_host`:
  - `docker exec -w /home/gxxl/slam_ws_v2/libs/ORB_SLAM3 autoware_env_v2_host bash ./build.sh`
  - `docker exec -w /home/gxxl/slam_ws_v2/extra_ws autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 colcon build --packages-select orb_slam3_ros2 --cmake-args -DORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3'`

## Replay command

```bash
docker exec -w /home/gxxl/slam_ws_v2 autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 09_g2o_cpp11_abi --timeout-sec 180'
```

## Result

- `pass_count`: 0 / 3
- run return codes: 124, 124, 124
- required V2 tags present: true for all three runs
- IMU initialized: true for all three runs
- invalid pose publishes: 0 for all three runs
- allocator abort: not reproduced

| Run | OK ratio after init | Reset after init | Final KFs | Median inliers | Median MPs | Img buf max |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.2955 | 10 | 21 | 7.0 | 0.0 | 1.0 |
| 2 | 0.3649 | 17 | 0 | 12.0 | 0.0 | 1.0 |
| 3 | 0.3589 | 14 | 0 | 133.0 | 0.0 | 1.0 |

## Interpretation

The g2o C++11 rebuild fixed the previous `double free or corruption` / ASAN bad-free failure mode. The remaining failure is not backlog or stale pose publication. The replay now reaches IMU initialization, then repeatedly resets active maps through:

- `IMU_INIT_FAILED reason=not_enough_motion`
- `ACTIVE_MAP_RESET reason=local_mapping_active_map_reset`

Representative log values after IMU init:

- `motion_dist_m`: about `0.00003` to `0.00020`
- `required_motion_dist_m`: `0.020`
- `motion_time_sec`: `0.0`
- `required_motion_time_sec`: `10.0`

The next minimal change should target the small-motion reset policy for this fixed low-motion sync bag.
