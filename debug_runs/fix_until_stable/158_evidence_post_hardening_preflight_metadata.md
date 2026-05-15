# Evidence: Post-Hardening Replay Preflight Metadata

## Purpose

This records the replay preflight metadata after final-gate hardening. It checks
that the next container replay will still use the fixed sync-only bag, selected
sync topics, explicit wrapper pose gates, and a timeout long enough for full-bag
playback.

## Command

Run from `/home/gxxl/slam_ws_v2`:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py \
  --runs 1 \
  --label 30_postinit_inliers0_wrapper_pose_gate_full_window \
  --timeout-sec 210 \
  --min-pose-publish-inliers 15 \
  --min-pose-publish-tracked-mappoints 15 \
  --preflight-only
```

## Result

```text
preflight: ignoring non-replay bag topics: /image_raw, /imu/data_raw, /imu/raw_hw
preflight passed for /home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136
replay_topics: /sync/image_raw,/sync/imu
start_offset_sec: 0.0
```

## Metadata Snapshot

- bag: `/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136`
- selected image topic: `/sync/image_raw`
- selected IMU topic: `/sync/imu`
- replay topics: `/sync/image_raw,/sync/imu`
- QoS override topics: `/sync/image_raw`, `/sync/imu`, `/sync/imu_batch`
- ignored non-replay topics: `/image_raw`, `/imu/data_raw`, `/imu/raw_hw`
- `/sync/image_raw` count: `1668`
- `/sync/image_raw` fps_span: `9.274295544564222`
- `/sync/imu` count: `17980`
- `/sync/imu` fps_span: `100.00003119918655`
- bag_time_span_sec: `179.792912779`
- replay_duration_sec: `179.792912779`
- required_timeout_sec: `196.792912779`
- configured timeout_sec: `210.0`
- start_offset_sec: `0.0`
- settings file:
  `/home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml`
- settings Camera.fps: `9.0`
- QoS override:
  `/home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2/config/bag_qos_override.yaml`

## Conclusion

The current preflight metadata satisfies the final artifact generator's
sync-only latest-bag checks and has enough timeout margin for full-bag replay.
It also satisfies the QoS override topic-name gate. This is not behavior
validation; the required containerized 3-run ROS2 wrapper replay has not run
yet.
