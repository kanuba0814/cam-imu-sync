# Evidence: self-test uses replay harness command and preflight

Patch scope:
- `tools/selftest_final_stability_gates.py`

Local validation:
- `python3 -m py_compile tools/selftest_final_stability_gates.py` passed.
- `tools/selftest_final_stability_gates.py` passed.
- `git diff --check -- tools/selftest_final_stability_gates.py` passed.
- A line-length scan found no lines over 100 columns.

Bridge check:
- The self-test fixture now imports `run_stability_replay.py`.
- It calls `read_latest_bag()`, `preflight_replay()`, and `launch_command()`.
- Direct fixture inspection showed:
  - bag path:
    `/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136`
  - replay topics: `['/sync/image_raw', '/sync/imu']`
  - start offset: `0.0`
  - command includes `start_offset:=0.0`
  - command includes `replay_topics:=/sync/image_raw,/sync/imu`

Result:
The final gate self-test no longer validates a manually duplicated replay
command. Its positive aggregate uses the same command and preflight path that a
real `run_stability_replay.py` execution will use before ROS2 launch.
