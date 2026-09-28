# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workspace Overview

This is a multi-repo SLAM/simulation research environment, not a single ROS 2 package. Key sub-workspaces:

- `extra_ws/src/ORB_SLAM3_ROS2/` — Custom ROS 2 packages: ORB-SLAM3 wrapper, camera-IMU sync, IMU TF broadcaster
- `autoware/` — Autoware Universe meta-repository (130+ packages via `.repos` import)
- `carla/` — CARLA simulator binary (UE4.26, do not build from source)
- `libs/` — Third-party C++ libraries (ORB_SLAM3, Pangolin)
- `autoware-contents/` — Maps and large data assets

## Build Commands

> **Containerized environment**: ROS 2 Humble / Autoware run inside the Docker container
> `autoware_env_v2_host` — enter it with the `aw-host-start` shell function before building or running
> (the `colcon` commands below run *inside* that container, never on the host). `bk/` (a sibling dir
> under `~/`) holds backup data mounted into the container, e.g. `bk/home` → container `/home`.

Run commands from within the relevant sub-workspace:

```bash
# Build ORB_SLAM3 C++ library (required before building ROS 2 package)
cd extra_ws/src/ORB_SLAM3_ROS2/ORB_SLAM3 && ./build.sh

# Build custom ROS 2 packages
cd extra_ws && colcon build --packages-select orb_slam3_ros2

# Test + lint custom packages (lint failures are blocking)
cd extra_ws && colcon test --packages-select orb_slam3_ros2 && colcon test-result --verbose

# Import and build Autoware
cd autoware && vcs import src < repositories/autoware.repos
cd autoware && colcon build --mixin debug compile-commands

# Run Autoware pre-commit checks
cd autoware && pre-commit run -a

# Start CARLA simulator
cd carla && ./CarlaUE4.sh                         # windowed
cd carla && ./CarlaUE4.sh -RenderOffScreen         # headless
```

## Architecture

### extra_ws ROS 2 Packages

**`orb_slam3_ros2`** (C++14, ament_cmake) — Main SLAM package
- `imu_mono_realsense.cpp` — Primary SLAM node (monocular-inertial). Accepts `/sync/image_raw` + `/sync/imu`, publishes camera pose and point cloud. Vocabulary file resolved automatically from multiple paths including `libs/ORB_SLAM3/Vocabulary/ORBvoc.txt`.
- `orb_camera_info.cpp` — Reads YAML camera config and publishes `sensor_msgs/CameraInfo`
- `visualize.cpp` — Visualization helper
- Settings YAML files in `config/Monocular-Inertial/` (per-camera intrinsics, ORB detector params)

**`cam_imu_sync`** (Python) — Subscribes `/image_raw` + `/imu/data_raw`, re-publishes to `/sync/image_raw` + `/sync/imu` with Kalibr-calibrated time offset applied.

**`imu_tf_broadcaster`** (Python) — Broadcasts `imu_frame_id` → `world_frame_id` transforms from IMU data.

### Launch Files (`extra_ws/src/ORB_SLAM3_ROS2/launch/`)

| File | Scenario |
|------|----------|
| `mapping.launch.py` | Live RealSense D435i + ORB-SLAM3 + RViz |
| `h30_sync_slam.launch.py` | Pre-synced H30 camera/IMU input |
| `h30_mono_slam.launch.py` | Monocular-only (no IMU) |
| `bag_orb.launch.py` | Offline rosbag replay |
| `cam_imu_sync.launch.py` | Sync node standalone |
| `rtabmap.launch.py` | RTABMap integration |

### Output Artifacts

Generated at runtime; excluded from commits:
- `extra_ws/src/ORB_SLAM3_ROS2/clouds/` — Saved point clouds
- `extra_ws/src/ORB_SLAM3_ROS2/occupancy_grids/` — Saved 2D maps
- `extra_ws/src/ORB_SLAM3_ROS2/database_outputs/` — ORB-SLAM3 map databases
- `build/`, `install/`, `log/` — Colcon build artifacts

## Coding Style

- **C++**: `clang-format` with nearest `.clang-format` file
- **Python (autoware/)**: Black + isort (profile `black`) + flake8 (`max-line-length = 100`)
- **ROS names**: snake_case for nodes and targets (e.g., `imu_mono_node_cpp`, `orb_camera_info_node`)
- **Launch/config names**: descriptive and behavior-matching (e.g., `mapping.launch.py`, `bag_qos_override.yaml`)

## Commit Guidelines

- Commit inside the correct nested repo:
  ```bash
  git -C autoware ...
  git -C extra_ws/src/ORB_SLAM3_ROS2 ...
  ```
- `autoware/` uses Conventional Commits: `feat(scope): ...`, `fix(scope): ...`, `chore: ...`
- One functional change per commit; reference issue IDs when available
- PRs must include: purpose, changed paths, validation commands run, and screenshots/logs for visualization changes

## Key External Dependencies

- ROS 2 Humble
- ORB_SLAM3 library at `libs/ORB_SLAM3/` (with DBoW2, g2o, Sophus)
- Pangolin at `libs/Pangolin/`
- OpenCV, PCL, tf2_ros, cv_bridge, image_transport
- `nav2_map_server` (optional, enables map saving on shutdown)
- `realsense2` (optional, enables `orb_alt` executable)

## Sub-module Documentation

- CARLA-specific details: [`carla/CLAUDE.md`](carla/CLAUDE.md)
