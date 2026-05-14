# 00 Git Status Before

## Objective

Continue `goal/orbDebugGoalV2.md`: do not stop at `decision.md`; keep iterating with one minimal explainable change, commit every source change, and validate the fixed sync-only bag with three replays before declaring stability.

## Branches Created

- `extra_ws`: `debug/orb-fix-until-stable`
- `extra_ws/src/ORB_SLAM3_ROS2`: `debug/orb-fix-until-stable`
- `libs/ORB_SLAM3`: `debug/orb-fix-until-stable`

## Command Evidence

### extra_ws

Command: `git -C extra_ws branch --show-current`

```text
debug/orb-fix-until-stable
```

Command: `git -C extra_ws log --oneline -10`

```text
da1c8d3 fix(cam_imu_sync): isolate fixed-rate imu publishing
3b6e844 chore(cam_imu_sync): log received imu rate in sync diagnostics
6ba56cc fix(cam_imu_sync): harden raw imu ingest and resampling
487d918 chore(cam_imu_sync): snapshot deterministic sync work before stability fix
466506d chore: snapshot extra_ws state before cam_imu_sync resampled imu work
be20801 feat(cam_imu_sync): add linear interpolation at frame boundaries
8f0c521 feat(cam_imu_sync): initial commit with delay-based sync
3c68b24 init empty main branch
```

Relevant `git status --short` classification:

- `debug_runs/latest/`: untracked previous V1 diagnostic artifacts. Keep as evidence.
- `debug_runs/fix_until_stable/`: new V2 evidence directory.
- `logs/`: untracked historical runtime logs. Not part of this V2 source change.
- `src/ORB_SLAM3_ROS2/`: nested repo, tracked separately below.
- `tools/h30_sync_bag_audit.py`: untracked previous bag audit helper. Keep as prior diagnostic tooling unless later needed.

### ORB_SLAM3_ROS2

Command: `git -C extra_ws/src/ORB_SLAM3_ROS2 branch --show-current`

```text
debug/orb-fix-until-stable
```

Command: `git -C extra_ws/src/ORB_SLAM3_ROS2 log --oneline -10`

```text
3e3b880 fix(core): add SyncWithImu thread to fix IMU data loss
400c784 fix(config): increase IMU noise params from 2x to 10x safety factor
a5675df feat(launch): add h30_sync_slam for pre-synchronised input
a4eaee7 feat(sync): implement IMU-camera linear interpolation synchronization
0dcfbaf feat(node): add cam_imu_time_offset and ROS topic input support
b25090f feat(launch): add H30 mono SLAM and bag playback launchers
d4358cb feat(config): add rmoncam + H30 IMU calibration configs
03888cc feat(build): improve ORB_SLAM3 discovery and build configuration
9f86dc5 updated ORB_SLAM3 readme, this readme, and visualize
c9c5827 can save images, poses, and point cloud from orb_slam3
```

Command: `git -C extra_ws/src/ORB_SLAM3_ROS2 status --short --untracked-files=all`

```text
 M .gitignore
 M CMakeLists.txt
 M CMakeModules/FindORB_SLAM3.cmake
 M config/Monocular-Inertial/rmoncam_h30.yaml
 M config/bag_qos_override.yaml
 M launch/h30_bag_test.launch.py
 D launch/h30_mono_slam.launch.py
 M launch/h30_sync_slam.launch.py
 M package.xml
 M src/imu_mono_realsense.cpp
?? launch/h30_bag_replay.launch.py
?? launch/h30_pure_mono_slam.launch.py
?? launch/h30_sync_debug_slam.launch.py
?? tools/bag_audit.py
?? tools/extract_rosout.py
?? tools/h30_bag_principle_audit.py
?? tools/imu_visual_correlation.py
?? tools/parse_orb_log.py
?? tools/run_bag_matrix.py
```

Classification:

- `src/imu_mono_realsense.cpp`: previous wrapper diagnostics and sync handling changes; V2 still lacks required queue/timing/pose-gate fields and bounded queues.
- `launch/h30_bag_replay.launch.py`, `tools/parse_orb_log.py`: useful prior replay scaffolding, but V2 requires a stricter `tools/run_stability_replay.py` and expanded parser metrics.
- `tools/run_bag_matrix.py`: broad matrix runner from prior exploration. Do not use for V2 one-variable gates.
- `config/Monocular-Inertial/rmoncam_h30.yaml`: contains prior calibration and feature edits. Treat as candidate config changes requiring replay evidence before becoming final default.
- `h30_mono_slam.launch.py` deletion and extra launch/build/package changes require review before commit.

### libs/ORB_SLAM3

Command: `git -C libs/ORB_SLAM3 branch --show-current`

```text
debug/orb-fix-until-stable
```

Command: `git -C libs/ORB_SLAM3 log --oneline -10`

```text
4452a3c Update Dependencies.md
851db08 Update README.md
0df83dd V1.0: 22nd December 2021
578500b Update README.md
2067374 Update README.md
093173b Readme.md updated
a80b467 V0.4: Beta version, 21 April 2021
ef97841 Updated to V0.3beta
8ac600a Merge pull request #64 from ccamposm/master
ac8de2c Merge pull request #59 from jjgr3496/master
```

Command: `git -C libs/ORB_SLAM3 status --short --untracked-files=all`

```text
 M include/CameraModels/GeometricCamera.h
 M include/CameraModels/KannalaBrandt8.h
 M include/CameraModels/Pinhole.h
 M include/LocalMapping.h
 M include/System.h
 M include/Tracking.h
 M include/TwoViewReconstruction.h
 M src/CameraModels/KannalaBrandt8.cpp
 M src/CameraModels/Pinhole.cpp
 M src/LocalMapping.cc
 M src/System.cc
 M src/Tracking.cc
 M src/TwoViewReconstruction.cc
```

Classification:

- Core diagnostic API and events already exist in the working tree, including `DebugState`, `DebugEvent`, init/reset event logging, and tracking state extraction.
- Some changes also introduce algorithm/tuning knobs such as LocalMapping small-motion reset and Tracking thresholds. These must not be treated as final fixes until the V2 evidence flow proves them.

## Immediate Conclusion

The previous `debug_runs/latest/decision.md` is not sufficient for V2 completion: it identifies low feature count as a primary blocker, but explicitly says the best tested `nFeatures=1200` run still ended `RECENTLY_LOST` with resets. The next step is to preserve useful diagnostics in focused commits, add the missing V2 runtime metrics and safety gates, then rebuild and replay the fixed bag three times.
