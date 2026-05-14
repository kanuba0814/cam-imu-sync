# Hypothesis: record fixed-bag FPS and settings FPS in replay evidence

## Observation

The next behavior change is expected to set H30 `Camera.fps` from `30` to `9`, based on fixed-bag `/sync/image_raw` cadence. The current preflight records selected topics, but it does not yet record:

- measured image message count and FPS from the selected image topic
- current `Camera.fps` value from the selected settings file

Without these fields, a future replay summary proves the correct topic was selected but not that the validated config actually matched the fixed bag cadence.

## Minimal change

Change only replay-harness evidence output:

- compute selected image topic message count and span FPS from rosbag2 sqlite metadata
- parse `Camera.fps` from the selected OpenCV YAML settings file
- include both values in preflight JSON
- include both values in aggregate Markdown

Do not change ORB-SLAM3 behavior, wrapper runtime behavior, launch defaults, H30 YAML, parser gates, or replay commands.

## Expected validation

Local validation against the fixed H30 bag should show:

- `image_topic_stats.count=1668`
- `image_topic_stats.fps_span` around `9.274296`
- `settings_camera_fps=30.0` before the behavior change
- known failed `14_revert_preinit_inliers_35` summaries remain `pass_count=0` and `all_passed=false`

The next behavior change remains `Camera.fps: 9` when containerized replay is available.
