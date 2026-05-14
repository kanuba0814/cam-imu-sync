# Evidence: runtime parser gate coverage

## Purpose
Confirm that the replay parser checks the actual runtime stability conditions,
not just the presence of a summary file.

## Parser coverage
`tools/parse_runtime_orb_log.py` parses V2 wrapper log tags:

- `[orb_queue]`
- `[orb_timing]`
- `[orb_imu_window]`
- `[orb_state_transition]`
- `[orb_pose_gate]`
- `[orb_visual_quality]`
- `[orb_event]`

It computes the goal-critical metrics from those records:

- IMU initialized from the first `[orb_track]` record with `imu_initialized=1`
- `reset_count_after_init` from post-init `reset_count` delta
- `ok_ratio_after_init` from post-init tracking states
- `max_lost_streak_sec_after_init` from consecutive `RECENTLY_LOST`/`LOST`
- `reset_delta_last_60_sec` from the final 60 seconds of track records
- final keyframes, median tracked map points, and median inliers after init
- `image_to_last_imu_ms` percentiles from `[orb_imu_window]`
- `processed_image_age_ms` and `track_ms` from `[orb_timing]`
- queue size, dropped frames, and processed/input FPS from `[orb_queue]`
- invalid pose publishes from `[orb_pose_gate]`
- runtime errors from log lines containing `ERROR`

The parser's `stability_pass` requires all of these gates:

```text
imu_initialized
required_v2_tags_present
reset_count_after_init == 0
ok_ratio_after_init >= 0.90
max_lost_streak_sec_after_init < 5.0
reset_delta_last_60_sec == 0
final_keyframes >= 20
median_tracked_map_points_after_init >= 80
median_inliers_after_init >= 50
abs(image_to_last_imu_ms.p95) <= 20.0
processed_image_age_ms.p95 < 150.0
img_buf_size_max <= 2
controlled_backlog_pass
invalid_pose_publish_count == 0
runtime_error_count == 0
```

## Status
The parser covers the behavioral success criteria needed for final replay
validation. The current blocker is still that the latest real ROS2 wrapper
aggregate fails those gates.
