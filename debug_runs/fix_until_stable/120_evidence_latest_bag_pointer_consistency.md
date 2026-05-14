# Evidence: latest bag pointer consistency

## Purpose
Confirm that the replay harness and final artifact gate resolve the same fixed
bag path, so future failures are not caused by using different `LATEST_BAG.txt`
files.

## Current pointers
Both latest-bag files currently point to the same bag:

```text
/home/gxxl/slam_ws_v2/bags/LATEST_BAG.txt
/home/gxxl/slam_ws_v2/bags/goalDebug/LATEST_BAG.txt
```

Resolved path:

```text
/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136
```

## Existing aggregate
The latest real aggregate, `19_frames_to_reset_90.json`, records the same
`bag_path`:

```text
/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136
```

Its bag topic metadata includes both raw and sync topics, but replay preflight
selects only the sync topics for ORB wrapper playback.

## Status
Bag pointer consistency is covered. The goal remains incomplete because the
latest aggregate is `pass_count=0` and `all_passed=false`.
