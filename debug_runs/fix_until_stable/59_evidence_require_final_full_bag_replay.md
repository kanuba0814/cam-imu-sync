# Evidence: final artifacts require full-bag replay

## Change validated

`generate_final_stability_artifacts.py` now rejects final artifact generation unless preflight `replay_duration_sec` equals `bag_time_span_sec` and every run command includes `duration:=0.0`.

This is a final-artifact provenance guard only. It does not change ROS2 replay behavior, parser thresholds, launch behavior, or SLAM configuration.

## Local validation

Syntax and whitespace checks:

```bash
python3 -m py_compile extra_ws/src/ORB_SLAM3_ROS2/tools/generate_final_stability_artifacts.py
git -C extra_ws/src/ORB_SLAM3_ROS2 diff --check -- tools/generate_final_stability_artifacts.py
```

Accepted synthetic full-bag aggregate:

```text
wrote final artifacts to /tmp/orb_final_duration_tests/out_valid
```

Rejected synthetic truncated replay aggregate:

```text
error: preflight replay duration is not the full bag duration: replay_duration_sec=30.0, bag_time_span_sec=179.79
```

Rejected synthetic aggregate whose command omitted `duration:=0.0`:

```text
error: run 1 command is not the guarded ROS2 wrapper replay path; missing: duration:=0.0
```

Final artifacts therefore cannot be generated from a shortened replay segment.
