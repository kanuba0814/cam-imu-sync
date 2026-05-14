# Evidence: final report metrics table includes reset, lost, and IMU lag gates

## Change validated

`generate_final_stability_artifacts.py` now renders these additional final report columns:

- `Reset last 60s`
- `Max lost streak s`
- `IMU lag p50/p95 ms`

This is report-only output. It does not change replay, parser gates, launch behavior, or SLAM configuration.

## Local validation

Syntax and whitespace checks:

```bash
python3 -m py_compile extra_ws/src/ORB_SLAM3_ROS2/tools/generate_final_stability_artifacts.py
git -C extra_ws/src/ORB_SLAM3_ROS2 diff --check -- tools/generate_final_stability_artifacts.py
```

Synthetic final artifact generation:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/generate_final_stability_artifacts.py /tmp/orb_final_gate_tests/valid.json --output-dir /tmp/orb_final_table_tests/out_valid --kept-commit keep --excluded-hypothesis excluded --risk risk
```

Result:

```text
wrote final artifacts to /tmp/orb_final_table_tests/out_valid
```

Generated replay metrics table excerpt:

```text
| Run | IMU init time | OK ratio | Reset after init | Reset last 60s | Max lost streak s | Final KFs | Median inliers | Median MPs | IMU lag p50/p95 ms | Track p50/p95 ms | Image age p95 ms | Img buf max | Dropped images | ORB FPS p50 | Pose blocked | Invalid pose publishes |
| 1 | 1.0 | 0.95 | 0 | 0 | 1.0 | 21 | 60 | 90 | 5/10 | 20/50 | 100 | 1 | 0 | 9.1 | 1 | 0 |
```

The final report will therefore expose the same reset, lost-state, and IMU-lag gates that the generator independently checks.
