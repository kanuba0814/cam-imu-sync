# 02 Mono Sync Image

## Hypothesis

If `/sync/image_raw` is a usable visual input, pure monocular ORB-SLAM3 should eventually enter `OK` with nonzero keyframes, tracked map points, and inliers when replaying `h30_sync_only_normal`. If it never enters `OK`, the next work should stay in image encoding, `Camera.RGB`, intrinsics/distortion, or ORB features, not IMU.

## Command

```bash
cd /home/gxxl/slam_ws_v2/extra_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch orb_slam3_ros2 h30_bag_replay.launch.py \
  bag_path:=/home/gxxl/slam_ws_v2/bags/h30_sync_only_normal \
  play_bag:=true sensor_type:=monocular \
  image_topic:=/sync/image_raw imu_topic:=/sync/imu \
  settings_file:=/home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2/config/Monocular/rmoncam.yaml \
  cam_imu_time_offset:=0.0 orb_time_offset_mode:=zero_for_sync \
  debug_enable:=true use_rviz:=false use_pangolin:=false \
  rate:=1.0 duration:=60.0
```

No real camera driver, real IMU driver, or live `cam_imu_sync` node was started.

## Evidence

- log: `debug_runs/latest/02_mono_sync_image.log`
- parsed_json: `debug_runs/latest/02_mono_sync_image.json`
- tracking records: `2032`
- whether entered `OK`: `yes`
- first_ok_frame: `1849`
- first_ok_time: `1778734840.924440622` (`61.608s` after first tracked frame time `1778734779.316136360`)
- OK ratio: `0.090059`
- LOST count: `0`
- RECENTLY_LOST count: `0`
- reset_count: `0`
- max keyframe count: `32`
- final keyframe count: `30`
- tracked map points median/max: `0.0` / `428.0`
- inlier count median/max: `0.0` / `428.0`
- insufficient_imu_count: `0` (pure monocular mode; IMU subscription disabled)

## Gate

PASS. Monocular tracking enters `OK`, so the run is allowed to proceed to the two explicit VI offset tests. The late `first_ok_time` and low whole-window medians are weak image evidence, but they do not trigger the stage-2 stop condition.
