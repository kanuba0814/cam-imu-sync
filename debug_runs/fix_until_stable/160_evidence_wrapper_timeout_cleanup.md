# Evidence: Wrapper Replay Timeout Cleanup

## Purpose

The final validation must be three full ROS2 wrapper replays. If one replay
times out, leftover `ros2 launch`, wrapper, or `ros2 bag play` child processes
could contaminate the next run. This note records the harness-only fix that
prevents that failure mode before the next container replay.

## Change

- wrapper repo commit:
  `342ae01 test: clean up timed-out H30 wrapper replays`
- final gate commit:
  `067c63e test: reject timed-out H30 final replays`
- final report commit:
  `665c6dd test: show H30 pass and timeout evidence in final report`
- changed file:
  `extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py`
- behavior:
  each replay is launched with `start_new_session=True`; on timeout, the
  harness sends `SIGTERM` to the whole process group, escalates to `SIGKILL`
  after 10 seconds if needed, then writes `timed_out` and `timeout_sec` into the
  run JSON.
- final artifact gate behavior:
  `generate_final_stability_artifacts.py` rejects any run missing `timed_out`
  or reporting `timed_out: true`; `selftest_final_stability_gates.py` covers
  both rejection cases.
- final report behavior:
  `final_stability_report.md` includes per-run `Pass` and `Timed out` table
  columns so the report itself shows the consecutive accepted replays did not
  time out.

This does not change ORB behavior, wrapper launch arguments, selected topics,
QoS overrides, or runtime stability thresholds.

## Verification

Commands run from `/home/gxxl/slam_ws_v2`:

```bash
python3 -m py_compile \
  extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py \
  extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py \
  extra_ws/src/ORB_SLAM3_ROS2/tools/generate_final_stability_artifacts.py \
  extra_ws/src/ORB_SLAM3_ROS2/tools/selftest_final_stability_gates.py
```

Result: passed.

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/selftest_final_stability_gates.py
```

Result:

```text
preflight: ignoring non-replay bag topics: /image_raw, /imu/data_raw, /imu/raw_hw
final stability gate selftest passed
```

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py \
  --runs 1 \
  --label 30_postinit_inliers0_wrapper_pose_gate_full_window \
  --timeout-sec 210 \
  --min-pose-publish-inliers 15 \
  --min-pose-publish-tracked-mappoints 15 \
  --preflight-only
```

Result:

```text
preflight: ignoring non-replay bag topics: /image_raw, /imu/data_raw, /imu/raw_hw
preflight passed for /home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136
replay_topics: /sync/image_raw,/sync/imu
start_offset_sec: 0.0
```

## Next Action

After Docker escalation is available, run the containerized build and three-run
ROS2 wrapper replay from
`157_next_container_replay_after_gate_hardening.md`.
