# Evidence: self-test checks final output files

Patch scope:
- `tools/selftest_final_stability_gates.py`

Local validation:
- `python3 -m py_compile tools/selftest_final_stability_gates.py` passed.
- `tools/selftest_final_stability_gates.py` passed.
- `git diff --check -- tools/selftest_final_stability_gates.py` passed.
- A line-length scan found no lines over 100 columns.

Additional coverage:
- Positive synthetic generation must write:
  - `best_config.yaml`
  - `decision.md`
  - `stability_report.md`
  - `final_stability_report.md`
  - `final_commands.md`
  - `final_patch_summary.md`
- `best_config.yaml` must match the selected current settings file.

Result:
The self-test now verifies that a passing final aggregate produces the concrete
artifacts required by the goal, not only a zero exit code.
