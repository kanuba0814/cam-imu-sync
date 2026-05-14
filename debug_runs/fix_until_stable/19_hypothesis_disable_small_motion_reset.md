# Hypothesis: disable small-motion reset for H30 sync bag

## Observation

After the g2o ABI rebuild, the fixed bag no longer crashes. It reaches IMU initialization, but `LocalMapping` immediately flags `IMU_INIT_FAILED reason=not_enough_motion` and requests active map reset while the visual tracker still reports useful inliers and keyframes.

The reset guard is controlled by existing settings:

- `LocalMapping.ResetOnSmallMotionBeforeInertialBA2`
- `LocalMapping.SmallMotionResetMaxTime`
- `LocalMapping.SmallMotionResetDist`

Current defaults are enabled, `10.0` seconds, and `0.02` meters. The fixed sync bag has very small inter-keyframe translation after scale estimation, so the guard becomes a reset loop instead of a recovery mechanism.

## Minimal change

Add the following H30-specific setting to `config/Monocular-Inertial/rmoncam_h30.yaml`:

```yaml
LocalMapping.ResetOnSmallMotionBeforeInertialBA2: 0
```

This does not alter ORB-SLAM3 core code. It only disables the pre-BA2 small-motion reset for the H30 fixed-bag configuration that is already known to have bounded queues, fresh images, valid IMU timing, and no invalid pose publishing.

## Expected validation signal

The next 3-run replay should show:

- no `ACTIVE_MAP_RESET` growth after IMU init from the small-motion gate
- `reset_count_after_init == 0`
- `ok_ratio_after_init` rising toward the V2 gate
- final keyframes and tracked map points staying nonzero

If tracking remains unstable or pose becomes untrustworthy, this change is not sufficient and the next investigation should focus on post-init visual tracking quality, map-point retention, or IMU/camera calibration rather than allocator/backlog issues.
