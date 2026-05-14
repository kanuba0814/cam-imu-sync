# Evidence: fixed H30 bag camera rate and ROS 2 wrapper path

## Current validated baseline

The current kept runtime state is still:

- `extra_ws/src/ORB_SLAM3_ROS2` commit: `7a5fe5d Revert "fix: lower H30 preinit inlier gate"`
- Kept config: `LocalMapping.ResetOnSmallMotionBeforeInertialBA2: 0`
- H30 YAML still declares `Camera.fps: 30`

The latest 3-run validation, `14_revert_preinit_inliers_35`, remains failing but is the best current baseline:

| Run | OK ratio after init | Reset after init | Final KFs | Median inliers | Median MPs | Invalid pose publishes |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.6352 | 13 | 21 | 112.0 | 113.0 | 0 |
| 2 | 0.2802 | 12 | 21 | 2.0 | 0.0 | 0 |
| 3 | 0.6364 | 11 | 21 | 124.0 | 125.0 | 0 |

The goal is not achieved: reset count remains nonzero, OK ratio is below 0.90, and one run still collapses to zero median tracked map points.

## Fixed bag evidence

Only the sync-only ROS 2 bag path is allowed:

```text
/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136
```

The relevant topics in the sqlite bag are:

```text
1|/sync/imu_batch|sensor_msgs/msg/Imu
2|/sync/image_raw|sensor_msgs/msg/Image
3|/rosout|rcl_interfaces/msg/Log
5|/imu/pipeline_ready|std_msgs/msg/Bool
6|/sync/imu|sensor_msgs/msg/Imu
```

The fixed replay camera topic is `/sync/image_raw`, topic id `2`. Do not use `/image_raw`, live drivers, or live `cam_imu_sync` for this goal.

Metadata reports total bag duration `179792912779 ns`. Sqlite evidence for topic id `2`:

```text
count=1668
first_ns=1778574427043606216
last_ns=1778574606787716374
fps_span=9.274296
fps_metadata=9.277340
```

Frame interval distribution for `/sync/image_raw`:

```text
min_ms=28.777
avg_ms=107.825
max_ms=305.002
p50_ms=104.937
p95_ms=150.051
```

This fixed bag is a roughly 9.27 Hz image stream, not a 30 Hz stream.

## ORB-SLAM3 setting path

`Camera.fps` is read as an integer in:

```text
libs/ORB_SLAM3/src/Settings.cc:410
```

The setting is then used for frame-window behavior in tracking, including:

```text
libs/ORB_SLAM3/src/Tracking.cc:669
libs/ORB_SLAM3/src/Tracking.cc:1242
libs/ORB_SLAM3/src/Tracking.cc:1670
libs/ORB_SLAM3/src/Tracking.cc:3278
libs/ORB_SLAM3/src/Tracking.cc:3343
```

With `Camera.fps: 30`, ORB's frame-window parameters are inflated by about 3.2x relative to the actual fixed replay cadence.

## ROS 2 wrapper requirement

The validation entrypoint must remain the ROS 2 wrapper path because the final runtime is ROS 2:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 3 --label <label> --timeout-sec 180
```

That runner launches:

```text
ros2 launch orb_slam3_ros2 h30_bag_replay.launch.py
```

So the next config test must be made in `extra_ws/src/ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml`, rebuilt in `autoware_env_v2_host`, then replayed three times through the wrapper.

## Next minimal change

Next candidate change:

```yaml
Camera.fps: 9
```

Rationale:

- nearest integer to the measured fixed-bag rate, because ORB reads `Camera.fps` as `int`
- changes only timing-window behavior
- leaves the kept small-motion reset fix unchanged
- does not combine with inlier threshold, map reset, queue, or IMU parameter changes

Do not apply this change until containerized build and 3-run ROS 2 wrapper replay can be run immediately afterward.
