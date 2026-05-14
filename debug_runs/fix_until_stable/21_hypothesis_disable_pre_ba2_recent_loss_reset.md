# Hypothesis: disable pre-BA2 recent-loss active-map reset

## Observation

After disabling the `LocalMapping` small-motion reset, the replay still fails because `Tracking` resets the active map whenever tracking drops while inertial BA2 has not completed:

```cpp
if(!pCurrentMap->isImuInitialized() ||
    (!pCurrentMap->GetIniertialBA2() && mResetActiveMapBeforeInertialBA2))
{
    mpSystem->ResetActiveMap();
}
```

This policy is reasonable for normal motion, but it is too destructive for the fixed low-motion H30 bag. The map can have more than 100 median tracked map points after IMU init, yet a short low-inlier frame deletes the map because BA2 has not happened.

## Minimal change

Use the existing config hook and add this H30-specific setting:

```yaml
Tracking.ResetActiveMapBeforeInertialBA2: 0
```

This keeps the already-created map through short `RECENTLY_LOST` periods instead of deleting it before BA2. It does not lower tracking inlier thresholds and does not publish invalid poses; the wrapper pose gate remains active.

## Expected validation signal

The next 3-run replay should show:

- lower or zero `reset_count_after_init`
- fewer `NOT_INITIALIZED` samples after IMU init
- higher `ok_ratio_after_init`
- final keyframes and median tracked map points staying above the V2 thresholds

If `RECENTLY_LOST` time grows without reset recovery, the next change should target tracking robustness or relocalization behavior, not reset policy.
