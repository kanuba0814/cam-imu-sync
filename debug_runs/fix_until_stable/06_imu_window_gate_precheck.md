# 06 IMU Window Gate Precheck

## Hypothesis

`goal/orbDebugGoalV2.md` requires `image_to_last_imu_ms` p50/p95 to have no abnormal jumps. The first replay parser reported the metric but did not require it for `stability_pass`.

## Minimal Change

`parse_runtime_orb_log.py` now requires:

- `image_to_last_imu_ms.p95` exists.
- `abs(image_to_last_imu_ms.p95) <= 20.0`.

`run_stability_replay.py` now includes `image_to_last_imu_ms` p50/p95 in aggregate CSV and Markdown output.

## Commit

`extra_ws/src/ORB_SLAM3_ROS2`:

```text
b2de774 test: gate ORB stability on IMU window timing
```

## Local Validation

```bash
python3 -m py_compile \
  extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py \
  extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py
```

Passed.

Smoke test on old `nFeatures=1200` log:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py \
  extra_ws/debug_runs/latest/05_orbextractor_nfeatures_1200.log \
  --output-json /tmp/parse_runtime_1200_v2.json \
  --output-md /tmp/parse_runtime_1200_v2.md \
  --output-csv /tmp/parse_runtime_1200_v2.csv
```

Important output:

- `stability_pass: false`
- `ok_ratio_after_init: 0.2658349328214971`
- `reset_count_after_init: 27`
- `final_keyframes: 2`
- `image_to_last_imu_ms_p50: None`
- `image_to_last_imu_ms_p95: None`

The old log lacks the new `[orb_imu_window]` records, so it cannot pass the V2 stability verifier.

## Remaining Gate

The parser rule is ready, but the real acceptance still requires containerized build and three replays on the fixed bag.
