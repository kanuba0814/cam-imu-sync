# Hypothesis: expose replay return codes in aggregate summaries

## Observation

`run_stability_replay.py` stores each replay run's `returncode` in per-run JSON and uses it for aggregate `all_passed`. However, the aggregate Markdown and CSV tables do not show `returncode`.

The current failed runs often end with return code `124` because the timeout wrapper stops the launch after the evidence window. Hiding this field in the summary makes completion auditing weaker because a reader has to inspect per-run JSON to confirm process status.

## Minimal change

Change only `run_stability_replay.py` aggregate rendering:

- add `returncode` to aggregate CSV
- add `returncode` to aggregate Markdown

Do not change stability gates, parser logic, ORB behavior, wrapper behavior, launch defaults, or H30 YAML.

## Expected validation

Re-rendering the existing `14_revert_preinit_inliers_35` summaries should keep `pass_count=0` and `all_passed=false`, while the Markdown/CSV expose `returncode=124` for each run.
