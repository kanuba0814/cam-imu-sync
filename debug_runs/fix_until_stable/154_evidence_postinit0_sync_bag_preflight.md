# Evidence: Post-Init 0 Sync Bag Preflight

## Purpose

This is a local preflight check for the current post-init-0 candidate. It does
not replace the required containerized build or the three full ROS2 wrapper
replays.

## Current Time

- Checked at: `2026-05-15 11:47:49 JST`
- This was still before the Docker approval retry time reported by the runner.

## Latest Bag Pointers

Both latest pointers resolve to the same fixed H30 sync bag:

- `bags/LATEST_BAG.txt`: `/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136`
- `bags/goalDebug/LATEST_BAG.txt`: `/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136`

The bag sqlite file exists:

- `bags/goalDebug/h30_sync_raw_20260512_172136/h30_sync_raw_20260512_172136_0.db3`

## Bag Topics

Topic metadata from sqlite:

| Topic | Type | Count |
| --- | --- | ---: |
| `/image_raw` | `sensor_msgs/msg/Image` | 1666 |
| `/imu/data_raw` | `sensor_msgs/msg/Imu` | 35959 |
| `/imu/pipeline_ready` | `std_msgs/msg/Bool` | 0 |
| `/imu/raw_hw` | `yesense_interface/msg/ImuRawHw` | 35960 |
| `/rosout` | `rcl_interfaces/msg/Log` | 47 |
| `/sync/image_raw` | `sensor_msgs/msg/Image` | 1668 |
| `/sync/imu` | `sensor_msgs/msg/Imu` | 17980 |
| `/sync/imu_batch` | `sensor_msgs/msg/Imu` | 0 |

The replay must use only `/sync/image_raw` and `/sync/imu` for ORB input.
The raw topics exist in the bag but remain forbidden for this goal.

## Harness Defaults

The replay harness still defaults to:

- `--image-topic /sync/image_raw`
- `--imu-topic /sync/imu`
- `--orb-time-offset-mode zero_for_sync`
- `start_offset_sec == 0.0` is enforced

The harness explicitly bans selecting or replaying:

- `/image_raw`
- `/imu/data_raw`
- `/imu/raw_hw`

The harness `--preflight-only` path also passed without launching ROS:

```text
preflight: ignoring non-replay bag topics: /image_raw, /imu/data_raw, /imu/raw_hw
preflight passed for /home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136
replay_topics: /sync/image_raw,/sync/imu
start_offset_sec: 0.0
```

## Candidate Config

The current H30 YAML contains:

- `Camera.fps: 9`
- `ORBextractor.nFeatures: 1200`
- `Tracking.FramesToResetIMU: 100000`
- `Tracking.ResetActiveMapBeforeInertialBA2: 0`
- `Tracking.MinInliersImuMonoPostInit: 0`

The installed H30 config path resolves back to the source YAML, so the installed
launch will read the current candidate config:

```text
extra_ws/install/orb_slam3_ros2/share/orb_slam3_ros2/config/Monocular-Inertial/rmoncam_h30.yaml
-> /home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml
```

The installed `h30_bag_replay.launch.py` also contains the 15/15 wrapper pose
publication gates:

- `min_pose_publish_inliers`
- `min_pose_publish_tracked_mappoints`

## Decision

The local preflight is consistent with the goal constraints and the current
candidate. Validation is still incomplete until the containerized build and
three full ROS2 wrapper replays run successfully.
