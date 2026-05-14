# Evidence: require run index sequence and elapsed time in final aggregate

Patch scope:
- `tools/generate_final_stability_artifacts.py`
- `tools/selftest_final_stability_gates.py`

Local validation:
- `python3 -m py_compile` passed for both touched Python files.
- `tools/selftest_final_stability_gates.py` passed.
- `git diff --check` passed for both touched files.
- A line-length scan found no lines over 100 columns.

Self-test coverage:
- Positive synthetic aggregate now has run metadata:
  `[(1, 101.0), (2, 102.0), (3, 103.0)]`.
- A mismatched second run index (`run_index=99`) is rejected.
- A missing `elapsed_wall_sec` is rejected.

Result:
Final evidence must now include the per-run sequence and positive wall-clock
duration written by `run_stability_replay.py`, which makes the "three
consecutive replays" claim more auditable.
