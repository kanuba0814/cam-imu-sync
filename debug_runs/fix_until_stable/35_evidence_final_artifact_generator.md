# Evidence: guarded final stability artifact generator

## Change under validation

- `extra_ws/src/ORB_SLAM3_ROS2` commit: `9d6b43f test: add guarded final stability artifact generator`
- Files changed:
  - `tools/generate_final_stability_artifacts.py`
  - `CMakeLists.txt`

## Purpose

This is a validation/tooling change only. It does not change ORB-SLAM3 behavior, wrapper runtime behavior, launch defaults, or H30 YAML.

The new generator writes final goal artifacts only from a fully passing replay aggregate:

- `best_config.yaml`
- `decision.md`
- `stability_report.md`
- `final_stability_report.md`
- `final_patch_summary.md`
- `final_commands.md`

It refuses to write final artifacts unless:

- at least three runs are present
- aggregate `all_passed=true`
- `pass_count` equals run count
- every run has `stability_pass=true`
- every run has `returncode=0`
- every run has `controlled_backlog_pass=true`
- all final-report metric fields are present, including ORB processed FPS
- kept commits, excluded hypotheses, and risks are explicitly supplied

## Local validation

Syntax check:

```bash
python3 -m py_compile extra_ws/src/ORB_SLAM3_ROS2/tools/generate_final_stability_artifacts.py
```

Expected rejection against the current failed aggregate:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/generate_final_stability_artifacts.py extra_ws/debug_runs/fix_until_stable/14_revert_preinit_inliers_35.json --output-dir /tmp/orb_final_fail_test --kept-commit 'test commit reason' --excluded-hypothesis 'test excluded hypothesis' --risk 'test risk'
```

Result:

```text
error: aggregate is not fully passing: pass_count=0, runs=3, all_passed=False
```

Expected rejection against a synthetic old-format passing aggregate without ORB processed FPS:

```text
error: run 1 is missing final report metrics: orb_processed_fps_est.p50
```

Expected success against a synthetic new-format passing aggregate:

```text
wrote final artifacts to /tmp/orb_final_pass_test_v3
```

Generated files:

```text
best_config.yaml
decision.md
final_commands.md
final_patch_summary.md
final_stability_report.md
stability_report.md
```

The generated synthetic report included non-null `ORB FPS p50` values in the metrics table.

## Interpretation

The final artifact step is now guarded against false completion. It cannot turn the current failed `14_revert_preinit_inliers_35` replay into a final report.

The next behavior change remains the single H30 config edit:

```yaml
Camera.fps: 9
```

That edit must still wait until `autoware_env_v2_host` build and three-run ROS2 wrapper replay can run immediately afterward.
