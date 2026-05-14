# Evidence: reject aggregate run_count mismatch

Patch scope:
- `tools/generate_final_stability_artifacts.py`
- `tools/selftest_final_stability_gates.py`

Local validation:
- `python3 -m py_compile` passed for both touched Python files.
- `tools/selftest_final_stability_gates.py` passed.
- `git diff --check` passed for both touched files.
- A line-length scan found no lines over 100 columns in either touched file.

New coverage:
- The final generator rejects aggregates where `run_count` does not match the
  actual `runs` list length.
- The self-test covers `run_count=4` with only three run summaries.

Result:
Final reports can no longer silently carry a misleading aggregate run count.
This improves completion-audit integrity only; it does not prove fixed-bag
stability.
