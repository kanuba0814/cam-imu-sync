# Root Cause Correction & Deprecation of fix_until_stable Iteration

## TL;DR

The 165 hypothesis/evidence iterations in this directory (files `001_*.md` through
`165_*.md`) plus the `tools/run_stability_replay.py` /
`tools/generate_final_stability_artifacts.py` /
`tools/selftest_final_stability_gates.py` harness chased the **wrong root cause**.

The "frequent reset / IMU not initialised" symptom on the H30 mono-inertial
pipeline is **not** caused by anything that can be fixed at the wrapper layer.
It is the expected behaviour of ORB-SLAM3's monocular initialiser when the bag's
opening seconds lack camera motion.

This file marks the prior iteration as **deprecated** and records the actual
fix applied to the wrapper.

## What the prior iteration tried

- Tweaking `Tracking.MinInliersImuMonoPostInit` from 5 → 0
- Adding a wrapper-side `min_pose_publish_inliers` / `min_pose_publish_tracked_mappoints`
  pose-publish gate (default 15/15)
- Adding `drop_stale_images` + `max_image_age_ms=200` + `max_image_queue_size=2`
  to the wrapper's image queue
- Hardening a `stability_pass` parser/selftest/final-artifact pipeline that
  judged success on `median_inliers_after_init >= threshold` and similar
  derived metrics

None of these change the algorithmic outcome on the original
`bags/goalDebug/h30_sync_raw_20260512_172136` bag, because that bag's first
~84 seconds have median visual parallax of 0.02–0.49 px (well below the
hard-coded `required_parallax = 1.0 px` of ORB-SLAM3's `Initializer`).

## Real root cause (with code references)

1. **Mono-init parallax floor is hard-coded.** The Initializer requires
   `median_parallax >= 1.0 px` between two reference frames within a 1 s window.
   When that window expires without enough parallax, the reference frame is
   discarded and the cycle restarts. Repeated mono-init failure escalates to an
   active-map reset — see `Tracking.cc:2238-2243`:

   ```cpp
   if (mState == OK && bOK == false) {
     if (sensor IMU_MONO/STEREO/RGBD) {
       if (!isImuInitialized() ||
           (!IniertialBA2 && mResetActiveMapBeforeInertialBA2)) {
         cout << "IMU is not or recently initialized. Reseting active map..." << endl;
         mpSystem->ResetActiveMap();
       }
     }
   }
   ```

   The pre-init reset path **cannot be disabled by any yaml parameter**. It is
   conditional only on `isImuInitialized()` being false.

2. **IMU init is gated by KFs + time, not inliers.** `LocalMapping.cc:1233`
   `InitializeIMU` requires `KFs >= mImuMonoInitMinKFs` and
   `time_span >= mImuMonoInitMinTime`. After mono init succeeds, IMU init is
   typically immediate. Stages: VIBA1 at mTinit > 5 s, VIBA2 > 15 s,
   ScaleRefinement at 25/35/45/55/65/75 s.

3. **`mnMatchesInliers` is not a reliable per-frame liveness signal.** It is
   set inside `Tracking::TrackLocalMap` (`Tracking.cc:3175 mnMatchesInliers=0;`
   then incremented). For IMU-mono frames that do not enter the TrackLocalMap
   path (e.g. fast paths during IMU prediction), the value remains at 0 even
   though `tracking_state == OK` and `has_pose == true`. Gating pose
   publication on `num_inliers >= 15` therefore silently blocks 75 %+ of
   legitimate poses — exactly what the prior iteration was measuring as
   "failure."

4. **Image queue dwell-based drop interferes with mono init.** The 165-iteration
   wrapper had `drop_stale_images=true, max_image_age_ms=200`. ORB's mono-init
   reference-frame retry path occasionally takes >200 ms (Atlas reset, LocalMapping
   flush). The next image arrived during that window was silently dropped,
   breaking the continuous-frame stream that mono init needs to find a parallax
   pair.

## Community evidence

- [UZ-SLAMLab/ORB_SLAM3 issue #69 — Looping "IMU is not or recently initialized"](https://github.com/UZ-SLAMLab/ORB_SLAM3/issues/69)
  has 30+ users hitting the same symptom; the converged-on fixes are
  calibration (Kalibr + allan_variance_ros) and sufficient motion at start,
  not wrapper-layer mitigation.
- [UZ-SLAMLab/ORB_SLAM3 issue #736 — A summary of mono-inertial initialization issues](https://github.com/UZ-SLAMLab/ORB_SLAM3/issues/736)
  is the canonical reference. Two root-cause categories: bad cam-IMU
  extrinsics, or insufficient motion. Recommended IMU rate >100 Hz and camera
  10–30 Hz; jitter does not matter (predictably, since each `IMU::Point` carries
  its own timestamp).
- [zang09/ORB_SLAM3_ROS2 stereo-inertial-node.cpp:87-195](https://github.com/zang09/ORB_SLAM3_ROS2/blob/master/src/stereo-inertial/stereo-inertial-node.cpp)
  is the reference image-queue pattern: size-1 latest-only, no dwell-based
  drop, IMU-coverage check before consuming an image. This mirrors the
  upstream ORB_SLAM3 ROS_inertial example.

## Real fix (applied in this branch)

Wrapper refactor in `extra_ws/src/ORB_SLAM3_ROS2/src/imu_mono_realsense.cpp`:

- Image queue: switch to **size-1 latest-only** (zang09 / official pattern).
- Drop the `max_image_queue_size`, `drop_stale_images`, `max_image_age_ms`
  parameters entirely (they encode the wrong policy).
- Pose-publish gate defaults: `min_pose_publish_inliers` 15 → 0 and
  `min_pose_publish_tracked_mappoints` 15 → 0 (parameters retained, opt-in
  via launch override). `publish_pose_only_when_tracking_ok` stays `true`
  (sensible).
- Keep `SyncWithImu` thread (codex commit `3e3b880` correctly fixed an IMU
  data loss race; only the dwell-based drop block inside it is removed).

Yaml updates in `config/Monocular-Inertial/rmoncam_h30.yaml`:

- `Camera.fps: 9 → 30` (matches `bags/goalDebug/h30_150hz_150s` actual rate of
  30.02 Hz; this affects `Tracking.cc:3348` keyframe-insertion timing).
- `IMU.Frequency: 100.0 → 229.0` (informational only; matches the same bag's
  observed `/sync/imu` rate of 229.02 Hz).

## What this directory is now

- **`001_*.md` … `165_*.md`** — historical iteration log. **Deprecated**, kept
  for context. Do **not** treat the recommendations or hypotheses inside as
  authoritative.
- **`tools/run_stability_replay.py`** — the harness that judged on
  `stability_pass`. **Deprecated**. Will reference removed wrapper parameters
  (`max_image_queue_size`, `drop_stale_images`, `max_image_age_ms`) and will
  fail to launch the wrapper. Kept for git history.
- **`tools/generate_final_stability_artifacts.py`** and
  **`tools/selftest_final_stability_gates.py`** — same status: **deprecated**.

## Future diagnostic order (if similar issue recurs)

When the symptom is "frequent reset / IMU not initialised", **check in this
order before changing the wrapper or yaml**:

1. Count `MONO_INIT_FAILED_*` events in the wrapper's `[orb_event]` log. If
   `MONO_INIT_FAILED_NOT_ENOUGH_MOTION` dominates and `median_parallax << 1.0`,
   the bag/scenario itself is the problem — re-record with motion in the first
   5–10 seconds (translation + roll + pitch).
2. Verify `Camera.fps` and `IMU.Frequency` in yaml roughly match the actual
   stream rates. `IMU.Frequency` is informational; `Camera.fps` affects
   keyframe-insertion timing.
3. Verify cam-IMU extrinsic calibration with Kalibr; verify IMU intrinsics
   with allan_variance_ros. ORB issue #736 covers this in detail.
4. Only then look at wrapper-layer behaviour (queue, gates).
5. Only then look at ORB-SLAM3 source-level changes (last resort; the
   `required_parallax = 1.0 px` floor in `Initializer` is intentional —
   reducing it produces numerically unstable triangulation).
