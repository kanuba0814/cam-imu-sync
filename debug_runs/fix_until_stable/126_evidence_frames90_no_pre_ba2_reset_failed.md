# Evidence: 20_frames90_no_pre_ba2_reset failed

Run label: `20_frames90_no_pre_ba2_reset`
Aggregate: `/home/gxxl/slam_ws_v2/extra_ws/debug_runs/fix_until_stable/20_frames90_no_pre_ba2_reset.json`
Replay path: ROS2 wrapper only, fixed sync bag, full replay, `start_offset_sec=0.0`

Changed variable:

- `Tracking.ResetActiveMapBeforeInertialBA2: 0`
- Baseline retained `Tracking.FramesToResetIMU: 90`

Loaded policy was confirmed in all run logs:

- `frames_to_reset_imu=90`
- `reset_active_map_before_inertial_ba2=0`
- `visual_pose_optimization_before_inertial_ba2=0`

Aggregate result:

- `run_count=3`
- `pass_count=0`
- `all_passed=False`

Per-run failure summary:

| Run | Runtime errors | OK ratio after init | Reset after init | Final KFs | Median MPs | Median inliers | Reset delta last 60 sec | Final state |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 1 | 0.0 | 0 | 10 | 0.0 | 0.0 | 5 | `RECENTLY_LOST` |
| 2 | 0 | 0.593103448275862 | 1 | 21 | 145.0 | 145.0 | 1 | `OK` |
| 3 | 1 | 0.0 | 0 | 10 | 0.0 | 0.0 | 5 | `RECENTLY_LOST` |

Interpretation:

- This experiment is worse than the current frames90 baseline.
- Disabling the pre-BA2 active-map reset did not make recent-lost recovery stable.
- Runs 1 and 3 initialized IMU, then stayed in `RECENTLY_LOST` with zero tracked map points and zero inliers.
- The bad runs show the IMU state continuing to propagate with large pose drift while visual tracking remains at zero inliers.
- Two runs ended with ROS launch reporting `imu_mono_node_cpp` process death, `exit code -11`.

Decision:

- Revert the YAML experiment commit.
- Do not keep `Tracking.ResetActiveMapBeforeInertialBA2: 0` as the default H30 config.
- Next work should not treat active-map reset suppression alone as a viable fix.
