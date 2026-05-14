# Evidence: `Tracking.FramesToResetIMU` settings loader path

Purpose:

- Confirm the H30 YAML value used by experiment 25 is loaded by ORB_SLAM3 core
  and is visible in runtime logs.

Source inspected:

- `/home/gxxl/slam_ws_v2/libs/ORB_SLAM3/src/Tracking.cc`

Loader behavior:

- In IMU modes, `mnFramesToResetIMU` is initialized to `mMaxFrames`.
- The tracking settings loader then reads:

```cpp
mnFramesToResetIMU = readOptionalTrackingInt(
    "Tracking.FramesToResetIMU", mnFramesToResetIMU);
```

- The same startup block prints:

```text
tracking reset policy: ... frames_to_reset_imu=<value> ...
```

Current H30 candidate:

```yaml
Tracking.FramesToResetIMU: 100000
```

Interpretation:

- Experiment 25 replay logs must show `frames_to_reset_imu=100000`.
- If they do not, the replay did not load the intended H30 settings file or
  did not use the rebuilt ORB core/wrapper path.
- This gives a direct first check before interpreting any tracking stability
  metrics.

Remaining blocker:

- This is loader-path evidence only. The required validation remains a
  containerized build and three full ROS2 wrapper replays.
