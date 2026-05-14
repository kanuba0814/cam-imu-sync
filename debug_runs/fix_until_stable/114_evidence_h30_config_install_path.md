# Evidence: H30 config install path

## Purpose
Confirm that the ROS2 wrapper launch will read the current H30 YAML when the
next one-line config experiment is applied.

## Source install rule
`extra_ws/src/ORB_SLAM3_ROS2/CMakeLists.txt` installs package config files with:

```cmake
install(
  DIRECTORY config/
  DESTINATION share/${PROJECT_NAME}/config
)
```

The H30 replay launch default `settings_file` points through the package share
path:

```text
share/orb_slam3_ros2/config/Monocular-Inertial/rmoncam_h30.yaml
```

## Current install state
The installed config path is a symlink to the source file:

```text
extra_ws/install/orb_slam3_ros2/share/orb_slam3_ros2/config/Monocular-Inertial/rmoncam_h30.yaml
  -> extra_ws/src/ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml
```

## Implication
The next YAML-only experiment should be visible to `h30_bag_replay.launch.py`.
Even so, the goal still requires a committed change and containerized
`orb_slam3_ros2` build before the three ROS2 wrapper replays.
