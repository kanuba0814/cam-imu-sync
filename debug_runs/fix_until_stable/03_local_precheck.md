# 03 Local Precheck

## Purpose

Run non-authoritative local checks while container access is blocked. These checks do not replace the required `autoware_env_v2_host` build/replay validation.

## ORB_SLAM3 Host Build Attempt

Command:

```bash
cd /home/gxxl/slam_ws_v2/libs/ORB_SLAM3
./build.sh
```

Result: failed on host dependencies/toolchain before validating the modified ORB core files.

Observed blockers:

- `Thirdparty/DBoW2` failed because the host lacks `boost/serialization/serialization.hpp`.
- `Thirdparty/Sophus` failed because host GCC 15 treats Eigen/Sophus array-bounds warnings as errors in Sophus tests.
- Main `ORB_SLAM3` CMake configure failed because host CMake could not find `PangolinConfig.cmake`.

Interpretation: this host is not the authoritative runtime/build environment for this workspace. This is consistent with the workspace rule that ROS and required libraries live inside `autoware_env_v2_host`.

## Wrapper Syntax Precheck Attempt

Command used the existing `extra_ws/build/orb_slam3_ros2/compile_commands.json` entry and converted it to `-fsyntax-only`.

Result: failed immediately because the host has no `/opt/ros/humble` installation:

```text
fatal error: geometry_msgs/msg/detail/transform_stamped__struct.hpp: No such file or directory
ls: cannot access '/opt/ros': No such file or directory
```

Interpretation: no useful wrapper syntax conclusion can be drawn on the host.

## Parser Smoke Test

Command:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py \
  extra_ws/debug_runs/latest/05_orbextractor_nfeatures_1200.log \
  --output-json /tmp/parse_runtime_1200.json \
  --output-md /tmp/parse_runtime_1200.md \
  --output-csv /tmp/parse_runtime_1200.csv
```

Result: parser ran successfully on the old 1200-feature log.

Important parsed result:

- `stability_pass: false`
- `imu_initialized: true`
- `ok_ratio_after_init: 0.2658349328214971`
- `reset_count_after_init: 27`
- `reset_delta_last_60_sec: 17`
- `tracking_state: RECENTLY_LOST`
- `final_keyframes: 2`
- `median_tracked_map_points_after_init: 0.0`
- New V2 tags are absent in this old log: `queue=0`, `timing=0`, `imu_window=0`, `pose_gate=0`, `visual_quality=0`.

This confirms the parser path works and again confirms the prior `decision.md` state is not stable.

## Next Required Step

Do not declare completion. Once Docker access is available, run the required container validation:

```bash
docker exec -it autoware_env_v2_host bash
cd /home/gxxl/slam_ws_v2/libs/ORB_SLAM3 && ./build.sh
cd /home/gxxl/slam_ws_v2/extra_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
export ORB_SLAM3_ROOT_DIR=/home/gxxl/slam_ws_v2/libs/ORB_SLAM3
colcon build --packages-select orb_slam3_ros2 --symlink-install
python3 src/ORB_SLAM3_ROS2/tools/run_stability_replay.py \
  --runs 3 \
  --bag-path /home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136 \
  --settings-file /home/gxxl/slam_ws_v2/extra_ws/debug_runs/latest/config_variants/rmoncam_h30_nfeatures_1200.yaml \
  --label 02_replay_baseline_after_wrapper_fixes
```
