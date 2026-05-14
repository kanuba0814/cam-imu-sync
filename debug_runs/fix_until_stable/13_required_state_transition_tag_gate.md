# Required State Transition Runtime Tag Gate

## Change

- ORB_SLAM3_ROS2 commit: `e90f90a test: require ORB state transition runtime tag`.
- `parse_runtime_orb_log.py` now includes `state_transition` in the
  `required_v2_tags_present` gate.

## Rationale

`goal/orbDebugGoalV2.md` explicitly requires `[orb_state_transition]` output
when tracking state, IMU initialization, reset count, or map id changes. A V2
stability pass must therefore prove that the replay captured this diagnostic
surface; otherwise reset and RECENTLY_LOST transitions could be hidden from the
summary.

## Local Validation

Commands run from `/home/gxxl/slam_ws_v2`:

```bash
python3 -m py_compile \
  extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py \
  extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py
git -C extra_ws/src/ORB_SLAM3_ROS2 diff --check -- \
  tools/parse_runtime_orb_log.py
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py \
  extra_ws/debug_runs/latest/05_orbextractor_nfeatures_1200.log
```

Observed on the old nFeatures=1200 log:

- `state_transition`: `0`
- `required_v2_tags_present`: `false`
- `stability_pass`: `false`

The old replay still also fails on the original algorithm symptoms:
`reset_count_after_init=27`, `reset_delta_last_60_sec=17`,
`tracking_state=RECENTLY_LOST`, `final_keyframes=2`, and
`ok_ratio_after_init=0.2658349328214971`.

## Status

This is a parser gate only. The fixed-bag build and 3-run replay are still
required before any stability claim.
