# Evidence: no-reset experiment observability

Superseded: this observability note belongs to the older experiment 20
`Tracking.ResetActiveMapBeforeInertialBA2: 0` branch. Experiment 20 failed and
was later excluded. Keep this file as historical evidence only.

## Purpose
Confirm that the next no-reset experiment can be judged from existing logs
without adding another instrumentation-only source change first.

## ORB core evidence
`Tracking::TrackLocalMap()` already pushes an ORB debug event when local-map
tracking fails:

```text
event_code=TRACK_LOCAL_MAP_FAILED
reason=recent_relocalization_low_inliers
reason=imu_mono_low_inliers
reason=imu_mono_low_inliers_before_imu_init
num_matches=<matches before optimization>
num_inliers=<mnMatchesInliers>
```

The pre-BA2 reset branch is the one under test:

```text
if !pCurrentMap->isImuInitialized()
   or (!pCurrentMap->GetIniertialBA2() and reset_active_map_before_inertial_ba2)
then ResetActiveMap()
```

Setting `Tracking.ResetActiveMapBeforeInertialBA2: 0` should suppress only the
second case: initialized IMU map before inertial BA2. It should not suppress
resets before IMU initialization.

## Wrapper evidence
The wrapper logs each tracked frame with:

```text
tracking_state
imu_initialized
reset_count
last_reset_reason
num_inliers
num_tracked_mappoints
num_keyframes
```

It also logs `[orb_event]` records emitted by ORB core.

## Parser evidence
`tools/parse_runtime_orb_log.py` computes:

- `reset_count_after_init`
- `ok_ratio_after_init`
- `max_lost_streak_sec_after_init`
- `reset_delta_last_60_sec`
- final keyframes
- median inliers and tracked map points after init

## Status
The current instrumentation is sufficient for `20_frames90_no_pre_ba2_reset`.
If the no-reset run suppresses resets but creates long `RECENTLY_LOST` streaks,
low OK ratio, or weak map metrics, the parser and per-frame logs should expose
that directly. No additional logging-only source commit is needed before this
one-line config experiment.
