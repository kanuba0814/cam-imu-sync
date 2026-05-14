# Hypothesis: self-test should use replay harness command and preflight

`tools/selftest_final_stability_gates.py` has been useful for final artifact
gate checks, but its positive aggregate manually duplicated the replay command
and preflight metadata. That allows drift between the actual
`run_stability_replay.py` command and the synthetic self-test command.

Expected fix:
- Import `run_stability_replay.py` inside the self-test.
- Use `read_latest_bag()`, `preflight_replay()`, and `launch_command()` to build
  the positive synthetic aggregate.
- Keep the synthetic run metrics, but derive the wrapper command and preflight
  from the real replay harness.

This is validation bridge hardening only and does not change runtime replay or
ORB behavior.
