# Debug Metric Snapshot Locking

## Change

- ORB_SLAM3_ROS2 commit: `b58788a fix: snapshot ORB debug summary metrics under locks`.
- `[orb_track]` now logs `pose_drift_m` from a local value captured while
  holding `debug_pose_mutex_`.
- `[orb_summary]` now snapshots pose drift/yaw drift under `debug_pose_mutex_`
  and IMU rate/mean values under a new `debug_imu_stats_mutex_`.
- IMU callback updates the debug IMU counters, mean values, and observed rate
  while holding `debug_imu_stats_mutex_`.

## Rationale

The V2 replay gate depends on terminal metrics to prove queue behavior, timing,
pose gating, and pose trust. Shared debug-only values were previously written
from the IMU or tracking path and read from the timer summary without a common
snapshot lock. That can make evidence noisy or undefined even when the SLAM
algorithm behavior is unchanged.

This change is intentionally limited to debug metric state. It does not change
ORB-SLAM3 thresholds, input timestamps, queue policy, or pose publish gating.

## Local Validation

Commands run from `/home/gxxl/slam_ws_v2`:

```bash
clang-format -style=file -i \
  -lines=858:874 -lines=1002:1033 -lines=1238:1240 -lines=1450:1450 \
  extra_ws/src/ORB_SLAM3_ROS2/src/imu_mono_realsense.cpp
git -C extra_ws/src/ORB_SLAM3_ROS2 diff --check -- \
  src/imu_mono_realsense.cpp
rg -n \
  "debug_last_pose_drift_m_|debug_last_pose_yaw_drift_rad_|observed_imu_rate_hz_|debug_gyro_mean_|debug_acc_mean_|debug_imu_total_count_|debug_imu_window_count_" \
  extra_ws/src/ORB_SLAM3_ROS2/src/imu_mono_realsense.cpp
```

The remaining references are either protected by the new/same mutex, are
member declarations, or are in `check_imu_rate_yaml_consistency()`, which is
called only from the IMU callback while `debug_imu_stats_mutex_` is held.

## Status

Container build and fixed-bag replay remain required. This patch only improves
the reliability of runtime evidence that the replay parser will consume.
