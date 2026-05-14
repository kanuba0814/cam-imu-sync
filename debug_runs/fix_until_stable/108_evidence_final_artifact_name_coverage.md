# Evidence: final artifact name coverage

## Purpose
Confirm that the guarded final artifact generator covers both sets of requested
completion files before relying on it after a future passing replay aggregate.

## Required by the goal
The goal text names these final artifacts:

- `best_config.yaml`
- `decision.md`
- `stability_report.md`

The later phase-nine checklist also names:

- `final_stability_report.md`
- `final_patch_summary.md`
- `final_commands.md`

## Current generator behavior
`tools/generate_final_stability_artifacts.py` writes all of those files from a
passing aggregate:

```text
best_config.yaml
final_stability_report.md
stability_report.md
decision.md
final_commands.md
final_patch_summary.md
```

The selftest file also requires the generated output directory to contain all
six names and checks that `best_config.yaml` exactly matches the selected
settings file.

## Status
Artifact naming is not a remaining gap. The remaining completion blocker is
still behavioral: the fixed bag has not yet produced three passing ROS2 wrapper
replays.
