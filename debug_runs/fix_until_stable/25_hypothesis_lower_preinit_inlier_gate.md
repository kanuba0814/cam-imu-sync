# Hypothesis: lower H30 pre-init inlier gate

## Observation

With only the small-motion reset disabled, H30 replay still deletes maps before IMU initialization on borderline visual support. ORB-SLAM3 defaults to `Tracking.MinInliersImuMonoPreInit=50`, but the fixed low-motion bag repeatedly has 36-48 inliers immediately before a reset.

This reset happens before the map has enough uninterrupted lifetime to make IMU initialization reliable. Post-init failures with 0-14 inliers are still genuinely bad and should continue to reset for now.

## Minimal change

Use the existing ORB-SLAM3 config hook and add this H30-specific setting:

```yaml
Tracking.MinInliersImuMonoPreInit: 35
```

This keeps the post-init gate unchanged at 15 and keeps recent-loss reset behavior enabled. The value remains stricter than the visual-only default of 30, but it stops deleting pre-init maps that have mid-30s to high-40s inlier support.

## Expected validation signal

The next 3-run replay should show:

- fewer active-map resets before the first stable IMU initialization
- improved OK ratio after init
- more runs with nonzero median tracked map points
- no increase in invalid pose publishes because the ROS 2 wrapper still publishes only when tracking is OK

If reset count remains high but moves mainly to post-init `imu_mono_low_inliers`, the next hypothesis should target IMU initialization quality or recent-relocalization behavior, not wrapper queueing.
