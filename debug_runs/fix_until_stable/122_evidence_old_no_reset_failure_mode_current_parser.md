# Evidence: old no-reset failure mode with current parser

## Purpose
Re-parse the old `18_pre_ba2_recovery_fps9` no-reset experiment with the current
runtime parser. This checks whether the old no-reset failure was behavioral or
mainly caused by runtime process errors.

## Config observed in logs
The old run used:

```text
recent_reloc_max_frames=9
reset_active_map_before_inertial_ba2=0
visual_pose_optimization_before_inertial_ba2=0
```

It did not log `frames_to_reset_imu=90`, so it is not equivalent to the next
planned `20_frames90_no_pre_ba2_reset` experiment.

## Current parser results

| Run | Runtime errors | Reset after init | OK ratio | Max lost streak s | Reset last 60s | Final KFs | Median inliers | Median MPs |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0 | 3 | 0.1300 | 5.0825 | 2 | 0 | 0.0 | 0.0 |
| 2 | 0 | 6 | 0.5006 | 5.0864 | 6 | 21 | 40.0 | 32.0 |
| 3 | 0 | 6 | 0.4718 | 5.0714 | 2 | 21 | 42.0 | 1.0 |

Input-side metrics remained healthy in that run: processed image age p95 stayed
below `18ms`, max image buffer was `1`, controlled backlog passed, and invalid
pose publishes were `0`.

## Conclusion
The old no-reset attempt failed behaviorally, not because of runtime process
errors. It allowed long enough bad-state streaks and weak map metrics to fail the
final gates. The next no-reset retest is still justified only because the current
baseline now includes `Tracking.FramesToResetIMU: 90`.
