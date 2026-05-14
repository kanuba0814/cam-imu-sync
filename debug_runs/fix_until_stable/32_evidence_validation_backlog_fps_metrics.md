# Evidence: replay backlog and processed-FPS metrics in validation output

## Change under validation

- `extra_ws/src/ORB_SLAM3_ROS2` commit: `c3f74e1 debug: expose replay backlog fps stability metrics`
- Files changed:
  - `tools/parse_runtime_orb_log.py`
  - `tools/run_stability_replay.py`

## Purpose

This is a validation-tooling change only. It does not change ORB-SLAM3 behavior, wrapper runtime behavior, launch defaults, H30 YAML, or the fixed bag replay command.

The change makes the backlog/FPS acceptance evidence explicit:

- `input_image_fps_est`
- `input_imu_fps_est`
- `orb_processed_fps_est`
- `oldest_img_age_ms`
- `newest_img_age_ms`
- `img_buf_size_final`
- `imu_buf_size_max`
- `controlled_backlog_pass`

`controlled_backlog_pass` requires:

- queue records exist
- `orb_processed_fps_est` p50 is positive
- `processed_image_age_ms` p95 is below 150 ms
- `oldest_img_age_ms` p95 is below 150 ms when present
- `img_buf_size_max <= 2`

## Local validation

Compiled the updated scripts:

```bash
python3 -m py_compile extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py
```

Re-parsed existing `14_revert_preinit_inliers_35` ROS2 wrapper replay logs:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py extra_ws/debug_runs/fix_until_stable/14_revert_preinit_inliers_35_run01.log --output-json /tmp/14_revert_run01_reparse.json --output-md /tmp/14_revert_run01_reparse.md
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py extra_ws/debug_runs/fix_until_stable/14_revert_preinit_inliers_35_run02.log --output-json /tmp/14_revert_run02_reparse.json --output-md /tmp/14_revert_run02_reparse.md
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/parse_runtime_orb_log.py extra_ws/debug_runs/fix_until_stable/14_revert_preinit_inliers_35_run03.log --output-json /tmp/14_revert_run03_reparse.json --output-md /tmp/14_revert_run03_reparse.md
```

Generated an aggregate from the three re-parsed summaries under `/tmp/orb_aggregate_test`.

## Result

The known failed run remains failed, while the new backlog/FPS fields are populated:

| Run | stability_pass | controlled_backlog_pass | OK ratio | Reset after init | ORB FPS p50 | Input image FPS p50 | Image age p95 ms | Img buf max | Invalid pose publishes |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | false | true | 0.6352 | 13 | 8.996 | 8.996 | 13.4449 | 1.0 | 0 |
| 2 | false | true | 0.2802 | 12 | 8.944 | 8.927 | 16.4460 | 1.0 | 0 |
| 3 | false | true | 0.6364 | 11 | 8.920 | 8.947 | 14.5751 | 1.0 | 0 |

Aggregate output confirms:

```text
pass_count=0
all_passed=false
```

## Interpretation

The validation tooling now directly reports the FPS/backlog evidence required by the goal. It does not change the current behavioral conclusion: the latest validated ORB state still fails because reset count remains nonzero and OK ratio is below target.

The next behavioral change remains:

```yaml
Camera.fps: 9
```

That change still must wait until `autoware_env_v2_host` build and 3-run ROS2 wrapper replay can run immediately afterward.
