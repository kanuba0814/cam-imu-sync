# Evidence: run 19 runtime error shutdown clue

Superseded in part: the "next planned behavior experiment" text below refers to
the older experiment 20 branch. The shutdown clue remains relevant historical
evidence if a future replay fails only on runtime errors.

## Purpose
Record the current evidence for the `exit code -11` failures in
`19_frames_to_reset_90` so the next experiments do not treat runtime errors as a
generic parser artifact.

## Observed behavior
Re-parsing the run 19 logs with the current parser shows:

| Run | runtime_error_count | Process result |
| ---: | ---: | --- |
| 1 | 1 | `imu_mono_node_cpp` died with exit code `-11` |
| 2 | 1 | `imu_mono_node_cpp` died with exit code `-11` |
| 3 | 0 | wrapper received SIGINT and exited cleanly |

In run 1 and run 2, the crash happens near the end of replay and after the last
recorded ORB frame. Both runs print `RESETING FRAME!!!` immediately before the
last recorded `frame_id=1045`; the process death is logged a few lines later.

`RESETING FRAME!!!` comes from:

```cpp
if(mCurrentFrame.mnId==(mnLastRelocFrameId+mnFramesToResetIMU))
{
    cout << "RESETING FRAME!!!" << endl;
    ResetFrameIMU();
}
```

`ResetFrameIMU()` is currently an empty function, so this line is a timing marker
rather than direct evidence that the empty function itself crashes.

## Shutdown path observation
The ROS2 wrapper destructor currently stops only `SyncWithImu`:

```cpp
sync_running_ = false;
if (sync_thread_.joinable()) sync_thread_.join();
```

The wrapper does not explicitly call `orb_slam3_system_->Shutdown()`. ORB-SLAM3
does provide `System::Shutdown()`, which requests LocalMapping and LoopClosing
threads to finish. That may become a separate minimal wrapper-exit fix if runtime
errors persist after the next behavior experiment.

## Status
This is a runtime-error lead, not a completed fix. The next planned behavior
experiment remains `20_frames90_no_pre_ba2_reset`; its aggregate must still have
`runtime_error_count=0` in every run. If it improves tracking but still produces
exit `-11`, handle wrapper shutdown as a separate minimal commit and replay
three times again.
