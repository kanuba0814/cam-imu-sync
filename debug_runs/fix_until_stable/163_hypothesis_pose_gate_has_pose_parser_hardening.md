# Hypothesis: Runtime Pose Gate Has-Pose Parser Hardening

## Observation

The wrapper logs `has_pose` in each `[orb_pose_gate]` record. The final parser
already rejects published poses with invalid tracking state or low visual
support, but it should also explicitly reject any published pose where
`has_pose` is false or missing.

## Change

Harden `parse_runtime_orb_log.py` so `invalid_pose_publish_count` also counts
`publish_pose=1` when:

- `has_pose` is missing
- `has_pose=0`

Add a selftest case for this condition.

## Expected Effect

This is evidence-gate hardening only. It does not alter ORB-SLAM3 or wrapper
runtime behavior. It prevents a final report from accepting a pose publish that
does not have a current ORB pose behind it.
