# Evidence: 24_disable_imu_reset_window_4s failed

Run label: `24_disable_imu_reset_window_4s`
Aggregate: `/home/gxxl/slam_ws_v2/extra_ws/debug_runs/fix_until_stable/24_disable_imu_reset_window_4s.json`
Replay path: ROS2 wrapper only, fixed sync bag, full replay, `start_offset_sec=0.0`

Changed variable:

- `LocalMapping.ImuMonoInitMinTime: 4.0`
- `Tracking.FramesToResetIMU: 0`

Loaded policy was confirmed in logs:

- `imu_mono_init_min_time=4`
- `frames_to_reset_imu=0`

Aggregate result:

- `run_count=3`
- `pass_count=0`
- `all_passed=False`

Per-run failure summary:

| Run | Runtime errors | First IMU init frame | OK ratio after init | Reset after init | Reset delta last 60 sec | Final KFs | Median MPs | Median inliers |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0 | 785 | 0.6534090909090909 | 12 | 6 | 21 | 127.5 | 126.0 |
| 2 | 0 | 803 | 0.697215777262181 | 11 | 8 | 21 | 125.0 | 124.0 |
| 3 | 0 | 788 | 0.6350114416475973 | 9 | 5 | 21 | 138.0 | 137.5 |

Interpretation:

- `Tracking.FramesToResetIMU: 0` removed the `RESETING FRAME!!!` segfault path: no wrapper process deaths were observed in the three replays.
- The same change forces immediate IMU prediction after initialization, and each run enters a post-init low-inlier reset loop.
- Later initializations sometimes survive to the end, but too late to satisfy OK-ratio and no-reset gates.

Decision:

- Do not use `Tracking.FramesToResetIMU: 0` as the final H30 policy.
- The next minimal experiment should preserve the visual recovery path while bypassing the finite reset-frame gate.
