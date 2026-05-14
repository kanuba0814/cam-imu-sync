# Hypothesis: guard final artifacts with replay preflight

## Observation

`generate_final_stability_artifacts.py` already rejected aggregates unless every run passed the stability gates, returned `0`, and included the required runtime metrics. It did not yet reject a passing-looking aggregate if the aggregate lacked replay preflight metadata, selected a forbidden topic, used a timeout too short for full-bag replay, or omitted the exact settings file evidence.

That is a completion-risk gap because the goal requires final evidence from the ROS2 wrapper on the fixed sync-only bag, not a proxy run or a manually constructed passing summary.

## Minimal change

Add final-artifact preflight validation only:

- require aggregate `preflight`
- require selected image topic `/sync/image_raw`
- require selected IMU topic `/sync/imu` or `/sync/imu_batch`
- reject forbidden selected topics such as `/image_raw`
- require image topic count/FPS evidence
- require settings file, QoS override, `settings_camera_fps`
- require replay timing fields and `timeout_sec >= required_timeout_sec`
- require each run command to be `ros2 launch orb_slam3_ros2 h30_bag_replay.launch.py`

This does not change replay, launch, parser, or SLAM behavior.

## Expected validation signal

The generator should reject missing-preflight, forbidden-topic, and short-timeout synthetic aggregates, but accept a synthetic aggregate that carries valid sync-only preflight metadata and wrapper replay commands.
