# Hypothesis: match H30 Camera.fps to fixed-bag cadence

## Observation

`rmoncam_h30.yaml` currently has:

```yaml
Camera.fps: 30
```

The fixed ROS 2 replay does not process this bag at 30 FPS. Runtime summaries from `14_revert_preinit_inliers_35` show ORB FPS mostly in the 7-12 range. The wrapper queues are bounded and IMU lag is sane, so this is not an unbounded backlog problem.

ORB-SLAM3 uses camera FPS to derive frame-window behavior such as max frames and recent-relocalization windows. With `Camera.fps=30`, reset-sensitive windows are roughly three times longer than the actual bag cadence. This can make `recent_relocalization_low_inliers` and active-map reset behavior overly sticky for the fixed H30 replay.

## Minimal change

After confirming the exact `/sync/image_raw` bag rate, update only the H30 YAML `Camera.fps` value to match the fixed bag cadence. Candidate range from runtime summaries is 10-11 FPS.

Do not combine this with threshold changes. Keep:

```yaml
LocalMapping.ResetOnSmallMotionBeforeInertialBA2: 0
```

and leave the inlier gates at their defaults.

## Expected validation signal

The next 3-run replay should show:

- fewer recent-relocalization or pre-BA2 reset loops
- higher OK ratio after init
- at least the same two high-map-point runs seen in `14_revert_preinit_inliers_35`
- no invalid pose publishes from the ROS 2 wrapper

If this fails, the next target should be ORB/IMU initialization quality rather than wrapper queueing.
