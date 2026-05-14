# Evidence: current parser rejects run 19 runtime errors

## Purpose
Re-parse the latest real replay logs with the current parser to confirm that
runtime process errors are counted and will block final acceptance.

## Input
Logs from the latest real ROS2 wrapper aggregate:

```text
19_frames_to_reset_90_run01.log
19_frames_to_reset_90_run02.log
19_frames_to_reset_90_run03.log
```

## Current parser results

| Run | stability_pass | runtime_error_count | reset_count_after_init | OK ratio | reset_delta_last_60_sec |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | false | 1 | 3 | 0.6890 | 4 |
| 2 | false | 1 | 3 | 0.6890 | 4 |
| 3 | false | 0 | 7 | 0.7712 | 4 |

Run 1 and run 2 include:

```text
[ERROR] [imu_mono_node_cpp-1]: process has died ... exit code -11
```

## Status
The current parser catches runtime errors that older aggregates did not expose in
their markdown table. This confirms that the final gate must reject run 19 even
apart from the reset and OK-ratio failures.
