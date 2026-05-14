# Hypothesis: Serialize ORB Tracking And Debug State Reads

## Observation

Replay label `04_h30_features_1200` still failed 3/3 after raising H30
`ORBextractor.nFeatures` to 1200:

- `run_count=3`, `pass_count=0`, `all_passed=false`
- all runs crashed immediately after ORB printed `New Map created with ... points`
- initial map support improved to 161-175 points, but IMU never initialized
- debug output still reported non-finite gravity values before map initialization

The wrapper timer called `GetDebugState()` under `orbslam3_mutex_`, but the
tracking thread only acquired that mutex after `TrackMonocular()` returned.
That allowed timer-side debug reads to overlap ORB initial map creation.

## Minimal Change

Commit `3b8059d` moved the existing `orbslam3_mutex_` lock so it covers:

- `TrackMonocular(...)`
- copying the returned pose into `Tcw_`

This serialized wrapper-side `TrackMonocular()` calls with timer-side
`GetDebugState()` and pose publishing. No topic, timestamp, feature, IMU, queue,
or ORB core algorithm settings were changed.

## Validation

Replay label `05_serialized_orb_access` ran 3 times on the fixed bag:

- `run_count=3`, `pass_count=0`, `all_passed=false`
- runs 2 and 3 had `required_v2_tags_present=true`; run 1 missed at least one
  required tag before the abort path completed
- all runs had `imu_initialized=false`, `final_keyframes=0`, `ok_ratio_after_init=0.0`
- `img_buf_size_max=1`
- `invalid_pose_publish_count=0`
- all runs aborted after `First KF:0; Map init KF:0` and
  `New Map created with ... points`
- all runs ended with `double free or corruption (out)` and runner timeout
  `returncode=124`

Initial map point counts in this run were:

| Run | Initial Map Points |
| ---: | ---: |
| 1 | 172 |
| 2 | 175 |
| 3 | 175 |

Serializing wrapper-side tracking/debug access did not clear the map-creation
memory corruption. The remaining suspicious debug-only issue is reading
`LocalMapping::mRwg` before IMU initialization; the logs still show non-finite
gravity values in runs 1 and 3. The next minimal change should stop debug
state/event export from reading LocalMapping gravity/scale until the active map
reports IMU initialization.
