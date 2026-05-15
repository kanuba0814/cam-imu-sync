# Evidence: Experiment 26 Disabled Pre-BA2 Active Reset But Still Failed

## Replay

- Command: `python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 26_no_pre_ba2_active_reset_full_window_4s --timeout-sec 210`
- Bag: `/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136`
- Wrapper launch topics: `/sync/image_raw`, `/sync/imu`
- Ignored raw topics: `/image_raw`, `/imu/data_raw`, `/imu/raw_hw`
- Build before replay: containerized `colcon build --packages-select orb_slam3_ros2` passed in `autoware_env_v2_host`.

## Loaded Settings

The run logs confirm the candidate was loaded:

- `frames_to_reset_imu=100000`
- `reset_active_map_before_inertial_ba2=0`
- `ImuMonoInitMinTime: 4`

This is a ROS2 wrapper replay result, not an ORB standalone run.

## Result

- run_count: 3
- pass_count: 0
- all_passed: false
- Process returncodes: 0, 0, 0
- Runtime errors: 0, 0, 0
- Controlled backlog: true for all runs
- Invalid pose publishes: 0 for all runs

| Run | OK ratio after init | Max lost streak after init | Reset after init | Reset delta last 60s | Final KFs | Median inliers | Median MPs |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.8165 | 4.9585 | 1 | 1 | 21 | 162.0 | 162.0 |
| 2 | 0.8040 | 5.2824 | 1 | 1 | 21 | 163.0 | 163.0 |
| 3 | 0.7633 | 4.9612 | 1 | 1 | 21 | 185.5 | 185.5 |

## Failure Path

Disabling `Tracking.ResetActiveMapBeforeInertialBA2` changed the failure mode in the expected direction: low-inlier frames no longer immediately clear the active map. The node enters `RECENTLY_LOST` and the wrapper pose gate blocks publishing while tracking is not OK.

The remaining failure is long recently-lost windows and one later reset/rebuild:

- Run 2 initialized at frame 811 with `estimated_scale=0.111557914`, then entered `RECENTLY_LOST` at frame 955 with 5 inliers. It briefly recovered at frame 965, then failed again at frame 966 with scale jumping to `0.407969947` and `bias_norm=1.198534846`.
- Run 2 later entered another long loss at frame 1253 with 13 inliers and frame 1254 with 8 inliers.
- Run 3 initialized at frame 804 with `estimated_scale=0.108848377`, then entered `RECENTLY_LOST` at frame 958 with 7 inliers and frame 959 with 2 inliers.
- Run 1 initialized at frame 854 with `estimated_scale=0.129072172`.

The candidate preserved final maps better than experiment 25, but it did not meet stability gates: OK ratio stayed below 0.90, the lost streak reached about 5 seconds, and `reset_delta_last_60_sec` remained non-zero.

## Conclusion

`Tracking.ResetActiveMapBeforeInertialBA2: 0` is useful but insufficient. The first accepted H30 IMU initialization appears weak: all three runs initialize near scale 0.11-0.13, then later lose tracking around the same visual dropout windows. The next minimal change should delay inertial acceptance so the map uses more motion before committing to IMU initialization.
