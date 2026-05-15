# Evidence: Experiment 29 Post-Init Inliers 5 Wrapper Gate Partial Pass

## Replay

- Command: `python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label 29_postinit_inliers5_wrapper_pose_gate_full_window --timeout-sec 210`
- Bag: `/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136`
- Wrapper launch topics: `/sync/image_raw`, `/sync/imu`
- Ignored raw topics: `/image_raw`, `/imu/data_raw`, `/imu/raw_hw`
- Result source: ROS2 wrapper replay, not ORB standalone.

## Loaded Settings

The run logs confirm the intended wrapper-gated candidate was loaded:

- `Tracking.FramesToResetIMU: 100000`
- `Tracking.ResetActiveMapBeforeInertialBA2: 0`
- `LocalMapping.ImuMonoInitMinTime: 4.0`
- `Tracking.MinInliersImuMonoPostInit: 5`
- `min_pose_publish_inliers=15`
- `min_pose_publish_tracked_mappoints=15`

## Result

- run_count: 3
- pass_count: 1
- all_passed: false
- Process returncodes: 0, 0, 0
- Runtime errors: 0, 0, 0
- Controlled backlog: true for all runs
- Invalid pose publishes: 0 for all runs

| Run | First IMU init frame | OK ratio after init | Max lost streak after init | Reset after init | Reset delta last 60s | Final KFs | Median inliers | Median MPs | Pose publish blocked |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 814 | 0.9143 | 4.9337 | 0 | 0 | 91 | 324.5 | 324.5 | 978 |
| 2 | 777 | 0.6005 | 4.9685 | 1 | 1 | 21 | 149.5 | 150.0 | 1197 |
| 3 | 777 | 0.8646 | 4.9482 | 0 | 0 | 21 | 184.0 | 184.0 | 1015 |

## Failure Details

The wrapper gate is effective:

- Run logs include `min_pose_publish_inliers=15 min_pose_publish_tracked_mappoints=15`.
- Low-confidence frames are blocked instead of published.
- `invalid_pose_publish_count` remains zero in all three runs.

The remaining failure is inside ORB tracking state, not ROS2 pose publication. After first IMU initialization, the failing runs still enter long `RECENTLY_LOST` spans caused by `imu_mono_low_inliers`. The low-inlier spans are not just 1-4 inlier edge cases:

- Run 2 post-init records: 326 zero-inlier samples, 12 samples with 1-4 inliers.
- Run 3 post-init records: 116 zero-inlier samples, 6 samples with 1-4 inliers.
- Run 3 has zero-inlier RECENTLY_LOST spans at frames `1066-1067`, `1071-1105`, and `1256-1306`.

## Decision

The wrapper-gated direction is valid because it produced the first full stability pass and preserved ROS2 pose trust. However, `Tracking.MinInliersImuMonoPostInit: 5` is still too high for the fixed H30 sync bag because the remaining failures include zero-inlier post-init recovery windows.

Do not finalize experiment 29. The next test should keep the wrapper publication gate unchanged and lower only the post-init internal ORB survival gate.
