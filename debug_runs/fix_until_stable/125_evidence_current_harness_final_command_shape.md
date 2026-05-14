# Evidence: current harness final command shape

## Purpose
Confirm that the current replay harness will generate commands compatible with
the hardened final artifact gate.

## Preflight
The harness resolved:

```text
bag_path=/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136
replay_topics=/sync/image_raw,/sync/imu
start_offset_sec=0.0
```

It also ignored non-replay bag topics:

```text
/image_raw, /imu/data_raw, /imu/raw_hw
```

## Generated command
The generated command contains the required final-gate arguments:

```text
ros2 launch orb_slam3_ros2 h30_bag_replay.launch.py
bag_path:=/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136
play_bag:=true
sensor_type:=imu-monocular
image_topic:=/sync/image_raw
imu_topic:=/sync/imu
settings_file:=/home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml
cam_imu_time_offset:=0.0
orb_time_offset_mode:=zero_for_sync
debug_enable:=true
debug_runtime_metrics:=true
enable_video_recording:=false
publish_pose_only_when_tracking_ok:=true
max_image_queue_size:=2
max_imu_queue_size:=500
drop_stale_images:=true
max_image_age_ms:=200.0
use_rviz:=false
use_pangolin:=false
rate:=1.0
duration:=0.0
start_offset:=0.0
replay_topics:=/sync/image_raw,/sync/imu
play_delay:=2.0
qos_profile_overrides_path:=/home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2/config/bag_qos_override.yaml
```

## Status
The current harness command shape satisfies the final gate's ROS2 wrapper,
sync-topic, full-bag, and safety-argument requirements. The missing evidence is
still behavioral: three passing wrapper replays do not exist yet.
