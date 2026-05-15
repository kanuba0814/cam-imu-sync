# Evidence: Experiment 28 IMU Init Min Time 6s Failed

## Replay

- Command: `python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 28_imu_init_min_time_6s_no_pre_ba2_reset_full_window --timeout-sec 210`
- Bag: `/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136`
- Wrapper launch topics: `/sync/image_raw`, `/sync/imu`
- Ignored raw topics: `/image_raw`, `/imu/data_raw`, `/imu/raw_hw`
- Build before replay: containerized `colcon build --packages-select orb_slam3_ros2` passed in `autoware_env_v2_host`.

## Loaded Settings

The run logs confirm the intended candidate was loaded:

- `frames_to_reset_imu=100000`
- `reset_active_map_before_inertial_ba2=0`
- `ImuMonoInitMinTime: 6`
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
| 1 | 807 | 0.7136 | 5.0845 | 1 | 1 | 21 | 159.0 | 159.0 |
| 2 | 831 | 0.6767 | 5.0159 | 4 | 3 | 21 | 157.0 | 158.0 |
| 3 | 798 | 0.7850 | 4.9527 | 5 | 5 | 21 | 157.0 | 158.0 |

## Interpretation

The 6-second midpoint is still worse than the 4-second experiment 26 baseline. It preserves final maps, but reset-after-init and reset-in-last-60s both fail, and OK ratio stays below the 0.90 gate.

The useful signal is that later in run 2/run 3 the scale can approach about 0.96, but the first accepted initialization still starts weak and the run continues to hit low-inlier recovery/reset paths.

## Decision

Do not finalize `LocalMapping.ImuMonoInitMinTime: 6.0`.

Restore the known better 4-second H30 baseline before testing a different mechanism. The next candidate should not further tune IMU init delay. It should instead decouple internal map survival from ROS2 pose publication:

- Keep ROS2 wrapper from publishing low-confidence poses.
- Let ORB survive brief post-init 5-14 inlier frames if the wrapper blocks those poses.
