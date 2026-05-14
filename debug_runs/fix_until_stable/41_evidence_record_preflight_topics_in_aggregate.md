# Evidence: replay preflight topics recorded in aggregate summaries

## Change under validation

- `extra_ws/src/ORB_SLAM3_ROS2` commit: `120040c debug: record replay preflight topics in summaries`
- File changed:
  - `tools/run_stability_replay.py`

## Purpose

This is a replay-harness evidence change only. It does not change ORB-SLAM3 behavior, wrapper runtime behavior, launch defaults, H30 YAML, parser gates, or replay commands.

The runner now records preflight metadata in aggregate JSON and Markdown:

- bag topics discovered from rosbag2 sqlite metadata
- selected image and IMU topics
- ignored non-replay bag topics
- settings file checked before launch
- QoS override file checked before launch

## Local validation

Syntax check:

```bash
python3 -m py_compile extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py
```

Default fixed-bag preflight still passes:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --preflight-only --bag-path /home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136
```

Forbidden topic still fails:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --preflight-only --bag-path /home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136 --image-topic /image_raw
```

Result:

```text
run_stability_replay.py: error: preflight failed: selected forbidden replay topics: ['/image_raw']
```

Re-rendered an aggregate from the existing `14_revert_preinit_inliers_35` replay logs under `/tmp/orb_aggregate_preflight_test2`.

Aggregate JSON now contains:

```json
{
  "pass_count": 0,
  "all_passed": false,
  "preflight": {
    "bag_topics": [
      "/image_raw",
      "/imu/data_raw",
      "/imu/pipeline_ready",
      "/imu/raw_hw",
      "/rosout",
      "/sync/image_raw",
      "/sync/imu",
      "/sync/imu_batch"
    ],
    "ignored_bag_topics": [
      "/image_raw",
      "/imu/data_raw",
      "/imu/raw_hw"
    ],
    "selected_topics": {
      "image": "/sync/image_raw",
      "imu": "/sync/imu"
    }
  }
}
```

Aggregate Markdown now includes:

```text
- selected_image_topic: `/sync/image_raw`
- selected_imu_topic: `/sync/imu`
- ignored_bag_topics: `/image_raw, /imu/data_raw, /imu/raw_hw`
- pass_count: `0`
- all_passed: `False`
```

## Interpretation

The replay summary now proves the sync-only topic selection in the same artifact that reports pass/fail metrics. The known failed baseline remains failed.

The next behavior change remains:

```yaml
Camera.fps: 9
```

That change still waits for `autoware_env_v2_host` build and three-run ROS2 wrapper replay.
