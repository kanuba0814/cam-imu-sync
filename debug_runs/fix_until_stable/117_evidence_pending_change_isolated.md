# Evidence: pending source change isolation

Superseded: this recorded an older pre-permission state where final-gate
hardening was still uncommitted. Current wrapper behavior candidate is already
committed as `61d405e`, and current execution should follow
`141_resume_manifest_after_docker_approval.md`.

## Purpose
Confirm that the current uncommitted source changes are limited to the validated
final-gate hardening and do not already include the next behavior experiment.

## Wrapper repo diff
`git diff --name-only` in `extra_ws/src/ORB_SLAM3_ROS2` currently reports only:

```text
tools/generate_final_stability_artifacts.py
tools/selftest_final_stability_gates.py
```

There is no diff in:

```text
config/Monocular-Inertial/rmoncam_h30.yaml
launch/h30_bag_replay.launch.py
tools/run_stability_replay.py
tools/parse_runtime_orb_log.py
```

## ORB core diff
`git diff --name-only` in `libs/ORB_SLAM3` reports no local changes.

## Status
The pending commit can remain a single-purpose final-gate commit. The next
behavior experiment, `Tracking.ResetActiveMapBeforeInertialBA2: 0`, has not been
applied yet and should be made as a separate committed config change only after
the gate commit is successfully recorded.
