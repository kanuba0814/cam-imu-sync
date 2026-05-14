# Evidence: experiment 25 launch and config path

Purpose:

- Confirm the pending experiment 25 replay will exercise the ROS2 wrapper path
  only, and will load the current H30 source config candidate.

Launch file inspected:

- `extra_ws/src/ORB_SLAM3_ROS2/launch/h30_bag_replay.launch.py`

Launch behavior:

- Starts `orb_slam3_ros2/imu_mono_node_cpp`.
- Starts `ros2 bag play` only when `play_bag:=true`.
- Does not start a real camera driver.
- Does not start a real IMU driver.
- Does not start `cam_imu_sync`.
- RViz is behind `use_rviz`, and the replay harness default is `false`.
- Default `replay_topics` is `/sync/image_raw,/sync/imu`.
- Default `start_offset` is `0.0`.
- `settings_file` is passed as a wrapper parameter to `imu_mono_node_cpp`.

Current installed config path:

```text
/home/gxxl/slam_ws_v2/extra_ws/install/orb_slam3_ros2/share/orb_slam3_ros2/config/Monocular-Inertial/rmoncam_h30.yaml
-> /home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml
```

Current H30 candidate values:

```yaml
LocalMapping.ResetOnSmallMotionBeforeInertialBA2: 0
LocalMapping.ImuMonoInitMinTime: 4.0
Tracking.FramesToResetIMU: 100000
ORBextractor.nFeatures: 1200
Camera.fps: 9
```

Interpretation:

- A successful experiment 25 replay would be wrapper evidence, not standalone
  ORB-SLAM3 evidence.
- The replay command will not accidentally depend on `/image_raw` unless the
  harness or manual command overrides `replay_topics`.
- Because the installed H30 config resolves to the source config, the committed
  candidate is what the launch default sees after the wrapper install is sourced.

Remaining blocker:

- This is still only launch/config-path evidence. It does not replace the
  required container build and three full ROS2 wrapper replays.
