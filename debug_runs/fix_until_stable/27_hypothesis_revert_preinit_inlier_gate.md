# Hypothesis: revert pre-init inlier gate change

## Observation

`Tracking.MinInliersImuMonoPreInit: 35` made replay less stable. It increased reset count and removed the one high-map-point run from the previous validation. The lower gate appears to accept weak maps that pass visual pre-init checks but collapse immediately after IMU initialization.

## Minimal change

Revert wrapper commit `060661e fix: lower H30 preinit inlier gate`.

This preserves:

```yaml
LocalMapping.ResetOnSmallMotionBeforeInertialBA2: 0
```

and restores ORB-SLAM3's default:

```text
Tracking.MinInliersImuMonoPreInit = 50
```

## Expected validation signal

The next 3-run replay should recover the previous `12_revert_pre_ba2_recent_loss_reset` profile:

- at least one run with high median tracked map points
- no long `RECENTLY_LOST` streaks
- post-init low-inlier resets may remain, but the all-zero median map-point regression should disappear

After that, the next hypothesis should target a timing/config mismatch instead of weakening the pre-init inlier threshold further.
