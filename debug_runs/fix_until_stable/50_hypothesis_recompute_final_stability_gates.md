# Hypothesis: recompute final stability gates before writing final artifacts

## Observation

`generate_final_stability_artifacts.py` already required `stability_pass=true`, return code `0`, replay preflight metadata, and final report metrics. That still left a completion-audit gap: a malformed, manually edited, or stale aggregate could mark `stability_pass=true` while individual metrics violate the goal.

The final generator should not trust `stability_pass` as the only proof. It should independently re-evaluate the goal-level gates from the metrics stored in each run.

## Minimal change

Only strengthen the final artifact generator:

- require `imu_initialized=true`
- require V2 tags present
- require `reset_count_after_init == 0`
- require `ok_ratio_after_init >= 0.90`
- require `max_lost_streak_sec_after_init < 5.0`
- require `reset_delta_last_60_sec == 0`
- require keyframe, inlier, and tracked-map-point thresholds
- require sane IMU lag and processed image age
- require bounded image queue and controlled backlog
- require no invalid pose publishes

Do not change replay, parser, launch, config, or SLAM behavior.

## Expected validation signal

Synthetic aggregates that lie by setting `stability_pass=true` while violating a final gate should be rejected with the specific failed metric. A complete synthetic aggregate that satisfies every gate should still generate final artifacts.
