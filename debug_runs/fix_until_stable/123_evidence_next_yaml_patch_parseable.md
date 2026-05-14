# Evidence: next YAML patch is parseable

Superseded: this syntax check belongs to the older experiment 20
`Tracking.ResetActiveMapBeforeInertialBA2: 0` plan. The current candidate is
experiment 25 with `Tracking.FramesToResetIMU: 100000`.

## Purpose
Before applying the next one-line behavior experiment to source, verify that the
planned H30 YAML setting is accepted by the same OpenCV FileStorage style used
by ORB-SLAM3.

## Temporary file
A temporary copy was created at:

```text
/tmp/rmoncam_h30_no_pre_ba2_reset.yaml
```

Only one line was added after `Tracking.FramesToResetIMU: 90`:

```yaml
Tracking.ResetActiveMapBeforeInertialBA2: 0
```

## OpenCV FileStorage readback
The temporary YAML was opened successfully and key readback showed:

```text
Tracking.FramesToResetIMU: empty=False isInt=True value=90.0
Tracking.ResetActiveMapBeforeInertialBA2: empty=False isInt=True value=0.0
Camera.fps: empty=False isInt=True value=9.0
ORBextractor.nFeatures: empty=False isInt=True value=1200.0
```

## Status
The planned config patch is syntactically safe for ORB-SLAM3's YAML reader. It
has not been applied to source yet; it must remain a separate committed behavior
experiment after the current final-gate hardening commit is recorded.
