# Evidence: 23_imu_init_min_time_4s_frames90 failed

Run label: `23_imu_init_min_time_4s_frames90`
Aggregate: `/home/gxxl/slam_ws_v2/extra_ws/debug_runs/fix_until_stable/23_imu_init_min_time_4s_frames90.json`
Replay path: ROS2 wrapper only, fixed sync bag, full replay, `start_offset_sec=0.0`

Changed variable:

- `LocalMapping.ImuMonoInitMinTime: 4.0`
- `Tracking.FramesToResetIMU: 90`

Loaded policy was confirmed in logs:

- `imu_mono_init_min_time=4`
- `frames_to_reset_imu=90`

Aggregate result:

- `run_count=3`
- `pass_count=0`
- `all_passed=False`

Per-run failure summary:

| Run | Runtime errors | First IMU init frame | OK ratio after init | Reset after init | Reset delta last 60 sec | Final KFs | Median MPs | Median inliers |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1 | 779 | 1.0 | 0 | 6 | 18 | 366.0 | 366.0 |
| 2 | 0 | 786 | 0.4563662374821173 | 15 | 4 | 21 | 0.0 | 49.0 |
| 3 | 1 | 786 | 0.7064439140811456 | 5 | 6 | 21 | 188.0 | 186.0 |

Interpretation:

- Delaying monocular IMU acceptance to 4 seconds can help: run 1 reached `OK ratio=1.0` with `reset_after_init=0`.
- The same run still failed the final map gate (`final_keyframes=18`) and reported one runtime error.
- Runs 1 and 3 still died with `exit code -11` shortly after `RESETING FRAME!!!`, matching the incomplete ORB_SLAM3 `ResetFrameIMU()` gate.
- The delay alone does not prevent weak initializations in all runs, because runs 2 and 3 still reset after IMU init.

Decision:

- Keep the 4-second IMU acceptance delay as a useful partial fix.
- Do not keep a finite `Tracking.FramesToResetIMU: 90` as the final policy unless the reset-frame gate is repaired or bypassed.
