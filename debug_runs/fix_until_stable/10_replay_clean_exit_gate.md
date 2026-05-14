# 10 Replay Clean Exit Gate

## Hypothesis

The replay verifier should not accept interrupted or externally terminated launches as stable runs. V2 requires full offline replay evidence, so accepting return codes such as `130` or `143` risks treating partial runs as valid.

## Minimal Change

`run_stability_replay.py` now requires every run to have:

- `stability_pass == true`
- `returncode == 0`

Both the aggregate `all_passed` field and the script process exit use this rule.

## Commit

`extra_ws/src/ORB_SLAM3_ROS2`:

```text
3a523fc test: require clean replay process exit
```

## Local Validation

```bash
python3 -m py_compile extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/run_stability_replay.py --runs 0
```

`--runs 0` still exits nonzero with the expected argparse error.

## Remaining Gate

Clean-exit gating only hardens the verifier. It does not replace the required container build and three fixed-bag replays.
