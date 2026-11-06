# Current Architecture

## Overview

The active implementation is a native Windows Python application. It deliberately avoids WSL, Docker, external databases, reverse proxies, and web frameworks.

```text
EZVIZ TY1 RTSP
       |
       +---------------------------+
       |                           |
       v                           v
app.py                        motion_gif.py
object detection + HTTP       motion capture + GIF worker
       |                           |
       +----------+----------------+
                  v
        SQLite metadata + media files
                  |
                  v
      static mobile gallery on port 5000
```

Important: this is the current implementation, not the ideal final architecture. Both Python processes currently open their own RTSP connection. A later consolidation should use one capture process and distribute frames locally to reduce decoding load and avoid camera connection limits.

## Components

### `app.py`

Responsibilities:

- Loads `.env` and `settings.json`.
- Opens the EZVIZ RTSP stream.
- Runs the compact NanoDet ONNX model on CPU.
- Tracks person/cat presence and saves a JPEG when a new presence begins.
- Re-arms after two analyzed frames without that label.
- Hosts a `ThreadingHTTPServer` on `0.0.0.0:5000`.
- Exposes `/api/status` and `/api/events`.
- Serves object snapshots, activity GIFs, and the static frontend.
- Periodically removes expired database rows and media.

### `motion_gif.py`

Responsibilities:

- Runs as a separate native Windows Python process.
- Opens the same RTSP stream independently.
- Downscales frames for inexpensive grayscale difference analysis.
- Saves full-source JPEG frames when the changed-pixel percentage exceeds the configured threshold.
- Places temporary frames in `data/motion_frames/` with epoch-millisecond filenames.
- Groups adjacent files when their timestamp gap is at most one second.
- Closes the group after 1.5 seconds of quiet.
- Converts groups with at least two images into a 960-pixel-wide animated GIF.
- Inserts GIF metadata into SQLite and deletes the temporary JPEGs.

### Static gallery

Files under `web/` provide a dependency-free mobile interface:

- Lazy-loaded responsive cards.
- Newest-first grouping by date.
- All, People, Cats, and date filters.
- JPEG and GIF presentation in the same feed.
- Automatic status and event refresh.

### Persistence

`data/events.sqlite3` uses SQLite WAL mode.

- `events`: person/cat snapshot metadata.
- `activity`: motion GIF metadata.

Media is not stored inside SQLite:

- `data/snapshots/`: object JPEGs.
- `data/motion_frames/`: temporary JPEGs awaiting grouping.
- `data/activity/`: completed GIFs.

### Configuration and secrets

- `settings.json`: non-secret thresholds, timing, retention, server address, and RTSP URL template.
- `.env`: local EZVIZ verification code. It is excluded by `.gitignore`.
- `.env.example`: safe template.

### Runtime

- `runtime/`: local Python virtual environment.
- `models/object_detection_nanodet_2022nov.onnx`: approximately 3.8 MB object model.
- `start.cmd`: starts the motion worker in the background and runs the dashboard/object process.
- `services/`: WinSW wrappers that register both Python workers as native Windows services.
- Windows Services (`services.msc`) provides the controller UI for Start, Stop, Restart, startup type, and current state.
- Both services use delayed automatic startup, restart five seconds after failure, and rotate logs at 5 MB/daily boundaries.
- Each service runs `service_runner.py`, a minimal supervisor that restarts its managed Python worker five seconds after any child exit. WinSW separately restarts the supervisor if the service wrapper fails.

## Data flow

### Object event

1. `app.py` reads a camera frame.
2. NanoDet reports person/cat boxes and confidence.
3. Two qualifying observations confirm presence.
4. A boxed JPEG is saved.
5. Metadata is inserted into `events`.
6. The gallery API returns the new card.
7. Absence for two analyzed frames re-arms the label.

### Activity GIF

1. `motion_gif.py` reads frames approximately every 0.4 seconds.
2. It computes changed-pixel percentage against the previous grayscale frame.
3. Qualifying frames are saved as timestamped JPEGs.
4. Files no more than one second apart form one group.
5. After 1.5 seconds without a qualifying frame, the group closes.
6. Multi-frame groups become animated GIFs; isolated frames are discarded.
7. GIF metadata is inserted into `activity` and temporary frames are deleted.
8. The All view returns both object snapshots and GIF activity.

## Current operational risks

- Two RTSP readers duplicate decoding and may interfere with one another.
- `start.cmd` starts both processes but is not yet registered for Windows automatic startup.
- There is no supervisor that restarts one worker if only that worker crashes.
- `/api/status` reports the object process but not the motion/GIF worker.
- Motion threshold has not been tuned for clothes, shadows, exposure shifts, or the camera timestamp overlay.
- GIF production has not yet been validated with a real movement sequence.
- The HTTP service has no authentication and is safe only on the trusted LAN/private VPN.
