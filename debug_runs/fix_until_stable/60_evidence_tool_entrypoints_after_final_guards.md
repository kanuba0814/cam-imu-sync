# Evidence: tool entrypoints still load after final artifact guards

## Scope

After the final artifact generator guards were tightened for preflight, command provenance, settings consistency, and full-bag duration, the Python tooling entrypoints were checked locally before the next behavior change.

This is syntax and CLI-entrypoint evidence only. It does not change replay behavior, parser thresholds, launch behavior, or SLAM configuration.

## Validation

Syntax check:

```bash
python3 -m py_compile extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py extra_ws/src/ORB_SLAM3_ROS2/tools/generate_final_stability_artifacts.py
```

Result: exit code `0`.

Replay runner CLI help:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --help
```

Result: exit code `0`; options include `--bag-path`, `--runs`, `--label`, `--image-topic`, `--imu-topic`, `--settings-file`, `--rate`, `--duration`, `--play-delay`, `--qos-profile-overrides-path`, `--preflight-only`, and `--timeout-sec`.

Final artifact generator CLI help:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/generate_final_stability_artifacts.py --help
```

Result: exit code `0`; options include `aggregate_json`, `--settings-file`, `--output-dir`, `--min-runs`, `--kept-commit`, `--excluded-hypothesis`, and `--risk`.

The next real behavior change remains the one-line H30 YAML `Camera.fps: 9` change followed by containerized build and three full fixed-bag ROS2 wrapper replays.
