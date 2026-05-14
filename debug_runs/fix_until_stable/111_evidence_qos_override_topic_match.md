# Evidence: QoS override topic match

## Purpose
Confirm that the rosbag2 QoS override file uses exact topic names from the fixed
H30 bag and that final replay uses only the sync topics required by the goal.

## Bag topics
The fixed bag topic table contains:

```text
/image_raw
/imu/data_raw
/imu/pipeline_ready
/imu/raw_hw
/rosout
/sync/image_raw
/sync/imu
/sync/imu_batch
```

## QoS override topics
`config/bag_qos_override.yaml` defines exact entries for:

```text
/sync/imu
/sync/image_raw
/sync/imu_batch
```

These names exactly match the sync topic names in the bag.

## Replay selection
`tools/run_stability_replay.py --preflight-only --timeout-sec 210` reported:

```text
preflight passed for /home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136
replay_topics: /sync/image_raw,/sync/imu
start_offset_sec: 0.0
```

It also reported that non-replay topics are ignored:

```text
/image_raw, /imu/data_raw, /imu/raw_hw
```

## Gate alignment
The launch file appends `--qos-profile-overrides-path` to `ros2 bag play` when a
path is provided, and the final artifact gate requires the replay command's
`qos_profile_overrides_path` to match the preflight metadata.

## Status
QoS topic naming is covered for the ROS2 wrapper replay path. This does not
complete the goal by itself; the fixed bag still needs three passing wrapper
replays after the next committed behavior change.
