# Evidence: require identical final replay commands

## Scope
- Wrapper repo: `/home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2`
- Source changes:
  - `tools/generate_final_stability_artifacts.py`
  - `tools/selftest_final_stability_gates.py`

## Change
The final artifact gate now rejects an aggregate where any replay run has a
different `command` from run 1. This prevents a final 3-run pass from mixing
different launch arguments, replay rate, bag selection, or wrapper safety flags.

The selftest adds a negative case that mutates run 2 from `rate:=1.0` to
`rate:=0.5` and expects:

```text
run 2 command differs from run 1 command
```

## Validation
Run from `/home/gxxl/slam_ws_v2/extra_ws/src/ORB_SLAM3_ROS2`:

```bash
python3 -m py_compile generate_final_stability_artifacts.py selftest_final_stability_gates.py
tools/selftest_final_stability_gates.py
git diff --check -- tools/generate_final_stability_artifacts.py tools/selftest_final_stability_gates.py
```

Results:

```text
final stability gate selftest passed
```

No whitespace errors were reported.
