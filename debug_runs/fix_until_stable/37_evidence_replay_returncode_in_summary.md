# Evidence: replay return codes in aggregate summaries

## Change under validation

- `extra_ws/src/ORB_SLAM3_ROS2` commit: `fe5ce23 debug: include replay return codes in stability summaries`
- File changed:
  - `tools/run_stability_replay.py`

## Purpose

This is a validation-tooling change only. It does not change ORB-SLAM3 behavior, wrapper runtime behavior, launch defaults, H30 YAML, parser gates, or replay commands.

The aggregate CSV/Markdown now exposes each replay process return code. `all_passed` already required `returncode=0`; this change makes that evidence visible in the summary artifacts.

## Local validation

Syntax check:

```bash
python3 -m py_compile extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py
```

Re-rendered an aggregate from the existing `14_revert_preinit_inliers_35` replay logs under `/tmp/orb_aggregate_returncode_test`.

Result:

```text
pass_count=0
all_passed=false
returncodes=[124, 124, 124]
```

The generated Markdown table begins with:

```text
| Run | Return | Pass | V2 Tags | IMU Init | ...
| 1 | 124 | False | True | True | ...
| 2 | 124 | False | True | True | ...
| 3 | 124 | False | True | True | ...
```

The generated CSV also includes `returncode` as the second column.

## Interpretation

The summary artifacts now expose process-level replay status alongside the stability metrics. The known failed baseline remains failed. This does not change the next behavioral step:

```yaml
Camera.fps: 9
```

That change still waits for `autoware_env_v2_host` build and three-run ROS2 wrapper replay.
