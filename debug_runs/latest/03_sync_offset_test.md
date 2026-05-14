# 03 Sync Offset Test

## Hypothesis

Stage 1 measured `/sync/image_raw` to nearest `/sync/imu` p50 within one millisecond on both bags, so the expected better configuration is `cam_imu_time_offset=0.0` with `orb_time_offset_mode=zero_for_sync`. The legacy `-0.01574` run is kept only as the required comparison and should warn if it applies a second offset to sync topics.

## Commands

3A:

```bash
ros2 launch orb_slam3_ros2 h30_bag_replay.launch.py \
  bag_path:=/home/gxxl/slam_ws_v2/bags/h30_sync_only_normal \
  play_bag:=true sensor_type:=imu-monocular \
  image_topic:=/sync/image_raw imu_topic:=/sync/imu \
  settings_file:=/home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml \
  cam_imu_time_offset:=0.0 orb_time_offset_mode:=zero_for_sync \
  debug_enable:=true use_rviz:=false use_pangolin:=false \
  rate:=1.0 duration:=120.0
```

3B:

```bash
ros2 launch orb_slam3_ros2 h30_bag_replay.launch.py \
  bag_path:=/home/gxxl/slam_ws_v2/bags/h30_sync_only_normal \
  play_bag:=true sensor_type:=imu-monocular \
  image_topic:=/sync/image_raw imu_topic:=/sync/imu \
  settings_file:=/home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml \
  cam_imu_time_offset:=-0.01574 orb_time_offset_mode:=legacy_warn \
  debug_enable:=true use_rviz:=false use_pangolin:=false \
  rate:=1.0 duration:=120.0
```

No real camera driver, real IMU driver, or live `cam_imu_sync` node was started.

## Evidence

| Metric | 3A offset=0 | 3B legacy -15.74ms |
| --- | ---: | ---: |
| imu_initialized | false | false |
| first_imu_initialized_time |  |  |
| first_ok_frame | 640 | 985 |
| first_ok_time | 1778734800.508330822 | 1778734812.021690369 |
| OK ratio | 0.025795 | 0.025534 |
| reset_count | 49 | 45 |
| late_reset_delta_30s | 8 | 8 |
| insufficient_imu_count | 2 | 3 |
| image_to_last_imu_ms p50 | 5.531549 | 5.561471 |
| image_to_last_imu_ms max | 15.138149 | 9.999514 |
| median inliers | 31.0 | 30.0 |
| max inliers | 93.0 | 91.0 |
| keyframe count | 3 | 4 |
| tracked map points max | 131.0 | 131.0 |
| final tracking_state | NOT_INITIALIZED | NOT_INITIALIZED |

3B emitted the expected wrapper warning:

```text
ORB is subscribing to synchronized image topic '/sync/image_raw' and still applying cam_imu_time_offset=-0.015740 s before TrackMonocular. This may be a second offset
```

## Gate

Both VI runs fail to initialize IMU. 3A is not clearly better than 3B, and 3B is not clearly better than 3A. Because pure monocular entered `OK`, this does not prove offset is the main cause; proceed to Tbc/Tcb and IMU semantics inspection before any ORB parameter tests.
