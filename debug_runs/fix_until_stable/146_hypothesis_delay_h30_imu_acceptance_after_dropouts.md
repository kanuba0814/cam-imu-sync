# Hypothesis: Delay H30 IMU Acceptance After Dropout Failures

## Observation

Experiment 26 verified that the ROS2 wrapper path is using the intended sync-only replay and H30 config. Disabling pre-BA2 active-map reset prevented immediate map clearing, but all three runs still failed the stability gate after accepting a weak first IMU initialization:

- First accepted scale was about 0.11-0.13 across the three runs.
- The first major post-init failure happened near the same dropout window around frame 955-958.
- Run 2 showed a large post-recovery jump: scale from about 0.11 to about 0.41 and `bias_norm` to about 1.20.

## Proposed Single Change

Change only:

```yaml
LocalMapping.ImuMonoInitMinTime: 8.0
```

Keep all other current H30 settings fixed:

- `Tracking.FramesToResetIMU: 100000`
- `Tracking.ResetActiveMapBeforeInertialBA2: 0`
- `LocalMapping.ResetOnSmallMotionBeforeInertialBA2: 0`
- `Camera.fps: 9`
- `ORBextractor.nFeatures: 1200`
- FAST thresholds: `15/5`

## Expected Effect

The local mapper should wait for a longer motion window before accepting IMU initialization. If the current 4-second acceptance is locking onto a weak inertial solution, the 8-second gate should reduce early bias/scale jumps and improve the OK ratio after initialization.

## Risk

Initialization may happen later, or may not happen on some replay runs if the motion window is still insufficient. The stability gate already rejects no-init runs and late unstable maps, so this is a safe one-variable test.

## Validation

After committing the config change, rebuild and run the wrapper-only full-bag replay:

```bash
docker exec -w /home/gxxl/slam_ws_v2/extra_ws autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 colcon build --packages-select orb_slam3_ros2 --cmake-args -DORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3'
docker exec -w /home/gxxl/slam_ws_v2 autoware_env_v2_host bash -lc 'source /opt/ros/humble/setup.bash && source /home/gxxl/slam_ws_v2/driver_ws/install/setup.bash && source /home/gxxl/slam_ws_v2/extra_ws/install/setup.bash && ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3 python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 27_imu_init_min_time_8s_no_pre_ba2_reset_full_window --timeout-sec 210'
```
