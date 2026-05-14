# 05 ORBextractor Feature Test

## Hypothesis

After timestamp, IMU unit, monocular image ability, offset comparison, and Tbc direction did not show a hard blocking error, the remaining allowed variable is ORBextractor feature count. The inertial YAML currently uses `ORBextractor.nFeatures: 250`, while the pure monocular YAML that entered `OK` uses `1500`. If feature count is the main bottleneck, raising only `nFeatures` while keeping `iniThFAST=15` and `minThFAST=5` should improve VI initialization.

## Configs

Temporary YAMLs were generated under `debug_runs/latest/config_variants/`:

- `rmoncam_h30_nfeatures_800.yaml`: `nFeatures=800`, `iniThFAST=15`, `minThFAST=5`
- `rmoncam_h30_nfeatures_1200.yaml`: `nFeatures=1200`, `iniThFAST=15`, `minThFAST=5`
- `rmoncam_h30_nfeatures_1500.yaml`: generated but not replayed after 1200 already confirmed the feature-count hypothesis and the Docker approval system blocked the extra run

No RGB, IMU noise, Tbc, timestamp, QoS, or FAST-threshold changes were combined with this test.

## Evidence

| Metric | Baseline 250 | nFeatures 800 | nFeatures 1200 |
| --- | ---: | ---: | ---: |
| imu_initialized | false | true | true |
| first_imu_initialized_frame |  | 906 | 711 |
| OK ratio | 0.025795 | 0.169098 | 0.233715 |
| reset_count | 49 | 36 | 27 |
| late_reset_delta_30s | 8 | 9 | 11 |
| insufficient_imu_count | 2 | 3 | 2 |
| image_to_last_imu_ms p50 | 5.531549 | 5.537629 | 5.531549 |
| median inliers | 31.0 | 44.0 | 48.0 |
| max inliers | 93.0 | 273.0 | 323.0 |
| keyframe count | 3 | 17 | 23 |
| tracked map points max | 131.0 | 273.0 | 323.0 |
| final tracking_state | NOT_INITIALIZED | NOT_INITIALIZED | RECENTLY_LOST |

Parser outputs:

- `debug_runs/latest/03A_sync_offset_zero.json`
- `debug_runs/latest/05_orbextractor_nfeatures_800.json`
- `debug_runs/latest/05_orbextractor_nfeatures_1200.json`

## Gate

PASS for the feature-count hypothesis. Raising only `nFeatures` makes IMU initialization happen and substantially improves OK ratio, keyframes, inliers, and tracked map points. The remaining resets mean the system is not yet stable, but the original 250-feature inertial YAML is a primary blocking factor for this fixed bag.
