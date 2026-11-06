from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import cv2
from PIL import Image


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PENDING = DATA / "motion_frames"
ACTIVITY = DATA / "activity"
DB = DATA / "events.sqlite3"


def load_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def database() -> sqlite3.Connection:
    connection = sqlite3.connect(DB, timeout=10)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_at TEXT NOT NULL,
            ended_at TEXT NOT NULL,
            frame_count INTEGER NOT NULL,
            media_file TEXT NOT NULL UNIQUE
        )"""
    )
    return connection


def make_gif(group: list[Path], settings: dict) -> None:
    if len(group) < 2:
        for path in group:
            path.unlink(missing_ok=True)
        return
    images = []
    width = int(settings["gif_width"])
    for path in group:
        with Image.open(path) as source:
            image = source.convert("RGB")
            if image.width > width:
                image.thumbnail((width, 10000), Image.Resampling.LANCZOS)
            images.append(image.copy())
    filename = f"{group[0].stem}-{group[-1].stem}.gif"
    images[0].save(
        ACTIVITY / filename,
        save_all=True,
        append_images=images[1:],
        duration=int(settings["gif_frame_ms"]),
        loop=0,
        optimize=True,
    )
    started = datetime.fromtimestamp(int(group[0].stem) / 1000).astimezone()
    ended = datetime.fromtimestamp(int(group[-1].stem) / 1000).astimezone()
    with database() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO activity(captured_at,ended_at,frame_count,media_file) VALUES(?,?,?,?)",
            (started.isoformat(timespec="seconds"), ended.isoformat(timespec="seconds"), len(group), filename),
        )
    for path in group:
        path.unlink(missing_ok=True)


def close_ready_groups(settings: dict) -> None:
    files = sorted(PENDING.glob("*.jpg"), key=lambda item: int(item.stem))
    if not files:
        return
    maximum_gap = int(float(settings["maximum_frame_gap_seconds"]) * 1000)
    groups, group = [], [files[0]]
    for path in files[1:]:
        if int(path.stem) - int(group[-1].stem) <= maximum_gap:
            group.append(path)
        else:
            groups.append(group)
            group = [path]
    groups.append(group)
    cutoff = int(time.time() * 1000 - float(settings["close_after_seconds"]) * 1000)
    for group in groups:
        if int(group[-1].stem) <= cutoff:
            make_gif(group, settings)


def main() -> None:
    load_env()
    config = json.loads((ROOT / "settings.json").read_text(encoding="utf-8"))
    motion = config["motion"]
    password = os.environ.get("EZVIZ_PASSWORD", "")
    url = config["camera"]["rtsp_url"].replace("{EZVIZ_PASSWORD}", password)
    PENDING.mkdir(parents=True, exist_ok=True)
    ACTIVITY.mkdir(parents=True, exist_ok=True)
    database().close()
    interval = float(motion["check_interval_seconds"])
    minimum = float(motion["minimum_changed_percent"])
    previous = None
    while True:
        capture = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not capture.isOpened():
            time.sleep(5)
            continue
        while True:
            started = time.monotonic()
            ok, frame = capture.read()
            if not ok:
                break
            height, width = frame.shape[:2]
            small_width = 320
            small = cv2.resize(frame, (small_width, int(height * small_width / width)), interpolation=cv2.INTER_AREA)
            gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (7, 7), 0)
            if previous is not None:
                difference = cv2.absdiff(previous, gray)
                changed = cv2.threshold(difference, 25, 255, cv2.THRESH_BINARY)[1]
                changed = cv2.dilate(changed, None, iterations=2)
                changed_percent = 100.0 * cv2.countNonZero(changed) / changed.size
                if changed_percent >= minimum:
                    cv2.imwrite(str(PENDING / f"{int(time.time() * 1000)}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
            previous = gray
            close_ready_groups(motion)
            time.sleep(max(0.0, interval - (time.monotonic() - started)))
        capture.release()
        previous = None
        time.sleep(2)


if __name__ == "__main__":
    main()
