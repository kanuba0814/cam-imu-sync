# 09 Debug Metric Thread Safety

## Hypothesis

The V2 wrapper metrics must be trustworthy during replay. `[orb_queue]` is emitted from image callback, IMU callback, and the tracking thread, but its 1 Hz counters were shared without a mutex. Pose drift baseline values were also updated from both the tracking/debug path and timer publish path.

This could corrupt diagnostic evidence even if SLAM behavior itself is unchanged.

## Minimal Change

`imu_mono_realsense.cpp` now:

- serializes `[orb_queue]` window state with `debug_queue_mutex_`.
- serializes pose baseline/drift state with `debug_pose_mutex_`.
- keeps the change scoped to debug metric state only.

## Commit

`extra_ws/src/ORB_SLAM3_ROS2`:

```text
2f15933 fix: serialize ORB debug metric state updates
```

## Local Validation

```bash
git -C extra_ws/src/ORB_SLAM3_ROS2 diff --check
python3 -m py_compile \
  extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py \
  extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py
```

Both commands passed.

## Remaining Gate

This improves diagnostic reliability but does not prove SLAM stability. Containerized build and three replays are still required.
