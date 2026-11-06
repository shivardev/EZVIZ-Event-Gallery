# Product Requirements and Constraints

## Product goal

Build a small, dependable, image-first event viewer for one EZVIZ TY1 camera. The user should be able to open a local webpage on a phone and understand what happened during the day without opening full recordings or managing infrastructure.

The product is successful when it captures useful visual evidence of activity, groups related moments, and presents them quickly in chronological order. Reliability and understandable results matter more than sophisticated infrastructure.

## Expected user experience

- Open one URL and immediately see recent activity.
- See images or short animated previews rather than a video-first timeline.
- Treat a person leaving and later returning as separate activity.
- Capture general visible activity even when object recognition confidence is low.
- Group still images from one continuous action into an animated GIF when consecutive frames are no more than one second apart.
- Avoid repeated cards for a person standing still.
- Tap a card to view the full image or animation.
- Filter by people, cats, and date.
- Work comfortably on a phone and remain responsive with many events.
- Use little bandwidth; never download full recordings to build the gallery.

## Functional requirements

### Camera and capture

- Connect to the single EZVIZ TY1 RTSP stream at `192.168.1.9:554`.
- Store the EZVIZ verification code only in the local `.env` file.
- Do not alter the camera, its SD-card recordings, or unrelated cameras.
- Reconnect automatically after a temporary RTSP failure.
- Capture high-quality JPEG evidence from the 1080p source.

### Activity pipeline

- Detect scene change independently from object recognition.
- Capture timestamped JPEG frames while meaningful change is occurring.
- Group frames into the same activity when adjacent timestamps differ by at most one second.
- Close an activity after approximately 1.5 seconds without qualifying change.
- Convert each multi-frame group into a looping GIF in a separate background worker.
- Remove temporary JPEG frames after successful GIF creation.
- Keep isolated/noisy frames from creating useless cards.

### Object pipeline

- Recognize `person` and `cat` using a compact CPU model.
- Require repeated recognition before saving an object event.
- Save one object snapshot when a subject appears.
- Re-arm only after the subject is absent, so a return becomes a new event.
- Object recognition must enrich the feed; it must not be the only way activity is captured.

### Gallery

- Show newest items first, grouped by date.
- Show object JPEGs and activity GIFs in the same feed.
- Provide All, People, Cats, and date filters.
- Lazy-load media.
- Automatically refresh the feed while open.
- Make each card open the underlying media at full size.

### Storage and data

- Use SQLite only for metadata.
- Store images/GIFs as ordinary files.
- Keep configuration in JSON plus a private `.env` secret file.
- Apply a bounded retention period to object snapshots and activity GIFs.
- Do not add PostgreSQL, MySQL, Redis, message queues, cloud databases, or a separate application server.

### Access and security boundary

- Serve the dashboard directly on port 5000 with no login for the first version.
- Bind to the Windows host so it is reachable from the trusted LAN and existing ZeroTier network.
- Never create router port-forwarding or expose the unauthenticated service publicly.
- Do not change ZeroTier, existing VPN routing, or unrelated firewall configuration.

### Reliability

- Start automatically after Windows sign-in or reboot.
- Restart capture/dashboard workers after a crash.
- Recover from camera and network interruptions without manual action.
- Limit logs, temporary frames, and retained media so the disk cannot grow without bound.
- Provide observable health for the web server, RTSP input, detector, motion worker, and last successful frame/GIF.

## Laptop and measured environment

These are measured values from the target laptop, not generic assumptions:

| Item | Measured value |
|---|---|
| Operating system | Windows Home, build 26200 (system API reports Windows 10 Home Single Language / version 2009) |
| Processor | AMD Ryzen 7 4700U with Radeon Graphics |
| CPU cores / logical processors | 8 / 8 |
| Physical RAM | 7,968,419,840 bytes, approximately 7.4 GiB usable |
| Free space on C: during implementation | approximately 45.9 GiB |
| Python | CPython 3.12.2 |
| Camera source | 1920×1080 RTSP stream |
| LAN address observed | `192.168.1.15` |
| ZeroTier address observed | `172.23.121.170` |
| Existing WSL memory | approximately 3.5 GiB available inside WSL |
| Existing WSL services | Docker, MySQL container, Portainer container |

## Resource constraints

- Eight gigabytes of installed RAM is shared by Windows, the phone-accessible web service, video decoding, inference, and unrelated user applications.
- WSL/Docker Frigate caused the WSL VM to restart under memory pressure. It is therefore retained but stopped, not used for the active implementation.
- CPU-only inference must be rate-limited. The compact NanoDet model measured roughly 133–190 ms on ordinary test frames, with occasional slower readings.
- Disk free space is limited enough that continuous video recording is inappropriate. Only event media should be retained.
- Two independent readers of the same RTSP stream double decode/network work and may exceed the camera's connection limit. The architecture should ultimately share one capture source between workers.
- Animated GIF is convenient in browsers but inefficient compared with animated WebP. GIF dimensions, frame count, and retention must remain bounded.
- The laptop may be used for calls and normal work; the application must not monopolize CPU or memory.

## Technology limitations

- Native Windows only for the active version; do not require WSL, Docker, Java, Node.js, or .NET.
- Python standard library for HTTP and SQLite.
- Headless OpenCV and NumPy for RTSP decoding, motion analysis, and CPU inference.
- Pillow only for GIF encoding.
- OpenCV Zoo NanoDet ONNX model, limited to the COCO classes it knows.
- No frontend build system; use static HTML, CSS, and JavaScript.
- No external services, subscriptions, custom domains, TLS setup, or cloud dependency.

## Acceptance criteria

- A real departure and return produce two distinct useful events.
- General activity produces an animated gallery card even if person/cat confidence is too low.
- A continuous action becomes one GIF rather than many cards.
- Temporary frames are removed after conversion.
- People/cat/date filters operate correctly.
- Phone access works over LAN and the existing ZeroTier route.
- Both workers recover automatically after failure and after a Windows reboot.
- At least one full day of operation is tested without runaway CPU, RAM, disk, duplicate alerts, or a stalled camera feed.

