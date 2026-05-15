# Evidence: Experiment 27 IMU Init Min Time 8s Failed

## Replay

- Command: `python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 27_imu_init_min_time_8s_no_pre_ba2_reset_full_window --timeout-sec 210`
- Bag: `/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136`
- Wrapper launch topics: `/sync/image_raw`, `/sync/imu`
- Ignored raw topics: `/image_raw`, `/imu/data_raw`, `/imu/raw_hw`
- Build before replay: containerized `colcon build --packages-select orb_slam3_ros2` passed in `autoware_env_v2_host`.

## Loaded Settings

The run logs confirm the intended candidate was loaded:

- `frames_to_reset_imu=100000`
- `reset_active_map_before_inertial_ba2=0`
- `ImuMonoInitMinTime: 8`
- `ImuMonoInitMinKFs: 10`

This is a ROS2 wrapper replay result, not an ORB standalone run.

## Result

- run_count: 3
- pass_count: 0
- all_passed: false
- Process returncodes: 0, 0, 0
- Runtime errors: 0, 0, 0
- Controlled backlog: true for all runs
- Invalid pose publishes: 0 for all runs

| Run | First IMU init frame | OK ratio after init | Max lost streak after init | Reset after init | Reset delta last 60s | Final KFs | Median inliers | Median MPs |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 848 | 0.4037 | 4.9585 | 0 | 0 | 0 | 0.0 | 0.0 |
| 2 | 827 | 0.5399 | 4.9822 | 2 | 2 | 21 | 130.0 | 134.0 |
| 3 | 931 | 0.8095 | 4.9852 | 1 | 1 | 21 | 168.0 | 168.0 |

## Interpretation

The 8-second delay was not acceptable. It delayed IMU acceptance, but it also left the map in the pre-IMU path long enough to hit additional low-inlier active-map resets before initialization.

Useful signal:

- Run 3 eventually initialized with a much stronger scale near `1.0127`, far better than the about `0.11-0.13` scale seen in experiment 26.

Negative signal:

- Run 1 lost the final map entirely.
- Run 2 still had reset-after-init and reset-in-last-60s failures.
- Pre-IMU low-inlier resets appeared before a stable initialization could be accepted, for example run 2 at frames 239, 441, 474, 654, and 699.

## Decision

Do not finalize `LocalMapping.ImuMonoInitMinTime: 8.0`.

The old `Tracking.MinInliersImuMonoPreInit` 30/35/40 experiments were already rejected because they admitted weak bootstraps or worsened reset loops. The next minimal retry should keep the same conceptual knob but reduce the delay to a midpoint:

- Test `LocalMapping.ImuMonoInitMinTime: 6.0`
- Keep `Tracking.FramesToResetIMU: 100000`
- Keep `Tracking.ResetActiveMapBeforeInertialBA2: 0`
