from __future__ import annotations

import json
import logging
import os
import signal
import sqlite3
import threading
import time
import urllib.parse
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parent
SETTINGS_PATH = ROOT / "settings.json"
DATA_DIR = ROOT / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
ACTIVITY_DIR = DATA_DIR / "activity"
DB_PATH = DATA_DIR / "events.sqlite3"
WEB_DIR = ROOT / "web"
MODEL_PATH = ROOT / "models" / "object_detection_nanodet_2022nov.onnx"

COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog",
    "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle",
    "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich",
    "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book",
    "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush",
]

STOP = threading.Event()
STATUS_LOCK = threading.Lock()
STATUS = {"camera": "starting", "last_frame": None, "last_error": None, "inference_ms": None}


def load_env(path: Path) -> None:
    """Load a small local .env file without adding another dependency."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if value[:1] == value[-1:] and value.startswith(("'", '"')):
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def load_settings() -> dict:
    with SETTINGS_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def connect_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    return connection


def init_db() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    SNAPSHOT_DIR.mkdir(exist_ok=True)
    ACTIVITY_DIR.mkdir(exist_ok=True)
    with connect_db() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                captured_at TEXT NOT NULL,
                label TEXT NOT NULL CHECK(label IN ('person','cat')),
                confidence REAL NOT NULL,
                snapshot TEXT NOT NULL UNIQUE
            )"""
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_events_time ON events(captured_at DESC)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_events_label_time ON events(label, captured_at DESC)")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                captured_at TEXT NOT NULL,
                ended_at TEXT NOT NULL,
                frame_count INTEGER NOT NULL,
                media_file TEXT NOT NULL UNIQUE
            )"""
        )


class NanoDet:
    def __init__(self, model_path: Path, confidence: float, nms: float = 0.6):
        self.strides = (8, 16, 32, 64)
        self.image_shape = (416, 416)
        self.reg_max = 7
        self.confidence = confidence
        self.nms = nms
        self.project = np.arange(self.reg_max + 1)
        self.mean = np.array([103.53, 116.28, 123.675], dtype=np.float32).reshape(1, 1, 3)
        self.std = np.array([57.375, 57.12, 58.395], dtype=np.float32).reshape(1, 1, 3)
        self.net = cv2.dnn.readNet(str(model_path))
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        self.anchors = []
        for stride in self.strides:
            height, width = self.image_shape[0] // stride, self.image_shape[1] // stride
            x, y = np.meshgrid(np.arange(width) * stride, np.arange(height) * stride)
            self.anchors.append(np.column_stack(((x.flatten() + 0.5 * (stride - 1)), (y.flatten() + 0.5 * (stride - 1)))))

    def infer(self, frame: np.ndarray) -> list[tuple[str, float, tuple[int, int, int, int]]]:
        height, width = frame.shape[:2]
        square = cv2.resize(frame, self.image_shape, interpolation=cv2.INTER_AREA).astype(np.float32)
        blob = cv2.dnn.blobFromImage((square - self.mean) / self.std)
        self.net.setInput(blob)
        outputs = self.net.forward(self.net.getUnconnectedOutLayersNames())
        boxes, scores = [], []
        for stride, cls_score, bbox_pred, anchors in zip(self.strides, outputs[::2], outputs[1::2], self.anchors):
            cls_score = np.squeeze(cls_score)
            bbox_pred = np.squeeze(bbox_pred)
            exp = np.exp(bbox_pred.reshape(-1, self.reg_max + 1))
            distances = ((exp / np.sum(exp, axis=1, keepdims=True)) @ self.project).reshape(-1, 4) * stride
            max_scores = cls_score.max(axis=1)
            top = max_scores.argsort()[::-1][:1000]
            points, distances, cls_score = anchors[top], distances[top], cls_score[top]
            boxes.append(np.column_stack((points[:, 0] - distances[:, 0], points[:, 1] - distances[:, 1],
                                          points[:, 0] + distances[:, 2], points[:, 1] + distances[:, 3])))
            scores.append(cls_score)
        boxes = np.concatenate(boxes)
        scores = np.concatenate(scores)
        class_ids = np.argmax(scores, axis=1)
        confidences = np.max(scores, axis=1)
        wanted = np.array([COCO_CLASSES[index] in ("person", "cat") for index in class_ids])
        boxes, confidences, class_ids = boxes[wanted], confidences[wanted], class_ids[wanted]
        if not len(boxes):
            return []
        xywh = boxes.copy()
        xywh[:, 2:4] -= xywh[:, 0:2]
        indices = cv2.dnn.NMSBoxes(xywh.tolist(), confidences.tolist(), self.confidence, self.nms)
        results = []
        for index in np.array(indices).flatten():
            x1, y1, x2, y2 = boxes[index]
            scaled = (max(0, int(x1 * width / 416)), max(0, int(y1 * height / 416)),
                      min(width - 1, int(x2 * width / 416)), min(height - 1, int(y2 * height / 416)))
            results.append((COCO_CLASSES[int(class_ids[index])], float(confidences[index]), scaled))
        return results


def save_event(label: str, confidence: float, frame: np.ndarray, box: tuple[int, int, int, int], quality: int) -> None:
    now = datetime.now().astimezone()
    filename = f"{now.strftime('%Y%m%d-%H%M%S-%f')}-{label}.jpg"
    output = frame.copy()
    x1, y1, x2, y2 = box
    cv2.rectangle(output, (x1, y1), (x2, y2), (38, 220, 120), 3)
    cv2.putText(output, f"{label} {confidence:.0%}", (x1, max(30, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (38, 220, 120), 2)
    cv2.imwrite(str(SNAPSHOT_DIR / filename), output, [cv2.IMWRITE_JPEG_QUALITY, quality])
    with connect_db() as connection:
        connection.execute("INSERT INTO events(captured_at,label,confidence,snapshot) VALUES(?,?,?,?)",
                           (now.isoformat(timespec="seconds"), label, confidence, filename))


def camera_worker(settings: dict) -> None:
    password = os.environ.get("EZVIZ_PASSWORD", "").strip()
    url = settings["camera"]["rtsp_url"].replace("{EZVIZ_PASSWORD}", password)
    if (not password or password == "REPLACE_ME") and "{EZVIZ_PASSWORD}" in settings["camera"]["rtsp_url"]:
        with STATUS_LOCK:
            STATUS.update(camera="waiting_for_password", last_error="Enter EZVIZ_PASSWORD in .env")
        return
    detector = NanoDet(MODEL_PATH, float(settings["detection"]["confidence"]))
    cv2.setNumThreads(int(settings["detection"].get("opencv_threads", 2)))
    sample_seconds = float(settings["detection"]["sample_seconds"])
    confirm_hits = int(settings["detection"]["confirm_hits"])
    cooldown = float(settings["detection"]["event_cooldown_seconds"])
    quality = int(settings["storage"]["jpeg_quality"])
    recent_hits = {"person": 0, "cat": 0}
    recent_misses = {"person": 0, "cat": 0}
    active_presence = {"person": False, "cat": False}
    last_saved = {"person": 0.0, "cat": 0.0}
    while not STOP.is_set():
        capture = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not capture.isOpened():
            with STATUS_LOCK:
                STATUS.update(camera="reconnecting", last_error="Unable to open RTSP stream")
            STOP.wait(10)
            continue
        with STATUS_LOCK:
            STATUS.update(camera="connected", last_error=None)
        while not STOP.is_set():
            started = time.monotonic()
            ok, frame = capture.read()
            if not ok:
                with STATUS_LOCK:
                    STATUS.update(camera="reconnecting", last_error="RTSP read failed")
                break
            infer_started = time.monotonic()
            detections = detector.infer(frame)
            elapsed_ms = round((time.monotonic() - infer_started) * 1000)
            by_label = {}
            for label, confidence, box in detections:
                if label not in by_label or confidence > by_label[label][0]:
                    by_label[label] = (confidence, box)
            for label in recent_hits:
                if label in by_label:
                    recent_hits[label] += 1
                    recent_misses[label] = 0
                else:
                    recent_hits[label] = 0
                    recent_misses[label] += 1
                    if recent_misses[label] >= 2:
                        active_presence[label] = False
                if (label in by_label and recent_hits[label] >= confirm_hits and not active_presence[label]
                        and time.time() - last_saved[label] >= cooldown):
                    confidence, box = by_label[label]
                    save_event(label, confidence, frame, box, quality)
                    last_saved[label] = time.time()
                    active_presence[label] = True
            with STATUS_LOCK:
                STATUS.update(last_frame=datetime.now().astimezone().isoformat(timespec="seconds"), inference_ms=elapsed_ms)
            STOP.wait(max(0.0, sample_seconds - (time.monotonic() - started)))
        capture.release()
        STOP.wait(3)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, format_string: str, *args) -> None:
        logging.info("%s - %s", self.client_address[0], format_string % args)

    def json_response(self, value, status=200):
        body = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/status":
            with STATUS_LOCK:
                status = dict(STATUS)
            status["model"] = MODEL_PATH.name
            return self.json_response(status)
        if parsed.path == "/api/events":
            query = urllib.parse.parse_qs(parsed.query)
            label = query.get("label", [""])[0]
            date = query.get("date", [""])[0]
            clauses, params = [], []
            if label in ("person", "cat"):
                clauses.append("label = ?")
                params.append(label)
            if date:
                clauses.append("substr(captured_at,1,10) = ?")
                params.append(date)
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            with connect_db() as connection:
                rows = connection.execute("SELECT id,captured_at,label,confidence,snapshot FROM events" + where + " ORDER BY captured_at DESC LIMIT 500", params).fetchall()
                result = [dict(row) | {"media_url": "/snapshots/" + row["snapshot"], "media_type": "jpg"} for row in rows]
                if not label:
                    activity_sql = "SELECT id,captured_at,frame_count,media_file FROM activity"
                    activity_params = []
                    if date:
                        activity_sql += " WHERE substr(captured_at,1,10) = ?"
                        activity_params.append(date)
                    activity_rows = connection.execute(activity_sql + " ORDER BY captured_at DESC LIMIT 500", activity_params).fetchall()
                    result.extend(dict(row) | {"label": "activity", "confidence": None, "snapshot": row["media_file"], "media_url": "/activity/" + row["media_file"], "media_type": "gif"} for row in activity_rows)
                    result.sort(key=lambda row: row["captured_at"], reverse=True)
            return self.json_response(result[:500])
        if parsed.path.startswith("/snapshots/"):
            filename = Path(urllib.parse.unquote(parsed.path.removeprefix("/snapshots/"))).name
            path = SNAPSHOT_DIR / filename
            if not path.is_file():
                return self.send_error(404)
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            return self.wfile.write(body)
        if parsed.path.startswith("/activity/"):
            filename = Path(urllib.parse.unquote(parsed.path.removeprefix("/activity/"))).name
            path = ACTIVITY_DIR / filename
            if not path.is_file():
                return self.send_error(404)
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/gif")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            return self.wfile.write(body)
        return super().do_GET()


def prune_worker(settings: dict) -> None:
    retention = int(settings["storage"]["retention_days"])
    while not STOP.wait(3600):
        cutoff = time.time() - retention * 86400
        with connect_db() as connection:
            old = connection.execute("SELECT snapshot FROM events WHERE strftime('%s',captured_at) < ?", (int(cutoff),)).fetchall()
            connection.execute("DELETE FROM events WHERE strftime('%s',captured_at) < ?", (int(cutoff),))
        for row in old:
            (SNAPSHOT_DIR / row["snapshot"]).unlink(missing_ok=True)
        with connect_db() as connection:
            old_activity = connection.execute("SELECT media_file FROM activity WHERE strftime('%s',captured_at) < ?", (int(cutoff),)).fetchall()
            connection.execute("DELETE FROM activity WHERE strftime('%s',captured_at) < ?", (int(cutoff),))
        for row in old_activity:
            (ACTIVITY_DIR / row["media_file"]).unlink(missing_ok=True)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_env(ROOT / ".env")
    settings = load_settings()
    init_db()
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"Missing model: {MODEL_PATH}")
    signal.signal(signal.SIGINT, lambda *_: STOP.set())
    signal.signal(signal.SIGTERM, lambda *_: STOP.set())
    threading.Thread(target=camera_worker, args=(settings,), daemon=True, name="camera").start()
    threading.Thread(target=prune_worker, args=(settings,), daemon=True, name="prune").start()
    address = (settings["server"]["host"], int(settings["server"]["port"]))
    server = ThreadingHTTPServer(address, Handler)
    server.timeout = 1
    logging.info("Dashboard listening on http://%s:%s", *address)
    while not STOP.is_set():
        server.handle_request()
    server.server_close()


if __name__ == "__main__":
    main()
