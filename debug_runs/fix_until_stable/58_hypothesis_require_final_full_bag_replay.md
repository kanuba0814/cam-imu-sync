# Hypothesis: final artifacts must come from full-bag replay

## Observation

The final artifact generator checked timeout coverage and command provenance, but it did not explicitly reject aggregates where `replay_duration_sec` was shorter than `bag_time_span_sec`, nor did it require the run command to contain `duration:=0.0`.

The goal requires stable replay of the fixed bag, not a shortened segment. Final artifacts should therefore be impossible to generate from a truncated replay.

## Minimal change

Only strengthen `generate_final_stability_artifacts.py`:

- require `replay_duration_sec == bag_time_span_sec`
- require each run command to include `duration:=0.0`

Do not change replay, parser gates, launch behavior, or SLAM configuration.

## Expected validation signal

A synthetic full-bag aggregate should still generate final artifacts. A synthetic aggregate with a shorter replay duration or a command missing `duration:=0.0` should be rejected.
