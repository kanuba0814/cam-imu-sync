# Hypothesis: Disable Pre-BA2 Active-Map Reset With Full Replay Window

## Observation

Experiment 25 passed the wrapper-only replay preflight and loaded the intended H30 settings, but failed all three stability runs. The common failure is not backlog, stale raw topics, process death, or the fixed-frame IMU reset gate. It is a local-map low-inlier frame causing `ACTIVE_MAP_RESET` while the map is still before inertial BA2.

Current loaded policy from experiment 25:

- `frames_to_reset_imu=100000`
- `ImuMonoInitMinTime: 4`
- `reset_active_map_before_inertial_ba2=1`

## Proposed Single Change

Set only:

```yaml
Tracking.ResetActiveMapBeforeInertialBA2: 0
```

Do not change feature count, FAST thresholds, IMU init time, queue settings, replay command, replay topics, or `Tracking.FramesToResetIMU`.

## Expected Effect

After IMU initialization, a transient low-inlier `TrackLocalMap()` failure before inertial BA2 should enter `RECENTLY_LOST` without immediately resetting the active map. The existing visual/IMU recovery path can then attempt to recover on subsequent frames, and `reset_count_after_init` should stay at zero.

## Risk

If low-inlier frames represent unrecoverable bad pose rather than a transient dropout, the run may fail with low OK ratio or long `RECENTLY_LOST` streaks instead of reset loops. The stability gate already rejects those cases.

## Validation

After committing the config change, rebuild and run:

```bash
docker exec -w /home/gxxl/slam_ws_v2/extra_ws autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 colcon build --packages-select orb_slam3_ros2 --cmake-args -DORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3'
docker exec -w /home/gxxl/slam_ws_v2 autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 26_no_pre_ba2_active_reset_full_window_4s --timeout-sec 210'
```
