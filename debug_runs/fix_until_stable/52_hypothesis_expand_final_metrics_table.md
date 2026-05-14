# Hypothesis: expand final report metrics table

## Observation

The final artifact generator already validates reset deltas, lost streaks, and IMU lag internally, but the generated `final_stability_report.md` table did not show all of those gate values. That would make the final report harder to audit without opening the JSON.

## Minimal change

Only expand the final report metrics table to include:

- `reset_delta_last_60_sec`
- `max_lost_streak_sec_after_init`
- `image_to_last_imu_ms` p50/p95

Do not change replay behavior, final gate thresholds, parser behavior, launch files, or SLAM configuration.

## Expected validation signal

A synthetic passing aggregate should still generate final artifacts, and `final_stability_report.md` should show the added columns in the replay metrics table.
