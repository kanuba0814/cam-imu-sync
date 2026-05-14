# Evidence: final artifact generator recomputes stability gates

## Change validated

`generate_final_stability_artifacts.py` now independently re-checks the goal-level stability gates from every run's metrics before writing final artifacts. It no longer treats `stability_pass=true` as sufficient by itself.

The added gate checks include IMU initialization, required V2 tags, reset count after init, OK ratio, lost streak, last-60s reset delta, keyframes, median inliers, median tracked map points, IMU lag, processed image age, image queue bound, controlled backlog, and invalid pose publish count.

## Local validation

Syntax and whitespace checks:

```bash
python3 -m py_compile extra_ws/src/ORB_SLAM3_ROS2/tools/generate_final_stability_artifacts.py
git -C extra_ws/src/ORB_SLAM3_ROS2 diff --check -- tools/generate_final_stability_artifacts.py
```

Rejected synthetic aggregate with `stability_pass=true` but reset after init:

```text
error: run 2 does not satisfy final stability gates: reset_count_after_init=1
```

Rejected synthetic aggregate with `stability_pass=true` but OK ratio below threshold:

```text
error: run 1 does not satisfy final stability gates: ok_ratio_after_init=0.89
```

Rejected synthetic aggregate with `stability_pass=true` but invalid pose publish:

```text
error: run 3 does not satisfy final stability gates: invalid_pose_publish_count=1
```

Accepted synthetic aggregate with valid sync-only preflight, ROS2 wrapper commands, and all final gate metrics passing:

```text
wrote final artifacts to /tmp/orb_final_gate_tests/out_valid
```

The older real failed aggregate remains rejected before final artifact generation:

```text
error: aggregate is missing replay preflight metadata
```

This means the next real passing result must come from the current guarded replay runner and satisfy the metric gates, not only carry a passing flag.
