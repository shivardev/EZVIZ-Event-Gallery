# Implementation Status

Status recorded on 2026-11-06 after live testing.

## Verified working

- EZVIZ RTSP authentication succeeds using the private `.env` value.
- Live camera frames are 1920×1080.
- Native dashboard responds on localhost, `192.168.1.15:5000`, and the Windows ZeroTier address `172.23.121.170:5000` when tested from the laptop itself.
- NanoDet loads and runs on CPU.
- Person recognition works after tuning the confidence threshold from 0.55 to 0.25 for this camera angle.
- Three person snapshot records exist in SQLite from live tests.
- Person presence re-arm logic produced later distinct images rather than only the original image.
- SQLite initializes and operates in WAL mode.
- People, cat, and date query parameters work at the API level.
- The mobile gallery loads and serves saved JPEGs.
- Docker/Frigate remains installed but stopped; it was not deleted.

## Implemented but not yet proven end to end

- Independent motion capture using frame difference.
- Timestamped temporary JPEG capture.
- One-second frame-gap grouping.
- GIF closure after 1.5 seconds of quiet.
- GIF encoding and insertion into the `activity` table.
- Display of activity GIFs in the All gallery.
- Expiration of activity GIFs under the retention policy.

At the time of this status snapshot, `activity` contained zero rows. The feature exists in code but has not yet passed a real motion-to-GIF acceptance test.

## Service management

- WinSW service definitions are included for the dashboard and motion worker.
- Both are configured for delayed automatic startup and restart five seconds after failure.
- A first crash test showed that WinSW stopped when its direct Python child was forcibly terminated. `service_runner.py` was added so worker exits restart inside the service; the final forced-child test still requires administrator confirmation.
- Windows Services is the controller UI.
- Both services are installed, set to Automatic, and currently report Running. The dashboard returned a connected camera state after service startup.

## Incomplete

- Reboot recovery test after Windows service installation.
- Motion-worker health in `/api/status`.
- Phone test from a separate LAN device.
- Remote phone test through the existing ZeroTier route.
- A full-day stability/resource/disk test.
- Motion masks for always-changing regions such as the timestamp overlay, shadows, or moving clothes.
- Best-frame selection across an entire object event; the object process currently saves the qualifying frame.
- Cat detection verified with a real cat.
- Cleanup validation after the configured 21-day retention period.
- Disk quota/maximum-byte cap in addition to time-based retention.
- Friendly error view when the camera is unavailable.

## Current measured state

- Camera API state: connected.
- Last measured inference: approximately 187 ms.
- Object events in SQLite: 3.
- Activity GIF events in SQLite: 0.
- Active application processes: `app.py` and `motion_gif.py`.
- Available C: space during measurement: approximately 45.9 GiB.

## Immediate next validation

1. Cause one clear movement sequence in the camera view.
2. Confirm temporary JPEGs appear while motion occurs.
3. Confirm one GIF is produced after quiet.
4. Confirm temporary JPEGs are removed.
5. Confirm the GIF appears and animates in the phone gallery.
6. Repeat with two actions separated by more than one second and confirm two cards.
7. Observe CPU, RAM, RTSP stability, and false activity while the scene is empty.
