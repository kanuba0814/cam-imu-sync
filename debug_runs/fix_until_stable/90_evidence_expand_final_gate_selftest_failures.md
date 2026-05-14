# Evidence: expand final gate self-test failure coverage

Patch scope:
- `tools/selftest_final_stability_gates.py`

Local validation:
- `python3 -m py_compile tools/selftest_final_stability_gates.py` passed.
- `python3 tools/selftest_final_stability_gates.py` passed.
- `git diff --check -- tools/selftest_final_stability_gates.py` passed.
- A line-length scan found no lines over 100 columns.

Additional negative cases now covered:
- Aggregate `pass_count=2` and `all_passed=false`.
- Run `returncode=1`.
- `required_v2_tags_present=false`.
- `invalid_pose_publish_count=1`.

Result:
The repeatable self-test now covers the main aggregate-level and run-level
signals used by the completion audit in addition to topic and wrapper safety
argument checks.
