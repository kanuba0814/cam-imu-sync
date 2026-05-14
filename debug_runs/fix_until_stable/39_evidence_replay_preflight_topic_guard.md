# Evidence: replay preflight topic guard

## Change under validation

- `extra_ws/src/ORB_SLAM3_ROS2` commit: `f36b424 test: guard offline replay topic selection`
- File changed:
  - `tools/run_stability_replay.py`

## Purpose

This is a replay-harness safety change only. It does not change ORB-SLAM3 behavior, wrapper runtime behavior, launch defaults, H30 YAML, parser gates, or replay metrics.

The runner now performs local preflight checks before launching ROS:

- bag path exists and contains rosbag2 sqlite files
- selected image topic is `/sync/image_raw`
- selected IMU topic is `/sync/imu` or `/sync/imu_batch`
- selected topics exist in the bag
- forbidden selected topics such as `/image_raw`, `/imu/data_raw`, and `/imu/raw_hw` are rejected
- settings and QoS override files exist
- extra non-replay bag topics are warned about, not treated as fatal
- `--preflight-only` can run these checks without starting ROS

## Fixed bag topics

The fixed bag contains:

```text
1|/sync/imu_batch|sensor_msgs/msg/Imu
2|/sync/image_raw|sensor_msgs/msg/Image
3|/rosout|rcl_interfaces/msg/Log
4|/imu/raw_hw|yesense_interface/msg/ImuRawHw
5|/imu/pipeline_ready|std_msgs/msg/Bool
6|/sync/imu|sensor_msgs/msg/Imu
7|/imu/data_raw|sensor_msgs/msg/Imu
8|/image_raw|sensor_msgs/msg/Image
```

Because `/image_raw` exists in the bag, the replay harness must guard against accidentally selecting it.

## Local validation

Syntax check:

```bash
python3 -m py_compile extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py
```

Default fixed-bag preflight:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --preflight-only --bag-path /home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136
```

Result:

```text
preflight: ignoring non-replay bag topics: /image_raw, /imu/data_raw, /imu/raw_hw
preflight passed for /home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136
```

Forbidden image topic check:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --preflight-only --bag-path /home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136 --image-topic /image_raw
```

Result:

```text
run_stability_replay.py: error: preflight failed: selected forbidden replay topics: ['/image_raw']
```

Forbidden IMU topic check:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --preflight-only --bag-path /home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136 --imu-topic /imu/data_raw
```

Result:

```text
run_stability_replay.py: error: preflight failed: selected forbidden replay topics: ['/imu/data_raw']
```

## Interpretation

The fixed bag remains usable through `/sync/image_raw` and `/sync/imu`, but the runner now fails before launch if someone tries to replay forbidden raw topics. This helps preserve the sync-only ROS2 wrapper validation contract for the next behavioral change.

The next behavior change remains:

```yaml
Camera.fps: 9
```

That change still waits for `autoware_env_v2_host` build and three-run ROS2 wrapper replay.
