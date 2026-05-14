# Hypothesis: require identical commands across final replay runs

The final aggregate should prove that the same ROS2 wrapper replay command
passed repeatedly. Per-run `run_index` proves order, but it does not prevent a
passing aggregate from mixing different command lines or config arguments.

Expected fix:
- In `generate_final_stability_artifacts.py`, require every run's `command` to
  match run 1 exactly.
- Add a self-test negative case where run 2 changes `rate:=1.0` to `rate:=0.5`.

This is final evidence integrity only and does not change runtime behavior.
