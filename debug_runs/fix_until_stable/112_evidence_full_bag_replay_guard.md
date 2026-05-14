# Evidence: full-bag replay guard

## Purpose
Confirm that final validation cannot pass with a partial replay, skipped bag
prefix, or insufficient timeout.

## Replay harness behavior
`tools/run_stability_replay.py` records these preflight fields:

```text
bag_time_span_sec
replay_duration_sec
required_timeout_sec
timeout_sec
rate
start_offset_sec
play_delay_sec
```

The preflight rejects nonzero start offsets:

```text
final stability replay must start at the beginning of the bag
```

When `duration=0.0`, the replay duration is set to the full bag span. The
required timeout is computed from:

```text
play_delay_sec + replay_duration_sec / rate + 15.0
```

and a smaller timeout is rejected before replay.

## Final artifact gate
`tools/generate_final_stability_artifacts.py` repeats the final checks:

- `start_offset_sec` must be `0.0`
- `replay_duration_sec` must equal `bag_time_span_sec`
- `timeout_sec` must be positive
- `timeout_sec` must be at least `required_timeout_sec`
- each replay command must contain `duration:=0.0`
- each replay command must contain `start_offset:=0.0`

## Status
The final replay path is guarded against partial-bag evidence. The current
remaining blocker is behavioral: the latest real ROS2 wrapper replay still does
not pass the stability gates.
