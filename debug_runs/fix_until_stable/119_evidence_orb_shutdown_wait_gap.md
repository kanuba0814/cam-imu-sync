# Evidence: ORB shutdown wait gap

Superseded in part: references to experiment 20 are historical. The shutdown
gap remains a possible separate branch only if the current experiment 25 replay
fails solely or primarily on runtime `exit code -11`.

## Purpose
Follow up on the `exit code -11` runtime errors by checking whether the existing
ORB shutdown API fully stops background threads.

## ORB system threads
`ORB_SLAM3::System` starts background threads for:

```text
LocalMapping::Run
LoopClosing::Run
Viewer::Run, when enabled
```

The thread handles are stored as raw pointers:

```text
std::thread* mptLocalMapping
std::thread* mptLoopClosing
std::thread* mptViewer
```

No `System` destructor is declared in `System.h`, so there is no automatic
shutdown or join path visible in the class interface.

## Current Shutdown behavior
`System::Shutdown()` currently:

- sets `mbShutDown=true`
- calls `mpLocalMapper->RequestFinish()`
- calls `mpLoopCloser->RequestFinish()`

The loop that waits for `mpLocalMapper->isFinished()` and
`mpLoopCloser->isFinished()` is present but commented out. The viewer finish
wait is also commented out.

## Wrapper behavior
The ROS2 wrapper destructor currently stops and joins only its own
`SyncWithImu` thread. It does not call `orb_slam3_system_->Shutdown()`.

## Implication
If `20_frames90_no_pre_ba2_reset` improves tracking but still fails final gates
because of runtime `exit code -11`, a separate minimal shutdown fix should be
considered. The likely scope is:

- wrapper: stop callbacks/tracking and call ORB shutdown under the ORB mutex
- ORB core: restore a bounded wait for LocalMapping/LoopClosing finish if
  calling `System::Shutdown()` alone is insufficient

This must remain separate from the next behavior experiment. It should not be
stacked into the no-reset config commit.
