# Hypothesis: Runtime Pose Gate Quality Parser Hardening

## Observation

The ROS2 wrapper already logs `[orb_pose_gate]` with:

- `tracking_state`
- `has_pose`
- `num_inliers`
- `num_tracked_mappoints`
- `publish_pose`
- `reason`

The runtime parser counted a pose publish as invalid when the tracking state was
not OK, but it did not independently reject a publish where the state was OK
while the visual support was below the final wrapper trust gate.

## Change

Harden `parse_runtime_orb_log.py` so `invalid_pose_publish_count` also counts
published poses with:

- non-OK tracking state
- non-`ok` gate reason
- missing/non-finite pose quality fields
- `num_inliers < 15`
- `num_tracked_mappoints < 15`

Add a selftest case so this cannot regress before the next ROS2 wrapper replay.

## Expected Effect

This does not change ORB-SLAM3 or wrapper runtime behavior. It only tightens the
final evidence parser so the final aggregate cannot accept low-quality ROS2 pose
publication evidence.
