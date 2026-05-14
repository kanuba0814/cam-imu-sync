# Hypothesis: require final replay start_offset zero

The final replay evidence already requires full bag duration, but the replay
start point should also be explicit. `h30_bag_replay.launch.py` defaults
`start_offset=0.0`, while `run_stability_replay.py` did not pass or record that
argument in the aggregate.

Expected fix:
- Add `--start-offset` to `run_stability_replay.py`, defaulting to `0.0`.
- Pass `start_offset:=0.0` into the ROS2 launch command.
- Record `start_offset_sec` in preflight metadata.
- Make the final generator reject nonzero start offsets or commands missing
  `start_offset:=0.0`.
- Cover both negative cases in the final gate self-test.

This is final evidence hardening only.
