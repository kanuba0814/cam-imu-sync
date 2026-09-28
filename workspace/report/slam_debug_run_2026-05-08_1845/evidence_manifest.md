# Evidence Manifest

Generated at: 2026-05-08 18:48 JST

## Commands Used

```bash
find extra_ws/logs -type f -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n' | sort | tail -80
find . -path '*/slam_debug/*' -type f -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n' | sort | tail -80
find . -type f \( -name 'orb_track.csv' -o -name 'raw_imu.csv' -o -name 'sync_frames.csv' -o -name 'sync_resampled_imu.csv' -o -name 'summary_1hz*.csv' -o -name 'run_meta_*.json' \) -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n' | sort | tail -120
find extra_ws/src/ORB_SLAM3_ROS2/output -maxdepth 3 -type f -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n' | sort | tail -80
ffprobe -v error -show_entries format=duration,size -of default=noprint_wrappers=1 <mp4>
```

## Located Files From 2026-05-08

```text
extra_ws/src/ORB_SLAM3_ROS2/output/2026-05-08_18-44-21/video/2026-05-08_18-44-21.mp4
  size: 258 bytes
  ffprobe duration: N/A

extra_ws/src/ORB_SLAM3_ROS2/output/2026-05-08_18-45-18/video/2026-05-08_18-45-18.mp4
  size: 258 bytes
  ffprobe duration: N/A
```

## Missing Expected Structured Debug Files

No files were found under any `slam_debug` path, and no matching files were found in the workspace for:

```text
raw_imu.csv
sync_frames.csv
sync_resampled_imu.csv
orb_track.csv
orb_pose.csv
summary_1hz*.csv
run_meta_*.json
```

## Interpretation

The run created ORB-SLAM3 default output directories but did not produce usable ORB video data or structured debug evidence. Treat this as a launch/config issue for the debug logging path, not as a valid static 60 second debug capture.

