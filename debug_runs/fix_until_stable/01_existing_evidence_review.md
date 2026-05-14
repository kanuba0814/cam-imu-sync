# 01 Existing Evidence Review

## Scope

Reviewed prior artifacts under `extra_ws/debug_runs/latest/` before making new V2 parameter or algorithm changes:

- `decision.md`
- `completion_audit.md`
- `01_sync_bag_audit.md`
- `02_mono_sync_image.md`
- `03_sync_offset_test.md`
- `04_tbc_semantics.md`
- `05_orbextractor_feature_test.md`
- Parsed JSON summaries for baseline, `nFeatures=800`, and `nFeatures=1200`
- Console logs for the replay runs

## 1. Direct Evidence For `nFeatures=250` Failure

Baseline `rmoncam_h30.yaml` used `ORBextractor.nFeatures: 250`.

Direct replay evidence from `03A_sync_offset_zero.json`:

- `imu_initialized: false`
- `tracking_state: NOT_INITIALIZED`
- `ok_ratio: 0.02579468473163106`
- `reset_count: 49`
- `late_reset_delta_30s: 8`
- `final_keyframe_count: 0`
- `keyframe_count: 3`
- `inlier_count.median: 31.0`
- `tracked_map_points.median: 0.0`
- `event_reason_counts` dominated by initialization failures:
  - `not_enough_matches: 895`
  - `not_enough_triangulated: 818`
  - `ambiguous_motion: 772`
  - `not_enough_motion: 211`

This is direct runtime evidence that the 250-feature inertial config cannot produce a stable VI map on the fixed bag.

## 2. Did `nFeatures=800` And `1200` Stabilize Mapping?

No. They only made IMU initialization possible.

`nFeatures=800`:

- `imu_initialized: true`
- `first_imu_initialized_frame: 906`
- `ok_ratio: 0.16909848879624806`
- `reset_count: 36`
- `late_reset_delta_30s: 9`
- `final_keyframe_count: 0`
- `tracking_state: NOT_INITIALIZED`

`nFeatures=1200`:

- `imu_initialized: true`
- `first_imu_initialized_frame: 711`
- `ok_ratio: 0.23371547681083898`
- `reset_count: 27`
- `late_reset_delta_30s: 11`
- `keyframe_count: 23`
- `final_keyframe_count: 2`
- `tracked_map_points.median: 0.0`
- `inlier_count.median: 48.0`
- `tracking_state: RECENTLY_LOST`

Both variants fail the V2 stability gate. `imu_initialized=true` is explicitly not accepted as success.

## 3. Why Did `nFeatures=1200` End `RECENTLY_LOST` / Reset?

The current evidence points to repeated active map reset after low-inlier local map tracking:

- `event_code_counts.ACTIVE_MAP_RESET: 79`
- `event_code_counts.TRACK_LOCAL_MAP_FAILED: 19`
- `event_reason_counts.local_mapping_active_map_reset: 52`
- `event_reason_counts.active_map_reset: 27`
- `event_reason_counts.imu_mono_low_inliers_before_imu_init: 13`
- `event_reason_counts.recent_relocalization_low_inliers: 6`

Near the final failure in `05_orbextractor_nfeatures_1200.log`, the last tracked record shows:

- `tracking_state=RECENTLY_LOST`
- `reset_count=27`
- `last_reset_reason=active_map_reset`
- `num_inliers=36`
- `num_tracked_mappoints=36`
- `num_keyframes=2`

This is not stable mapping. It suggests the map briefly initializes, then tracking/local mapping cannot keep enough inliers/map points alive.

## 4. Reset-Precursor Evidence In The Last 5 Seconds

The existing logs contain some fields needed for a rough precursor read:

- `tracking_state`
- `reset_count`
- `last_reset_reason`
- `num_inliers`
- `num_tracked_mappoints`
- `num_keyframes`
- `image_to_last_imu_ms`

The existing logs do not contain enough V2 fields to answer the full reset-precondition question. Missing fields include:

- `track_ms`
- `cv_bridge_ms`
- `wait_for_imu_ms`
- `video_write_ms`
- `total_frame_ms`
- `processed_image_age_ms`
- `img_buf_size`
- `imu_buf_size`
- dropped image and IMU counters
- explicit state-transition records
- pose publish allow/deny records

Therefore current evidence cannot separate performance/backlog from visual quality, local mapping backlog, and pose publication artifacts.

## 5. Missing Log Fields

A search of prior console logs found no V2 log tags:

- `[orb_queue]`
- `[orb_timing]`
- `[orb_imu_window]`
- `[orb_state_transition]`
- `[orb_pose_gate]`
- `[orb_visual_quality]`

The current wrapper working tree also still publishes pose from the latest `Tcw_` unconditionally in `timer_callback()` and calls `video_writer_.write(imageFrame)` unconditionally after each tracking attempt. The image and IMU queues are unbounded in the current wrapper.

## 6. Is Previous Conclusion 8 Sufficient?

No.

Conclusion 8 is useful as a narrowed diagnosis: 250 features is a primary blocker. It does not explain the full user-visible behavior: "very laggy, continuous reset, almost no map/pose." It also does not satisfy the V2 success criteria because:

- `nFeatures=1200` still ended `RECENTLY_LOST`.
- `reset_count` still increased to `27`.
- `late_reset_delta_30s` was `11`.
- `final_keyframe_count` was only `2`.
- median tracked map points was `0.0`.
- median inliers was below the V2 threshold of `50`.
- there was no evidence for `processed_image_age_ms p95 < 150ms`.
- there was no evidence that image queues are bounded or that stale frames are dropped.
- LOST / RECENTLY_LOST pose publication was not gated.

## Next Hypothesis

Before changing ORB parameters again, add the V2 wrapper runtime logs and safety controls:

- queue size and controlled drop metrics
- per-frame timing and image age
- IMU window metrics
- state transition logs
- pose gate logs
- visual quality logs
- video recording default off
- bounded image and IMU queues
- no stale pose publication when tracking is invalid

Then rebuild and replay the fixed bag three times from the `nFeatures=1200` narrowed baseline. If the three runs still fail, branch to the next evidence-backed single-variable fix.
