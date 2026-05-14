# Hypothesis: make backlog and processed-FPS gates explicit in replay evidence

## Observation

The current replay parser already evaluates the main stability gates:

- IMU initialized
- reset count after init
- OK ratio after init
- LOST / RECENTLY_LOST streak
- last-60-second reset delta
- final keyframes
- median tracked map points
- median inliers
- image-to-IMU lag
- processed image age
- image queue bound
- invalid pose publishing

The goal also requires evidence that ORB processed FPS or a controlled frame-dropping mechanism is stable, and that the system is not accumulating unbounded backlog.

Current replay logs already contain the needed queue metrics in `[orb_queue]`:

```text
input_image_fps_est
input_imu_fps_est
orb_processed_fps_est
img_buf_size
imu_buf_size
oldest_img_age_ms
newest_img_age_ms
processed_image_age_ms
dropped_img_count
dropped_imu_count
```

But `parse_runtime_orb_log.py` and the aggregate replay summaries do not expose FPS and queue-age statistics directly. They currently rely mostly on `processed_image_age_ms_p95` and `img_buf_size_max`.

## Minimal change

Change only validation tooling:

- parse `input_image_fps_est`, `input_imu_fps_est`, and `orb_processed_fps_est` from existing `[orb_queue]` records
- expose p50/p95/max or final queue statistics in per-run JSON/Markdown
- include the key FPS/backlog metrics in `run_stability_replay.py` aggregate CSV/Markdown
- make `controlled_backlog_pass` explicit from existing evidence

Do not change ORB-SLAM3 behavior, wrapper runtime behavior, H30 YAML, launch defaults, or the fixed bag replay command.

## Expected validation signal

Re-parsing existing `14_revert_preinit_inliers_35` logs should produce the new fields without changing the known result:

- `stability_pass` remains false
- reset/OK/map metrics remain unchanged
- new FPS/backlog fields are populated

After Docker access is restored, the next behavioral change remains the already documented H30 YAML single-point test:

```yaml
Camera.fps: 9
```
