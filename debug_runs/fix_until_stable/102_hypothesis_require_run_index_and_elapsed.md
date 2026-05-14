# Hypothesis: require run index sequence and elapsed time in final aggregate

The goal requires at least three consecutive wrapper replays. The final
generator already checks aggregate count and pass status, but it should also
verify the per-run metadata written by `run_stability_replay.py`:

- `run_index` must match the 1-based run order in the aggregate.
- `elapsed_wall_sec` must be present and positive.

Expected fix:
- Add these checks to `generate_final_stability_artifacts.py`.
- Add self-test negative cases for a mismatched `run_index` and missing
  `elapsed_wall_sec`.

This hardens final evidence only and does not change replay behavior.
