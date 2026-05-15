# Hypothesis: Use 6s H30 IMU Init Acceptance Window

## Observation

Experiment 26 with `LocalMapping.ImuMonoInitMinTime: 4.0` preserved final maps but accepted weak IMU initialization near scale 0.11-0.13, then failed around repeated dropout windows.

Experiment 27 with `LocalMapping.ImuMonoInitMinTime: 8.0` sometimes produced a stronger scale, but it kept the map pre-IMU too long and caused extra active-map resets before initialization.

## Proposed Single Change

Change only:

```yaml
LocalMapping.ImuMonoInitMinTime: 6.0
```

Keep all other current H30 settings fixed:

- `Tracking.FramesToResetIMU: 100000`
- `Tracking.ResetActiveMapBeforeInertialBA2: 0`
- `LocalMapping.ResetOnSmallMotionBeforeInertialBA2: 0`
- `Camera.fps: 9`
- `ORBextractor.nFeatures: 1200`
- FAST thresholds: `15/5`

## Expected Effect

The 6-second midpoint should delay the weak 4-second inertial acceptance without spending as long as the failed 8-second candidate in the fragile pre-IMU reset path.

The validation signal should be:

- first accepted scale higher than the 4-second run
- fewer pre-IMU active-map resets than the 8-second run
- OK ratio after init closer to or above 0.90
- reset-after-init and reset-in-last-60s at zero

## Validation

After committing the config change, rebuild and run the wrapper-only full-bag replay:

```bash
docker exec -w /home/gxxl/slam_ws_v2/extra_ws autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 colcon build --packages-select orb_slam3_ros2 --cmake-args -DORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3'
docker exec -w /home/gxxl/slam_ws_v2 autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 28_imu_init_min_time_6s_no_pre_ba2_reset_full_window --timeout-sec 210'
```
