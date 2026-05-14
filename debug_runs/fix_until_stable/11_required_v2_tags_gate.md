# Required V2 Runtime Tags Gate

## Change

- ORB_SLAM3_ROS2 commit: `1205735 test: require V2 runtime tags for stability pass`.
- Parser now requires non-empty `[orb_queue]`, `[orb_timing]`, `[orb_imu_window]`,
  `[orb_pose_gate]`, and `[orb_visual_quality]` records before `stability_pass`
  can be true.
- Per-run and aggregate replay reports now include `required_v2_tags_present`.

## Rationale

The V2 goal depends on runtime evidence for queue/backlog, IMU image timing,
processing age, pose publish gating, and visual quality. Old logs with only
`[orb_track]` and `[orb_event]` records must remain useful for diagnosis, but
cannot satisfy the V2 stability gate.

## Local Validation

Commands run from `/home/gxxl/slam_ws_v2`:

```bash
python3 -m py_compile \
  extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py \
  extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py
git -C extra_ws/src/ORB_SLAM3_ROS2 diff --check -- \
  tools/parse_runtime_orb_log.py tools/run_stability_replay.py
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py \
  extra_ws/debug_runs/latest/05_orbextractor_nfeatures_1200.log
```

Observed on the old nFeatures=1200 log:

- `required_v2_tags_present`: `false`
- `stability_pass`: `false`
- missing V2 tag counts: `queue=0`, `timing=0`, `imu_window=0`,
  `pose_gate=0`, `visual_quality=0`
- original failure symptoms are still present: `reset_count_after_init=27`,
  `reset_delta_last_60_sec=17`, `tracking_state=RECENTLY_LOST`,
  `final_keyframes=2`, `ok_ratio_after_init=0.2658349328214971`

## Status

This is a test/reporting gate only. It does not claim the fixed bag is stable.
The required container build and 3-run replay are still blocked until the
`autoware_env_v2_host` runtime is accessible from this session.
