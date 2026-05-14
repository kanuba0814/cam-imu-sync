# Evidence: experiment 25 command path readiness

Purpose:

- Verify the pending container build and replay commands refer to existing
  workspace paths before Docker execution is retried.

Local checks completed at `2026-05-15 06:52 JST`:

- `/home/gxxl/slam_ws_v2/extra_ws` exists.
- `extra_ws/src/ORB_SLAM3_ROS2/package.xml` exists.
- `extra_ws/src/ORB_SLAM3_ROS2/CMakeLists.txt` exists.
- `extra_ws/src/ORB_SLAM3_ROS2/launch/h30_bag_replay.launch.py` exists.
- `extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py` exists and is executable.
- `extra_ws/src/ORB_SLAM3_ROS2/tools/generate_final_stability_artifacts.py` exists.
- `/home/gxxl/slam_ws_v2/libs/ORB_SLAM3` exists.
- `/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136` exists.

Package identity:

```text
extra_ws/src/ORB_SLAM3_ROS2/CMakeLists.txt: project(orb_slam3_ros2)
extra_ws/src/ORB_SLAM3_ROS2/package.xml: <name>orb_slam3_ros2</name>
```

Bag files:

```text
h30_sync_raw_20260512_172136_0.db3
metadata.yaml
```

Interpretation:

- The planned `colcon build --packages-select orb_slam3_ros2` package selector
  matches the package metadata.
- The planned replay command has the required launch file, replay harness, ORB
  core path, and fixed bag path available locally.
- This only validates command path readiness. The actual build and replay still
  must run inside `autoware_env_v2_host`.
