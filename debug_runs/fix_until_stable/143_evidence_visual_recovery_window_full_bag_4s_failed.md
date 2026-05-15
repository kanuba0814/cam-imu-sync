# Evidence: Experiment 25 Full-Bag Visual Recovery Window Failed

## Replay

- Command: `python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 25_visual_recovery_window_full_bag_4s --timeout-sec 210`
- Bag: `/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136`
- Wrapper launch topics: `/sync/image_raw`, `/sync/imu`
- Ignored raw topics: `/image_raw`, `/imu/data_raw`, `/imu/raw_hw`
- Build before replay: containerized `colcon build --packages-select orb_slam3_ros2` passed in `autoware_env_v2_host`.

## Result

- run_count: 3
- pass_count: 0
- all_passed: false
- Process returncodes: 0, 0, 0
- Runtime errors: 0, 0, 0
- Controlled backlog: true for all runs

| Run | OK ratio after init | Reset after init | Reset delta last 60s | Final KFs | Median inliers | Median MPs |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.4306 | 11 | 3 | 0 | 27 | 0 |
| 2 | 0.8333 | 5 | 3 | 21 | 165 | 165 |
| 3 | 0.4040 | 6 | 4 | 0 | 7 | 0 |

## Loaded Settings

The replay logs confirm the intended candidate was actually loaded:

- `frames_to_reset_imu=100000`
- `ImuMonoInitMinTime: 4`
- `reset_active_map_before_inertial_ba2=1`

This rules out a stale install/config issue for experiment 25.

## Failure Path

Experiment 25 did not hit the fixed-frame `RESETING FRAME!!!` path and did not crash. The remaining failure mode is `TRACK_LOCAL_MAP_FAILED -> ACTIVE_MAP_RESET`:

- Run 1 initialized IMU at frame 264/265, then reset at frame 445 after `imu_mono_low_inliers` with 2 inliers.
- Run 2 initialized IMU at frame 810/811, then reset at frames 955, 1061, 1103, and 1253 with 1-7 inliers despite good map-quality windows elsewhere.
- Run 3 initialized IMU at frame 806/807, then reset at frame 944 and later reset loops.

The current single-variable change was insufficient. Keeping `FramesToResetIMU=100000` avoids the TODO reset-frame gate, but `Tracking.ResetActiveMapBeforeInertialBA2` remains enabled and clears the active map on transient low-inlier frames before inertial BA2.

## Next Hypothesis

Keep the full-bag visual recovery window and disable only pre-BA2 active-map reset on local-map tracking failure:

- Keep `Tracking.FramesToResetIMU: 100000`
- Keep `LocalMapping.ImuMonoInitMinTime: 4.0`
- Add `Tracking.ResetActiveMapBeforeInertialBA2: 0`

This is not a duplicate of experiment 20 because experiment 20 also used `Tracking.FramesToResetIMU: 90`, which still exposed the fixed-frame IMU reset/TODO path.
