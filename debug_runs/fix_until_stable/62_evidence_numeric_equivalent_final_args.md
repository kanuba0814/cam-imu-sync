# Evidence: final command checks accept numeric-equivalent replay args

## Change validated

`generate_final_stability_artifacts.py` now compares numeric run-command arguments by value for:

- `rate`
- `duration`
- `play_delay`

This avoids false rejection of equivalent command spellings while preserving semantic checks. It does not change ROS2 replay behavior, parser thresholds, launch behavior, or SLAM configuration.

## Local validation

Syntax and whitespace checks:

```bash
python3 -m py_compile extra_ws/src/ORB_SLAM3_ROS2/tools/generate_final_stability_artifacts.py
git -C extra_ws/src/ORB_SLAM3_ROS2 diff --check -- tools/generate_final_stability_artifacts.py
```

Accepted synthetic aggregate with numerically equivalent command values:

```text
wrote final artifacts to /tmp/orb_final_numeric_command_tests/out_equiv
```

The accepted command used:

```text
rate:=1
duration:=0
play_delay:=2
```

while preflight recorded:

```text
rate=1.0
replay_duration_sec=bag_time_span_sec
play_delay_sec=2.0
```

Rejected synthetic aggregate with a real numeric mismatch:

```text
error: run 1 command is not the guarded ROS2 wrapper replay path; missing: rate:=1.0
```

The default runner-style command still generates final artifacts:

```text
wrote final artifacts to /tmp/orb_final_numeric_command_tests/out_valid
```
