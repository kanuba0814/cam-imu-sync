# Hypothesis: final commands must match replay preflight

## Observation

The final artifact generator already requires sync-only preflight metadata and settings-file/FPS consistency. It still accepted run command lists that only proved the command was broadly a ROS2 wrapper launch. It did not require the command itself to contain the same bag path, settings file, QoS override, rate, or play delay recorded in preflight.

That leaves an audit gap for final artifacts because `final_commands.md` could show a partial or mismatched command while the aggregate preflight says something else.

## Minimal change

Only strengthen `generate_final_stability_artifacts.py` command validation:

- require `bag_path:=...` to match aggregate `bag_path`
- require `image_topic:=...` and `imu_topic:=...` to match preflight selected topics
- require `settings_file:=...` to match preflight settings file
- require `qos_profile_overrides_path:=...` to match preflight QoS override
- require `rate:=...` and `play_delay:=...` to match preflight timing

Do not change replay, parser gates, launch behavior, or SLAM configuration.

## Expected validation signal

A synthetic final aggregate with the full runner command should still generate final artifacts. Synthetic aggregates missing the replayed settings file, QoS override, or bag path in run commands should be rejected.
