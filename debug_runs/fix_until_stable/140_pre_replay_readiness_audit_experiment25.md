# Pre-Replay Readiness Audit: experiment 25

Audit time: `2026-05-15 06:54 JST`

## Objective restatement

Fix H30 sync-only bag stability through the ROS2 wrapper path. Completion still
requires a full fixed-bag three-run `orb_slam3_ros2` replay aggregate that passes
all stability gates, followed by final artifacts generated from that passing
aggregate.

## Current candidate

- wrapper repo HEAD: `61d405e fix: keep H30 visual recovery beyond fixed replay`
- ORB core repo HEAD: `a5ea5b1 fix: allow delaying monocular IMU initialization`
- `extra_ws` evidence HEAD: `030f659 debug: document H30 frames reset settings loader`

Candidate H30 config:

```yaml
Camera.fps: 9
ORBextractor.nFeatures: 1200
LocalMapping.ResetOnSmallMotionBeforeInertialBA2: 0
LocalMapping.ImuMonoInitMinTime: 4.0
Tracking.FramesToResetIMU: 100000
```

## Prompt-to-artifact checklist

| Requirement | Evidence | Status |
| --- | --- | --- |
| Use ROS2 wrapper, not standalone ORB | `137_evidence_experiment25_launch_config_path.md` confirms `h30_bag_replay.launch.py` starts `imu_mono_node_cpp` | Ready, unvalidated |
| Do not start real camera/IMU/cam_imu_sync | `137_evidence_experiment25_launch_config_path.md` confirms no real drivers or `cam_imu_sync` are launched | Ready |
| Use sync-only topics and avoid `/image_raw` | `132_evidence_experiment25_preflight_and_gate_tooling.md` shows preflight replay topics `/sync/image_raw,/sync/imu` and ignored `/image_raw` | Ready |
| Use fixed latest bag | `132_evidence_experiment25_preflight_and_gate_tooling.md` resolves `/home/gxxl/slam_ws_v2/bags/goalDebug/h30_sync_raw_20260512_172136` | Ready |
| Start at beginning of bag | `132_evidence_experiment25_preflight_and_gate_tooling.md` shows `start_offset_sec: 0.0` | Ready |
| Candidate config loaded through launch | `137_evidence_experiment25_launch_config_path.md` confirms installed config symlink to source H30 config | Ready |
| `FramesToResetIMU` affects intended code paths | `134_evidence_frames_to_reset_call_sites.md` audits motion-model, local-map, and reset-frame call sites | Ready |
| `FramesToResetIMU` loader is observable in logs | `139_evidence_frames_to_reset_settings_loader.md` requires `frames_to_reset_imu=100000` in replay logs | Ready |
| Build command paths valid | `138_evidence_experiment25_command_paths.md` confirms package name, launch file, tools, ORB core path, and bag path | Ready |
| Final artifact command prepared | `135_next_final_artifact_command_after_pass.md` contains generator command for the pass path | Ready, only after pass |
| Post-replay triage prepared | `136_next_experiment25_triage_after_replay.md` lists aggregate and log checks | Ready |
| Container build inside `autoware_env_v2_host` | Docker command previously rejected by approval usage limit before `10:28 AM` | Missing |
| Three full ROS2 wrapper replays | No `25_visual_recovery_window_full_bag_4s` aggregate exists yet | Missing |
| IMU init, no reset after init, OK ratio, no long LOST, final KFs/MPs/inliers, age/backlog/pose/runtime gates | Covered by parser/generator gates, but no experiment 25 aggregate yet | Missing |
| Final `best_config.yaml`, `decision.md`, `stability_report.md`, `final_stability_report.md`, `final_patch_summary.md`, `final_commands.md` | Generator ready, but no passing aggregate yet | Missing |

## Decision

Experiment 25 is ready to build and replay once Docker approval is available.
The goal is not complete. Do not apply another behavior change until this
candidate has a container build and three-run ROS2 wrapper replay result.
