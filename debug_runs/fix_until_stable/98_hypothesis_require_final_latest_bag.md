# Hypothesis: require final evidence to use current LATEST_BAG

The goal says the main bag is read from `~/slam_ws_v2/bags/LATEST_BAG.txt`.
`run_stability_replay.py` does this by default, but the final artifact
generator should also reject aggregates whose `bag_path` does not match the
current latest bag file.

Expected fix:
- Add latest-bag resolution to `generate_final_stability_artifacts.py`.
- Reject final aggregate JSON when `aggregate["bag_path"]` differs from the
  resolved latest bag.
- Make the final gate self-test derive its positive bag path from the same
  latest file and add a negative wrong-bag case.

This is final evidence integrity only.
