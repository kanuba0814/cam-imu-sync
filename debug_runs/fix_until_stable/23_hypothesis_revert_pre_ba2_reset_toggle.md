# Hypothesis: revert pre-BA2 reset-policy toggle

## Observation

`Tracking.ResetActiveMapBeforeInertialBA2: 0` was intended to preserve a useful H30 map across short `RECENTLY_LOST` periods. The fixed bag replay disproved that hypothesis. The three-run evidence shows lower `OK` ratio, zero median tracked map points, and long `RECENTLY_LOST` streaks.

## Minimal change

Revert wrapper commit `bfca09e fix: keep H30 map through pre-BA2 recent loss`.

This keeps the earlier useful H30-specific setting:

```yaml
LocalMapping.ResetOnSmallMotionBeforeInertialBA2: 0
```

It removes only the failed reset-policy override:

```yaml
Tracking.ResetActiveMapBeforeInertialBA2: 0
```

## Expected validation signal

The next fixed-bag replay should return to the `10_disable_small_motion_reset` behavior profile:

- median tracked map points and median inliers should recover in the successful `OK` windows
- long `RECENTLY_LOST` streaks should shrink
- reset count may remain nonzero, but the harmful zero-map-point behavior should disappear

If this is confirmed, the next hypothesis should target the low-inlier tracking failures that still trigger resets, not the pre-BA2 active-map reset policy.
