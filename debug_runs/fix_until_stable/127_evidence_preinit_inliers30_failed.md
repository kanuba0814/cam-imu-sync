# Evidence: 21_preinit_inliers30_frames90 failed

Run label: `21_preinit_inliers30_frames90`
Aggregate: `/home/gxxl/slam_ws_v2/extra_ws/debug_runs/fix_until_stable/21_preinit_inliers30_frames90.json`
Replay path: ROS2 wrapper only, fixed sync bag, full replay, `start_offset_sec=0.0`

Changed variable:

- `Tracking.MinInliersImuMonoPreInit: 30`
- `Tracking.FramesToResetIMU: 90`
- post-init active-map reset kept enabled

Loaded policy was confirmed in logs:

- `imu_mono_pre_init=30`
- `frames_to_reset_imu=90`
- `reset_active_map_before_inertial_ba2=1`

Aggregate result:

- `run_count=3`
- `pass_count=0`
- `all_passed=False`

Per-run failure summary:

| Run | Runtime errors | First IMU init frame | OK ratio after init | Reset after init | Reset delta last 60 sec | Final KFs | Median MPs | Median inliers |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1 | 771 | 0.8790322580645161 | 1 | 8 | 42 | 231.5 | 231.5 |
| 2 | 0 | 258 | 0.45454545454545453 | 16 | 6 | 21 | 0.0 | 21.0 |
| 3 | 1 | 771 | 0.9381818181818182 | 3 | 5 | 31 | 212.0 | 212.0 |

Interpretation:

- Lowering the pre-init threshold to 30 improves two runs substantially, but is still not stable.
- Run 2 initialized IMU at frame 258 and then repeatedly reset, so 30 is too permissive and can admit a weak bootstrap.
- Runs 1 and 3 still ended with ROS launch reporting `imu_mono_node_cpp` death, `exit code -11`.
- The setting cannot be accepted as final because reset-after-init, reset-in-last-60s, OK ratio, and runtime-error gates still fail.

Decision:

- Do not finalize `Tracking.MinInliersImuMonoPreInit: 30`.
- Next experiment should keep the same single variable but make it stricter, e.g. `40`, to preserve 40-49 inlier pre-init maps while rejecting weaker early bootstraps.
