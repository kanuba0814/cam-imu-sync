# Evidence: require final replay start_offset zero

Patch scope:
- `tools/run_stability_replay.py`
- `tools/generate_final_stability_artifacts.py`
- `tools/selftest_final_stability_gates.py`

Local validation:
- `python3 -m py_compile` passed for all three touched Python files.
- `tools/selftest_final_stability_gates.py` passed.
- `run_stability_replay.py --preflight-only --timeout-sec 210` passed and
  printed `start_offset_sec: 0.0`.
- `run_stability_replay.py --preflight-only --timeout-sec 210 --start-offset 1.0`
  failed with `final stability replay must start at the beginning of the bag`.
- `git diff --check` passed for all three touched files.

Self-test coverage:
- Positive synthetic aggregate includes `start_offset_sec=0.0` and
  `start_offset:=0.0`.
- Nonzero preflight `start_offset_sec=1.0` is rejected.
- Missing command argument `start_offset:=0.0` is rejected.

Result:
Final evidence now has to prove that the full-bag replay started at the
beginning, not merely that the duration matched the bag span.
