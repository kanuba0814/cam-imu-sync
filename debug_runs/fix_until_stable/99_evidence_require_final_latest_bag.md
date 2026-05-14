# Evidence: require final evidence to use current LATEST_BAG

Patch scope:
- `tools/generate_final_stability_artifacts.py`
- `tools/selftest_final_stability_gates.py`

Current latest files:
- `/home/gxxl/slam_ws_v2/bags/LATEST_BAG.txt`
- `/home/gxxl/slam_ws_v2/bags/goalDebug/LATEST_BAG.txt`

Both currently resolve to:
`/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136`

Local validation:
- `python3 -m py_compile` passed for both touched Python files.
- `tools/selftest_final_stability_gates.py` passed.
- `run_stability_replay.py --preflight-only --timeout-sec 210` passed and used
  the same bag path.
- `git diff --check` passed for both touched files.
- A line-length scan found no lines over 100 columns.

Self-test coverage:
- Positive synthetic aggregate derives its bag path from current `LATEST_BAG`.
- Negative synthetic aggregate with `/tmp/not_the_latest_h30_bag` is rejected.

Result:
Final artifacts can no longer be generated from a passing aggregate for a stale
or different bag path. The final evidence must match the current fixed bag
selected by `LATEST_BAG.txt`.
