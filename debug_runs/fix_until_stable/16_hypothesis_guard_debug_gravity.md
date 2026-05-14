# Hypothesis: Guard Debug Gravity Reads Until IMU Initialization

## Observation

Replay label `05_serialized_orb_access` still failed 3/3 after serializing
wrapper-side tracking and timer debug reads:

- `run_count=3`, `pass_count=0`, `all_passed=false`
- all runs had `imu_initialized=false`, `final_keyframes=0`
- all runs aborted after `First KF:0; Map init KF:0` and
  `New Map created with ... points`
- runs 1 and 3 still logged non-finite `gravity_norm` and gravity vector values
  before IMU initialization

Those non-finite values came from debug export reading `LocalMapping::mRwg`
before the active map had completed IMU initialization.

## Minimal Change

Commit `5296c2b` changed ORB-SLAM3 debug export only:

- `System::PushDebugEvent()` records the current map id but fills missing
  gravity/scale from `LocalMapping` only if the current map reports
  `isImuInitialized()`
- `System::GetDebugState()` uses `LocalMapping::mRwg/mScale` only after IMU
  initialization and only if the derived values are finite

No tracker, optimizer, timestamp, queue, feature, or IMU algorithm behavior was
changed.

## Validation

Replay label `06_guard_debug_gravity_until_imu_init` ran 3 times on the fixed
bag:

- `run_count=3`, `pass_count=0`, `all_passed=false`
- runs 2 and 3 had `required_v2_tags_present=true`; run 1 missed at least one
  required tag before the abort path completed
- all runs had `imu_initialized=false`, `final_keyframes=0`, `ok_ratio_after_init=0.0`
- `img_buf_size_max` stayed at `0` or `1`
- `invalid_pose_publish_count=0`
- logs now show initialization-time `estimated_scale=nan` and
  `gravity_norm=nan` instead of `inf`
- all runs still aborted after ORB printed `New Map created with ... points`
- all runs ended with `double free or corruption (out)` and runner timeout
  `returncode=124`

Initial map point counts in this run were:

| Run | Initial Map Points |
| ---: | ---: |
| 1 | 172 |
| 2 | 175 |
| 3 | 161 |

The guard fixed the debug-state undefined read symptom but did not clear the
map-creation crash. The next step should capture an abort stack for the ORB
initial map creation path instead of making another configuration guess.
