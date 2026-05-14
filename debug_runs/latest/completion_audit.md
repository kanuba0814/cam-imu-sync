# Completion Audit

Status: complete for `goal/orbDebugGoal.md`.

## Objective Restatement

Use the fixed sync-only bags to perform principle-driven diagnosis of `ORB_SLAM3_ROS2` and `cam_imu_sync`, never start real drivers or live `cam_imu_sync`, never require or subscribe to `/image_raw`, write hypothesis/evidence artifacts for each stage, stop on hard evidence, and end with one of the enumerated conclusions in `debug_runs/latest/decision.md`.

## Prompt-to-Artifact Checklist

| Requirement | Evidence | Status |
| --- | --- | --- |
| Read `goal/orbDebugGoal.md` | Current artifacts follow its stage names and stop gates. | done |
| Workspace is `/home/gxxl/slam_ws_v2/extra_ws` | All new outputs are under `extra_ws/debug_runs/latest`; new audit tool is `extra_ws/tools/h30_sync_bag_audit.py`. | done |
| Use `h30_sync_only_noMove` and `h30_sync_only_normal` | `01_sync_bag_audit.md` names both exact bag paths. | done |
| Do not start real camera driver | Only offline audit and `h30_bag_replay.launch.py` bag replay were used. | done |
| Do not start real IMU driver | Same evidence. | done |
| Do not start live `cam_imu_sync` | Same evidence; `/rosout` was read only from bag. | done |
| Do not subscribe to `/image_raw` or require raw image | `01_sync_bag_audit.md` says `/image_raw` is intentionally not required or read. | done |
| Stage 1 tool `tools/h30_sync_bag_audit.py` | File exists and was run inside `autoware_env_v2_host`. | done |
| Stage 1 JSON and Markdown | `debug_runs/latest/01_sync_bag_audit.json` and `.md` exist. | done |
| Check required sync topics | `01_sync_bag_audit.md` covers `/sync/image_raw`, `/sync/imu`, `/sync/imu_batch`, `/imu/pipeline_ready`, `/rosout`. | done |
| Count/rate/monotonic/IMU period | `01_sync_bag_audit.md` reports counts, rates, monotonic flags, and period mean/std. | done |
| Image-nearest-IMU offset stats | `01_sync_bag_audit.md` reports min/p50/p95/max for both bags. | done |
| Static IMU unit check | `01_sync_bag_audit.md` reports acc/gyro norms and unit hints. | done |
| Stage 2 launch supports required args and no hardware | `h30_bag_replay.launch.py` was used with `play_bag`, `sensor_type`, `image_topic`, `imu_topic`, `settings_file`, `cam_imu_time_offset`, `orb_time_offset_mode`, `debug_enable`, `use_rviz`, `use_pangolin`, `rate`, `duration`. | done |
| Stage 2 report | `02_mono_sync_image.md` reports OK entry, first OK time, reset/lost/keyframe/map point/inlier metrics. | done |
| Stop if monocular fails | Not triggered; monocular entered `OK`. | done |
| Stage 3 only two offset groups | `03_sync_offset_test.md` includes exactly 3A and 3B. | done |
| Stage 3 compare requested metrics | `03_sync_offset_test.md` compares imu init, first init time, OK ratio, reset count, insufficient IMU, image-to-last-IMU, inliers, keyframes. | done |
| Stage 4 Tbc/Tcb semantics | `04_tbc_semantics.md` includes YAML matrix, ORB source read path, wrapper transform check, Kalibr direction, and inverse decision. | done |
| Stage 5 only after earlier checks | `05_orbextractor_feature_test.md` follows Stage 1-4 and changes only `nFeatures`. | done |
| Stage 5 max three temporary YAMLs | `config_variants` contains 800, 1200, 1500 variants; 800 and 1200 were replayed, 1500 was generated but not replayed because 1200 already confirmed the hypothesis and Docker approval was blocked. | done |
| Final unique conclusion | `decision.md` gives conclusion 8. | done |

## Verification

- Build validation: `docker exec autoware_env_v2_host ... colcon build --packages-select orb_slam3_ros2 --symlink-install` completed successfully.
- Runtime validation: offline bag replay logs exist for Stage 2, Stage 3A, Stage 3B, Stage 5 nFeatures 800, and Stage 5 nFeatures 1200.
- Parser validation: corresponding JSON summaries exist for all completed replay logs.

## Residual Risk

The diagnosis is complete, but stable runtime is not achieved. The best tested feature setting (`nFeatures=1200`) still ends `RECENTLY_LOST` and has resets. Further work should start from the narrowed feature-count baseline.
