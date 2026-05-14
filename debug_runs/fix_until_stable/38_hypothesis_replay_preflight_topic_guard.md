# Hypothesis: add replay preflight topic guards

## Observation

The fixed H30 bag contains the required sync topics and also contains extra raw topics:

```text
/sync/imu_batch
/sync/image_raw
/rosout
/imu/raw_hw
/imu/pipeline_ready
/sync/imu
/imu/data_raw
/image_raw
```

The goal allows dependency only on sync replay topics such as `/sync/image_raw` and `/sync/imu`, and explicitly forbids using `/image_raw`. Because the bag physically contains `/image_raw`, a bad command-line override could accidentally replay the forbidden image topic while still using the same bag.

## Minimal change

Change only `tools/run_stability_replay.py` validation:

- add a default preflight check before any ROS launch
- require the selected image topic to be `/sync/image_raw`
- require the selected IMU topic to be `/sync/imu` or `/sync/imu_batch`
- reject selected forbidden topics such as `/image_raw`, `/imu/data_raw`, and `/imu/raw_hw`
- verify selected topics exist in the bag sqlite metadata
- verify settings and QoS override paths exist
- add `--preflight-only` so this check can run without starting ROS
- warn about extra bag topics without rejecting the fixed bag

Do not change ORB-SLAM3 behavior, wrapper runtime behavior, launch defaults, H30 YAML, parser gates, or replay metrics.

## Expected validation

Local checks should show:

- default fixed-bag preflight passes and warns that `/image_raw`, `/imu/data_raw`, and `/imu/raw_hw` are ignored
- `--image-topic /image_raw` is rejected before launch
- `--imu-topic /imu/data_raw` is rejected before launch

The next behavioral step remains `Camera.fps: 9` when containerized replay is available.
