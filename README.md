# Native Windows EZVIZ event gallery

Project documentation:

- `docs/REQUIREMENTS.md` — product expectations, laptop constraints, stack limits, and acceptance criteria.
- `docs/ARCHITECTURE.md` — current components, data flow, storage, and operational risks.
- `docs/STATUS.md` — verified, implemented-but-unproven, and incomplete features.
- `docs/SATISFACTION_GAP.md` — why earlier behavior did not meet the user's expectation and what must change.

This is a lightweight Windows alternative to Frigate. It uses only headless OpenCV, NumPy, Python's built-in web server, SQLite, and ordinary JPEG files. Docker/Frigate remains installed but stopped.

## Camera credential

Copy `.env.example` to `.env`, replace `REPLACE_ME` with the EZVIZ verification code, and keep `.env` private:

```text
EZVIZ_PASSWORD=your_code_here
```

The `.env` file is excluded from source control. The password is never stored in SQLite, `settings.json`, snapshots, or browser responses.

Run `start.cmd`, then open:

- This laptop: `http://127.0.0.1:5000`
- LAN: `http://192.168.1.15:5000`
- Existing ZeroTier network: `http://172.23.121.170:5000`

Do not forward port 5000 through the router or expose it publicly.

## Process controller and automatic recovery

The `services` folder uses the open-source WinSW service wrapper. Run `services\install-services.cmd` once and approve the Windows administrator prompt. After installation, run `services\open-controller.cmd` or open `services.msc` to Start, Stop, and Restart the two services independently:

- EZVIZ Event Gallery
- EZVIZ Motion GIF Worker

Both use delayed automatic startup, restart five seconds after failure, and rotate logs under `services\logs`.

The detector analyzes one frame per second with two OpenCV CPU threads. An event requires two confirmed detections. It saves once when a person or cat appears, then re-arms after the subject is absent for two analyzed frames so a return creates a new event without repeated images of someone standing still.

`motion_gif.py` is a separate lightweight process. It captures JPEG frames whenever the scene changes, groups frames separated by no more than one second, and converts the group to an animated GIF after 1.5 seconds of quiet. The temporary JPEGs are removed after conversion. GIF activity events appear in the main gallery alongside person/cat snapshots and use the same retention limit.
