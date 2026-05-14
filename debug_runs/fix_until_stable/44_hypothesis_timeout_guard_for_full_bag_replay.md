# Hypothesis: guard replay timeout against full-bag false failures

## Observation

The fixed bag spans about 179.8 seconds. `h30_bag_replay.launch.py` also delays bag playback by 2 seconds before starting `ros2 bag play`.

Several previous replay runs returned `124`, which means `run_stability_replay.py` killed the launch because `--timeout-sec` expired. With `--timeout-sec 180`, the timeout budget is shorter than:

```text
play_delay + full_bag_duration + launch shutdown margin
```

This can make a run fail at the process level even when the runtime metrics are otherwise parseable.

## Minimal change

Change only replay-harness preflight:

- compute bag time span from rosbag2 sqlite message timestamps
- expose the estimated bag duration in preflight metadata
- add a runner `--play-delay` argument matching the launch default
- pass `play_delay:=...` explicitly into `h30_bag_replay.launch.py`
- when `--timeout-sec` is set, reject values too low for the requested duration/rate/play delay

Do not change ORB-SLAM3 behavior, wrapper runtime behavior, launch defaults, H30 YAML, parser stability gates, or replay metrics.

## Expected validation

Local preflight should show:

- `--timeout-sec 180` is rejected for the full fixed bag
- a larger timeout such as `--timeout-sec 210` passes
- known failed `14_revert_preinit_inliers_35` summaries remain failed when re-rendered

The next behavior change remains `Camera.fps: 9` when containerized replay is available, but the replay timeout should be increased rather than reusing `180`.
