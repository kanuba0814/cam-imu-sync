# 07 Replay Runner Empty Run Guard

## Hypothesis

The replay verifier must not be able to return success without actually running the fixed bag. A `--runs 0` invocation previously risked a false green because Python `all([])` is `True`.

## Minimal Change

`run_stability_replay.py` now:

- rejects `--runs < 1` with an argparse error.
- treats aggregate `all_passed` as true only when every run both passes stability gates and exits with an accepted launch return code.
- returns process success only under the same conditions.

## Commit

`extra_ws/src/ORB_SLAM3_ROS2`:

```text
72bdb1f test: prevent empty replay runs from passing
```

## Local Validation

```bash
python3 -m py_compile extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 0
```

Result:

```text
run_stability_replay.py: error: --runs must be at least 1
```

The second command exits nonzero as intended.

## Remaining Gate

This guards the verifier only. Containerized build and three real replays are still required.
