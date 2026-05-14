# Hypothesis: add a guarded final stability artifact generator

## Observation

The goal requires final artifacts after a stable solution is found:

- `best_config.yaml`
- `decision.md`
- `stability_report.md`
- `final_stability_report.md`
- `final_patch_summary.md`
- `final_commands.md`

The current repeated replay path writes per-label JSON/CSV/Markdown summaries, but it does not have a guarded generator for the final goal artifacts. If a later replay passes all stability gates, the missing final artifact step could still block completion.

## Minimal change

Add a validation-only tool that:

- reads a `run_stability_replay.py` aggregate JSON
- refuses to generate final artifacts unless at least 3 runs exist and every run has `stability_pass=true` with return code `0`
- copies the validated settings YAML to `best_config.yaml`
- writes final report, decision, commands, and patch summary files

This does not change ORB-SLAM3 behavior, ROS wrapper behavior, launch defaults, H30 YAML, or replay parsing.

## Expected validation

Local tests should show:

- existing failed aggregate `14_revert_preinit_inliers_35.json` is rejected
- a synthetic passing aggregate in `/tmp` is accepted and writes all final artifact names

The behavioral next step remains the H30 `Camera.fps: 9` config test when Docker replay is available.
