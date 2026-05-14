# Evidence: experiment 25 preflight and gate tooling ready

Experiment label planned for container replay:

- `25_visual_recovery_window_full_bag_4s`

Current source/config state:

- wrapper repo HEAD: `61d405e fix: keep H30 visual recovery beyond fixed replay`
- core repo HEAD: `a5ea5b1 fix: allow delaying monocular IMU initialization`
- H30 config includes `LocalMapping.ImuMonoInitMinTime: 4.0`
- H30 config includes `Tracking.FramesToResetIMU: 100000`

Local checks completed:

```bash
python3 -m py_compile \
  extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py \
  extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py \
  extra_ws/src/ORB_SLAM3_ROS2/tools/generate_final_stability_artifacts.py \
  extra_ws/src/ORB_SLAM3_ROS2/tools/selftest_final_stability_gates.py
```

Result: passed.

```bash
extra_ws/src/ORB_SLAM3_ROS2/tools/selftest_final_stability_gates.py
```

Result:

```text
preflight: ignoring non-replay bag topics: /image_raw, /imu/data_raw, /imu/raw_hw
final stability gate selftest passed
```

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py \
  --runs 3 \
  --label 25_visual_recovery_window_full_bag_4s \
  --timeout-sec 210 \
  --preflight-only
```

Result:

```text
preflight: ignoring non-replay bag topics: /image_raw, /imu/data_raw, /imu/raw_hw
preflight passed for /home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136
replay_topics: /sync/image_raw,/sync/imu
start_offset_sec: 0.0
```

Interpretation:

- The planned replay selects the fixed sync-only bag and only `/sync/image_raw,/sync/imu`.
- The harness rejects start offsets other than `0.0`, forbidden raw topics, missing current settings, and too-low timeout.
- The final artifact generator will still reject this experiment until a real three-run ROS2 wrapper replay aggregate has `pass_count=3` and `all_passed=true`.

Current blocker:

- Required ROS2 wrapper build/replay inside `autoware_env_v2_host` is still blocked by the command approval usage limit. This preflight is not a replacement for replay validation.
