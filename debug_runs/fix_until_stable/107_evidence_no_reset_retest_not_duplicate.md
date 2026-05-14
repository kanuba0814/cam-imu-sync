# Evidence: no-reset retest is not a duplicate of run 18

Superseded: this justified the older experiment 20 branch. Experiment 20 later
failed and is now historical evidence only.

## Question
Before applying `Tracking.ResetActiveMapBeforeInertialBA2: 0` again, confirm
whether the previous failed no-reset experiment already tested the same condition
as the current baseline.

## Old no-reset experiment
`18_pre_ba2_recovery_fps9` failed:

| Run | OK ratio after init | Reset after init | Final KFs | Median inliers | Median MPs |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.13 | 3 | 0 | 0.0 | 0.0 |
| 2 | 0.5006 | 6 | 21 | 40.0 | 32.0 |
| 3 | 0.4718 | 6 | 21 | 42.0 | 1.0 |

The run logs show the active reset setting was disabled, but the extended IMU
reset window was not active:

```text
tracking reset policy: recent_reloc_max_frames=9, reset_active_map_before_inertial_ba2=0, visual_pose_optimization_before_inertial_ba2=0
```

## Current baseline
`19_frames_to_reset_90` also failed, but with much stronger maps and with the
extended IMU reset window active:

| Run | OK ratio after init | Reset after init | Final KFs | Median inliers | Median MPs |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.6890 | 3 | 33 | 166.0 | 166.0 |
| 2 | 0.6890 | 3 | 33 | 169.0 | 169.0 |
| 3 | 0.7712 | 7 | 21 | 116.0 | 117.0 |

The current logs show:

```text
tracking reset policy: recent_reloc_max_frames=9, frames_to_reset_imu=90, reset_active_map_before_inertial_ba2=1, visual_pose_optimization_before_inertial_ba2=0
```

## Conclusion
The next experiment is not a duplicate of `18_pre_ba2_recovery_fps9`. It tests a
new combination:

```text
frames_to_reset_imu=90
reset_active_map_before_inertial_ba2=0
```

That combination must still be treated as an experiment. It must be committed
before validation, built in `autoware_env_v2_host`, and replayed three times
through the ROS2 wrapper. If it fails with long `RECENTLY_LOST`, low OK ratio,
or weak map metrics, revert the config change instead of stacking another YAML
change.
