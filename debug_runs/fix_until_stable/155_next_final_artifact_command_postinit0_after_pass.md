# Next: Final Artifact Command After Post-Init 0 Passes

Use this only after the real ROS2 wrapper aggregate exists and shows:

- `run_count=3`
- `pass_count=3`
- `all_passed=true`

Required aggregate path:

```text
extra_ws/debug_runs/fix_until_stable/30_postinit_inliers0_wrapper_pose_gate_full_window.json
```

Generate the final artifacts with:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/generate_final_stability_artifacts.py \
  extra_ws/debug_runs/fix_until_stable/30_postinit_inliers0_wrapper_pose_gate_full_window.json \
  --settings-file extra_ws/src/ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml \
  --output-dir extra_ws/debug_runs/fix_until_stable \
  --kept-commit "ORB_SLAM3 a6b6c74 debug: add reset reason diagnostics needed to prove reset causes" \
  --kept-commit "ORB_SLAM3 5296c2b fix: guard debug gravity reads until IMU init to keep diagnostics safe" \
  --kept-commit "ORB_SLAM3 444696b fix: build g2o with C++11 to match ORB ABI" \
  --kept-commit "ORB_SLAM3 1d0857a fix: initialize IMU reset frame window before settings load" \
  --kept-commit "ORB_SLAM3 a5ea5b1 fix: allow delaying monocular IMU initialization for H30 weak-bootstrap avoidance" \
  --kept-commit "ORB_SLAM3_ROS2 61d405e fix: keep H30 visual recovery beyond fixed replay" \
  --kept-commit "ORB_SLAM3_ROS2 e167c21 fix: disable H30 incomplete IMU reset window" \
  --kept-commit "ORB_SLAM3_ROS2 88e06b7 fix: keep H30 map through pre-BA2 tracking dropouts" \
  --kept-commit "ORB_SLAM3_ROS2 9006321 fix: restore H30 four second inertial baseline" \
  --kept-commit "ORB_SLAM3_ROS2 95f55d8 fix: gate H30 low-inlier wrapper poses" \
  --kept-commit "ORB_SLAM3_ROS2 f93a5c7 fix: allow H30 post-init visual dropout survival" \
  --kept-commit "ORB_SLAM3_ROS2 20e2fff test: gate H30 IMU window median timing" \
  --kept-commit "ORB_SLAM3_ROS2 80567ea test: require explicit H30 wrapper pose gates" \
  --kept-commit "ORB_SLAM3_ROS2 be3fd27 test: require H30 replay IMU topic evidence" \
  --kept-commit "ORB_SLAM3_ROS2 replay/final-gate hardening commits: enforce sync-only latest-bag full-wrapper evidence before accepting final artifacts" \
  --excluded-hypothesis "offset/Tbc/IMU units/QoS alone: earlier audits did not explain continued resets on the fixed sync-only bag" \
  --excluded-hypothesis "nFeatures alone: 1200 features improved initialization evidence but earlier replays still reset or became recently lost" \
  --excluded-hypothesis "queue backlog alone: bounded queues and stale-frame gates are required safety fixes, but prior fresh-age runs still failed reset gates" \
  --excluded-hypothesis "pose fake publishing: publish gating prevents false odom/tf, but does not by itself create stable mapping" \
  --excluded-hypothesis "pre-BA2 visual optimization toggle and min-scale/preinit-inlier thresholds: earlier experiments failed and were reverted or excluded" \
  --excluded-hypothesis "finite FramesToResetIMU=90 and zero FramesToResetIMU=0: earlier experiments showed crash-at-gate versus immediate IMU-prediction reset loop" \
  --risk "This pass is proven only on the fixed H30 sync-only bag; live driver/sync behavior remains a separate validation target" \
  --risk "FramesToResetIMU=100000 intentionally bypasses ORB_SLAM3's unstable post-init IMU prediction handoff for this dataset" \
  --risk "Post-init internal inlier survival is relaxed to zero only because the ROS2 wrapper gates external pose publication below 15 inliers/tracked map points"
```

After the generator succeeds, inspect:

```bash
sed -n '1,240p' extra_ws/debug_runs/fix_until_stable/final_stability_report.md
sed -n '1,220p' extra_ws/debug_runs/fix_until_stable/stability_report.md
sed -n '1,220p' extra_ws/debug_runs/fix_until_stable/decision.md
sed -n '1,220p' extra_ws/debug_runs/fix_until_stable/final_patch_summary.md
sed -n '1,220p' extra_ws/debug_runs/fix_until_stable/final_commands.md
cmp -s \
  extra_ws/src/ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml \
  extra_ws/debug_runs/fix_until_stable/best_config.yaml
```

Do not run this command before the real aggregate passes; the generator should
reject incomplete, failing, non-wrapper, non-full-bag, or non-latest-bag
evidence.
