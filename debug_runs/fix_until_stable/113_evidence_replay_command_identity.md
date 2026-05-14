# Evidence: replay command identity

## Purpose
Confirm that the new final gate requiring identical replay commands is compatible
with the actual replay harness output.

## Existing aggregate check
The latest real aggregate, `19_frames_to_reset_90.json`, contains three replay
runs. The commands recorded in those three runs are identical:

```json
{
  "run_count": 3,
  "unique_command_count": 1,
  "all_passed": false,
  "pass_count": 0
}
```

This aggregate still fails behaviorally, but it shows that the harness naturally
records one stable command across repeated runs.

## Harness behavior
`tools/run_stability_replay.py` builds the launch command once per run from the
same parsed arguments:

```text
command = launch_command(args, bag_path)
summary["run_index"] = run_index
summary["elapsed_wall_sec"] = elapsed
summary["command"] = command
```

The run index and elapsed wall time differ by run, but the replay command should
not differ unless the operator changes arguments between runs or the harness is
modified incorrectly.

## Status
The identical-command final gate is compatible with normal harness output. It is
expected to reject mixed-argument final evidence while accepting real repeated
wrapper replays with one fixed command.
