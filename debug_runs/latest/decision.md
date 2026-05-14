# Decision

唯一结论：`8. 上述全部排除后，ORBextractor 特征数过低是主要原因。`

## Basis

- Sync-only bag is valid for this goal. `/image_raw` was intentionally not required or read.
- `/sync/image_raw` is healthy: normal bag `5396` frames at `30.012Hz`; noMove bag `594` frames at `30.017Hz`; header stamps are monotonic.
- `/sync/imu` is healthy: normal bag `17978` samples at `99.989Hz`; noMove bag `1980` samples at `100.000Hz`; header stamps are monotonic.
- Sync time domain is already aligned: normal `image - nearest imu` p50 `-0.289ms`, p95 `3.956ms`; noMove p50 `0.602ms`, p95 `4.642ms`.
- Static IMU units are correct enough for ORB input: acc norm mean about `9.752m/s^2`, gyro norm mean about `0.004rad/s`.
- Pure monocular `/sync/image_raw` entered `OK`, so the image stream is usable, though it initialized late.
- Offset comparison did not identify offset as the main cause: both `offset=0` and legacy `-15.74ms` failed IMU initialization with nearly identical OK ratio around `0.026`.
- Tbc/Tcb direction is not the hard error: ORB-SLAM3 expects camera-to-body/IMU for `IMU.T_b_c1`, and the current YAML uses Kalibr `T_ic` / cam0-to-imu0, not the camchain `T_cam_imu` matrix.
- The original inertial YAML uses only `ORBextractor.nFeatures: 250`. Raising only `nFeatures` to `800` and `1200`, while keeping `iniThFAST=15` and `minThFAST=5`, changed the result from no IMU initialization to `imu_initialized=true`.

## Key Comparison

| Metric | Baseline 250 | nFeatures 800 | nFeatures 1200 |
| --- | ---: | ---: | ---: |
| imu_initialized | false | true | true |
| first_imu_initialized_frame |  | 906 | 711 |
| OK ratio | 0.025795 | 0.169098 | 0.233715 |
| reset_count | 49 | 36 | 27 |
| median inliers | 31.0 | 44.0 | 48.0 |
| max inliers | 93.0 | 273.0 | 323.0 |
| keyframe count | 3 | 17 | 23 |
| tracked map points max | 131.0 | 273.0 | 323.0 |

## Caveat

This diagnosis identifies the primary blocker, not a finished stable tuning. Even `nFeatures=1200` still ends `RECENTLY_LOST` and has resets, so follow-up work should tune for stability from this narrowed baseline rather than returning to timestamp, unit, offset, or Tbc hypotheses.
