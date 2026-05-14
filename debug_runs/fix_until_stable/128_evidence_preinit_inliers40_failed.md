# Evidence: 22_preinit_inliers40_frames90 failed

Run label: `22_preinit_inliers40_frames90`
Aggregate: `/home/gxxl/slam_ws_v2/extra_ws/debug_runs/fix_until_stable/22_preinit_inliers40_frames90.json`
Replay path: ROS2 wrapper only, fixed sync bag, full replay, `start_offset_sec=0.0`

Changed variable:

- `Tracking.MinInliersImuMonoPreInit: 40`
- `Tracking.FramesToResetIMU: 90`
- post-init active-map reset kept enabled

Loaded policy was confirmed in logs:

- `imu_mono_pre_init=40`
- `frames_to_reset_imu=90`
- `reset_active_map_before_inertial_ba2=1`

Aggregate result:

- `run_count=3`
- `pass_count=0`
- `all_passed=False`

Per-run failure summary:

| Run | Runtime errors | First IMU init frame | OK ratio after init | Reset after init | Reset delta last 60 sec | Final KFs | Median MPs | Median inliers |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1 | 578 | 0.6371490280777538 | 6 | 7 | 34 | 161.0 | 160.0 |
| 2 | 0 | 258 | 0.4815340909090909 | 14 | 4 | 21 | 0.0 | 37.0 |
| 3 | 1 | 258 | 0.2921511627906977 | 7 | 6 | 33 | 0.0 | 35.0 |

Interpretation:

- Threshold 40 is worse than threshold 30 and worse than the frames90 baseline for OK ratio stability.
- It still permits early weak IMU initialization at frame 258 in two runs.
- It still fails reset-after-init and reset-in-last-60s gates in all runs.
- Runs 1 and 3 still have `imu_mono_node_cpp` death with `exit code -11`.

Decision:

- Revert the pre-init inlier threshold experiment line.
- Do not keep either `Tracking.MinInliersImuMonoPreInit: 30` or `40` in the final H30 config.
- Next work should target a different failure mechanism, not this threshold line.
