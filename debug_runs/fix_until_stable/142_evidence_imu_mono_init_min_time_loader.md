# Evidence: `LocalMapping.ImuMonoInitMinTime` settings loader path

Purpose:

- Confirm the H30 YAML value used by experiment 25 is loaded by ORB_SLAM3 core
  and can be verified in replay logs.

Source inspected:

- `/home/gxxl/slam_ws_v2/libs/ORB_SLAM3/src/LocalMapping.cc`
- `/home/gxxl/slam_ws_v2/libs/ORB_SLAM3/include/LocalMapping.h`

Loader behavior:

- `mImuMonoInitMinTime` defaults to `2.0f`.
- If the settings file contains `LocalMapping.ImuMonoInitMinTime`, the
  constructor reads it:

```cpp
if(!fsSettings["LocalMapping.ImuMonoInitMinTime"].empty())
    mImuMonoInitMinTime = static_cast<float>(
        fsSettings["LocalMapping.ImuMonoInitMinTime"]);
```

- The constructor prints the policy line including:

```text
ImuMonoInitMinTime: <value>
```

Runtime behavior:

- `InitializeIMU()` uses `mImuMonoInitMinTime` as the monocular IMU minimum
  initialization time before allowing inertial initialization to start.

Current H30 candidate:

```yaml
LocalMapping.ImuMonoInitMinTime: 4.0
```

Interpretation:

- Experiment 25 replay logs must show `ImuMonoInitMinTime: 4`.
- If they do not, the replay did not load the intended H30 settings file or did
  not use the rebuilt ORB core/wrapper path.
- This log check pairs with `frames_to_reset_imu=100000` as the first
  configuration-load sanity check before interpreting stability metrics.

Remaining blocker:

- This is loader-path evidence only. The required validation remains a
  containerized build and three full ROS2 wrapper replays.
