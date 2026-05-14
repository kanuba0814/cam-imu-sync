# Hypothesis: Raise H30 ORB Feature Budget To 1200

## Observation

Replay label `03_after_metric_snapshot_locking` ran 3 times on the fixed bag:

- `run_count=3`, `pass_count=0`, `all_passed=false`
- all runs had `required_v2_tags_present=true`
- all runs had `imu_initialized=false`, `final_keyframes=0`, `ok_ratio_after_init=0.0`
- all runs crashed after ORB printed `New Map created with 94 points`
- each run ended with `double free or corruption (out)` and runner timeout `returncode=124`

The active H30 settings file still has `ORBextractor.nFeatures: 250`.
Earlier evidence in `extra_ws/debug_runs/latest/05_orbextractor_feature_test.md`
showed 250 is the direct failure factor, while 1200 could at least initialize
IMU before later instability.

## Hypothesis

The current default feature budget is too low for this H30 sync-only bag. It
creates a weak initial map around 94 points and enters ORB's initial bundle
adjustment with too little support. Raising only `ORBextractor.nFeatures` from
250 to 1200 should move the replay past the current initialization crash and
recover enough visual support to diagnose the remaining reset/RECENTLY_LOST
problem with the V2 runtime metrics.

## Planned Minimal Change

Change only:

```yaml
ORBextractor.nFeatures: 250
```

to:

```yaml
ORBextractor.nFeatures: 1200
```

in `extra_ws/src/ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml`.

No timestamp, queue, pose gate, IMU noise, or ORB core behavior changes are
included in this round.

## Validation

Replay label `04_h30_features_1200` ran 3 times on the fixed bag after commit
`12cb940` changed the H30 feature budget to 1200:

- `run_count=3`, `pass_count=0`, `all_passed=false`
- all runs had `required_v2_tags_present=true`
- all runs had `imu_initialized=false`, `final_keyframes=0`, `ok_ratio_after_init=0.0`
- `img_buf_size_max` stayed bounded at `0` or `1`
- `invalid_pose_publish_count=0` in all runs
- all runs aborted after ORB printed `New Map created with ... points`
- each run ended with `double free or corruption (out)` and runner timeout `returncode=124`

Initial map point count improved compared with the 250-feature run:

| Replay | Initial Map Points |
| --- | ---: |
| `03_after_metric_snapshot_locking` | 94 |
| `04_h30_features_1200` run 1 | 175 |
| `04_h30_features_1200` run 2 | 161 |
| `04_h30_features_1200` run 3 | 175 |

The feature-budget change improves visual support, but it does not satisfy the
V2 goal and does not get past map-creation memory corruption. The next minimal
change should target unsafe concurrent ORB state access during initial map
creation before continuing reset/RECENTLY_LOST tuning.
