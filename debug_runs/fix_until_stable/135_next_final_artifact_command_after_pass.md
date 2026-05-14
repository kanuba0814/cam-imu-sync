# Next: final artifact command after experiment 25 passes

Use this only after the real ROS2 wrapper aggregate exists and shows
`run_count=3`, `pass_count=3`, and `all_passed=true`:

```bash
python3 extra_ws/src/ORB_SLAM3_ROS2/tools/generate_final_stability_artifacts.py \
  extra_ws/debug_runs/fix_until_stable/25_visual_recovery_window_full_bag_4s.json \
  --settings-file extra_ws/src/ORB_SLAM3_ROS2/config/Monocular-Inertial/rmoncam_h30.yaml \
  --output-dir extra_ws/debug_runs/fix_until_stable \
  --kept-commit "ORB_SLAM3 a6b6c74 debug: add reset reason diagnostics needed to prove reset causes" \
  --kept-commit "ORB_SLAM3 5296c2b fix: guard debug gravity reads until IMU init to keep diagnostics safe" \
  --kept-commit "ORB_SLAM3 444696b fix: build g2o with C++11 to match ORB ABI" \
  --kept-commit "ORB_SLAM3 1d0857a fix: initialize IMU reset frame window before settings load" \
  --kept-commit "ORB_SLAM3 a5ea5b1 fix: allow delaying monocular IMU initialization for H30 weak-bootstrap avoidance" \
  --kept-commit "ORB_SLAM3_ROS2 e626edb debug: add queue timing IMU window state pose and visual quality logs" \
  --kept-commit "ORB_SLAM3_ROS2 0deab31 test: add repeatable offline ROS2 wrapper replay harness" \
  --kept-commit "ORB_SLAM3_ROS2 4b7ba06 fix: use public TransformStamped ROS header for wrapper compatibility" \
  --kept-commit "ORB_SLAM3_ROS2 2f15933 fix: serialize ORB debug metric state updates" \
  --kept-commit "ORB_SLAM3_ROS2 b58788a fix: snapshot ORB debug summary metrics under locks" \
  --kept-commit "ORB_SLAM3_ROS2 3b8059d fix: serialize ORB tracking and debug state reads" \
  --kept-commit "ORB_SLAM3_ROS2 12cb940 fix: raise H30 ORB feature budget for fixed bag replay" \
  --kept-commit "ORB_SLAM3_ROS2 9a7ca4c fix: disable H30 small-motion reset loop" \
  --kept-commit "ORB_SLAM3_ROS2 cbe7b3c fix: match H30 camera fps to fixed bag rate" \
  --kept-commit "ORB_SLAM3_ROS2 db564bc fix: delay H30 monocular IMU bootstrap to four seconds" \
  --kept-commit "ORB_SLAM3_ROS2 61d405e fix: keep H30 visual recovery beyond fixed replay" \
  --kept-commit "ORB_SLAM3_ROS2 final gate commits 84c87f8..14fafc8: reject incomplete or non-identical final replay evidence" \
  --kept-commit "ORB_SLAM3_ROS2 replay guard commits f36b424..afd36da: enforce sync-only full-bag wrapper replay and command metadata" \
  --excluded-hypothesis "offset/Tbc/IMU units/QoS alone: earlier audits did not explain continued resets on the fixed sync-only bag" \
  --excluded-hypothesis "nFeatures alone: 1200 features improved initialization evidence but earlier replays still reset or became recently lost" \
  --excluded-hypothesis "queue backlog alone: bounded queues and stale-frame gates are required safety fixes, but prior stable-age runs still failed reset gates" \
  --excluded-hypothesis "pose fake publishing: publish gating prevents false odom/tf, but does not by itself create stable mapping" \
  --excluded-hypothesis "pre-BA2 visual optimization toggle and min-scale/preinit-inlier thresholds: experiments 16,17,21,22 failed and were reverted or excluded" \
  --excluded-hypothesis "finite FramesToResetIMU=90 and zero FramesToResetIMU=0: experiments 23 and 24 show crash-at-gate versus immediate IMU-prediction reset loop" \
  --risk "This pass would be proven on the fixed H30 sync-only bag only; live driver/sync behavior remains a separate validation target" \
  --risk "FramesToResetIMU=100000 intentionally bypasses ORB_SLAM3's unstable post-init IMU prediction handoff for this dataset" \
  --risk "Future bags with stronger motion may need a repaired ResetFrameIMU handoff rather than a replay-length visual recovery window"
```

After the generator succeeds, inspect:

```bash
sed -n '1,240p' extra_ws/debug_runs/fix_until_stable/final_stability_report.md
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
