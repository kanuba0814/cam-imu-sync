# Evidence: H30 replay launch is wrapper-only

## Purpose
Confirm that `h30_bag_replay.launch.py` satisfies the goal's hard runtime
constraints before using it as the final ROS2 wrapper validation path.

## Launch structure
The launch file starts:

- `orb_slam3_ros2` / `imu_mono_node_cpp`
- optional `ros2 bag play` through `ExecuteProcess` when `play_bag=true`
- optional `rviz2` only when `use_rviz=true`

The file header states that it does not start camera, IMU, or `cam_imu_sync`
drivers. A source scan of the launch file found no `usb_cam`, real IMU driver,
Yesense driver, or `cam_imu_sync` node.

## Replay topics
The launch argument defaults are:

```text
image_topic=/sync/image_raw
imu_topic=/sync/imu
replay_topics=/sync/image_raw,/sync/imu
```

`_bag_actions()` builds:

```text
ros2 bag play <bag_path> --clock --rate <rate> --start-offset <start_offset>
```

and only appends `--topics` for the selected `replay_topics`.

## Gate alignment
`tools/generate_final_stability_artifacts.py` requires final replay commands to
use:

```text
ros2 launch orb_slam3_ros2 h30_bag_replay.launch.py
play_bag:=true
sensor_type:=imu-monocular
image_topic:=/sync/image_raw
imu_topic:=/sync/imu
replay_topics:=/sync/image_raw,/sync/imu
use_rviz:=false
use_pangolin:=false
```

## Status
The launch path satisfies the wrapper-only constraint. The remaining blocker is
not launch composition; it is that the current fixed-bag ROS2 wrapper aggregate
still fails the stability gates.
