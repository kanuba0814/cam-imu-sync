# 05 Latest Bag Pointer

## Hypothesis

`goal/orbDebugGoalV2.md` says the main fixed bag should be read from:

```text
/home/gxxl/slam_ws_v2/bags/LATEST_BAG.txt
```

The workspace only had:

```text
/home/gxxl/slam_ws_v2/bags/goalDebug/LATEST_BAG.txt
```

This mismatch can cause operators and scripts to replay different bags or require explicit `--bag-path` overrides.

## Minimal Change

Created `/home/gxxl/slam_ws_v2/bags/LATEST_BAG.txt` with:

```text
/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136
```

That path exists and contains:

```text
h30_sync_raw_20260512_172136_0.db3
metadata.yaml
```

## Git Note

`/home/gxxl/slam_ws_v2` is not a usable git repository in this environment, so the bag pointer itself cannot be committed at the workspace root. This evidence file is committed in `extra_ws`.

## Remaining Gate

The bag pointer only aligns input selection. Stability still requires containerized build and three replay validations.
