"""
app.py — Bird Feeder Camera App main entry point.

Usage:
    python app.py               # Start the app (open http://localhost:5000)
    python app.py --calibrate   # Show camera feed with ROI overlay to tune settings
"""
import argparse
import sys
import os
import threading
import time
from datetime import datetime
from collections import deque

from flask import Flask, Response, render_template, jsonify, send_from_directory

import config
from camera import FeederCamera
from bird_identifier import BirdIdentifier
from database import SightingsDB


# ── Flask app setup ──────────────────────────────────────────────────────────

app = Flask(__name__)
os.makedirs(config.PHOTOS_DIR, exist_ok=True)


# ── Shared state (protected by locks) ───────────────────────────────────────

_camera        = FeederCamera()
_db            = SightingsDB()
_identifier    = None          # lazy-init (skips if no API key in calibration mode)

_annotated_frame    = None        # latest frame with overlays, for MJPEG stream
_annotated_lock     = threading.Lock()

_last_detection_time = None       # datetime of last triggered detection
_detection_lock      = threading.Lock()

# Small ring buffer of recent log messages shown on the dashboard
_log_messages = deque(maxlen=20)
_log_lock     = threading.Lock()


def _log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with _log_lock:
        _log_messages.appendleft(line)


# ── Detection background thread ──────────────────────────────────────────────

def _detection_loop():
    global _last_detection_time, _annotated_frame

    _log("Detection loop started.")
    prev_frame = None

    while True:
        frame = _camera.get_frame()
        if frame is None:
            time.sleep(0.05)
            continue

        # Draw ROI overlay on every displayed frame
        annotated = _camera.draw_roi_overlay(frame)

        # Motion detection
        if prev_frame is not None:
            motion_detected = _camera.detect_motion(frame, prev_frame)

            if motion_detected:
                now = datetime.now()
                with _detection_lock:
                    cooldown_ok = (
                        _last_detection_time is None
                        or (now - _last_detection_time).total_seconds()
                           >= config.MOTION_COOLDOWN_SECS
                    )

                if cooldown_ok:
                    with _detection_lock:
                        _last_detection_time = now

                    _log("Motion detected — capturing snapshot...")
                    threading.Thread(
                        target=_process_detection,
                        args=(frame.copy(),),
                        daemon=True,
                    ).start()

                    # Flash green border on annotated frame
                    import cv2
                    h, w = annotated.shape[:2]
                    cv2.rectangle(annotated, (0, 0), (w - 1, h - 1), (0, 255, 0), 6)

        prev_frame = frame

        with _annotated_lock:
            _annotated_frame = annotated

        time.sleep(0.03)   # ~30 fps


def _process_detection(frame):
    """Save photo and identify bird — runs in its own thread."""
    import cv2

    # Save photo
    photo_path = _camera.capture_snapshot(frame, "bird")
    _log(f"Photo saved: {photo_path}")

    # Identify bird with Claude API
    if _identifier is None:
        _log("Skipping ID — ANTHROPIC_API_KEY not set")
        return

    _log("Sending to Claude for bird identification...")
    result = _identifier.identify(photo_path)

    species     = result["species"]
    common_name = result["common_name"]
    confidence  = result["confidence"]
    description = result["description"]
    notes       = result["notes"]

    if species == "No bird detected":
        _log("No bird in frame — false alarm, skipping log entry.")
        os.remove(photo_path)   # clean up false-alarm photos
        return

    _db.insert_sighting(
        species=species,
        common_name=common_name,
        confidence=confidence,
        photo_path=photo_path,
        description=description,
    )

    label = common_name if common_name and common_name != "Unknown" else species
    _log(f"Identified: {label} ({confidence} confidence). {notes}")


# ── MJPEG stream generator ───────────────────────────────────────────────────

def _generate_stream():
    """Yield MJPEG frames for the /video_feed endpoint."""
    while True:
        with _annotated_lock:
            frame = _annotated_frame

        if frame is None:
            time.sleep(0.05)
            continue

        jpeg = _camera.encode_jpeg(frame)
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
        )
        time.sleep(0.04)   # ~25 fps to the browser


# ── Flask routes ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/video_feed")
def video_feed():
    return Response(
        _generate_stream(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/api/sightings")
def api_sightings():
    sightings = _db.get_recent(config.MAX_SIGHTINGS_DISPLAY)
    return jsonify(sightings)


@app.route("/api/status")
def api_status():
    today_count = _db.count_today()
    recent = _db.get_recent(1)
    last_species = recent[0]["common_name"] if recent else "None yet"

    with _detection_lock:
        last_detection = (
            _last_detection_time.strftime("%H:%M:%S")
            if _last_detection_time else "Never"
        )

    with _log_lock:
        logs = list(_log_messages)

    return jsonify({
        "camera_connected": _camera.cap is not None and _camera.cap.isOpened(),
        "today_count":      today_count,
        "last_species":     last_species,
        "last_detection":   last_detection,
        "log_messages":     logs,
    })


@app.route("/photos/<path:filename>")
def serve_photo(filename):
    return send_from_directory(config.PHOTOS_DIR, filename)


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Bird Feeder Camera App")
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Show camera feed with ROI overlay to tune feeder region settings",
    )
    args = parser.parse_args()

    if args.calibrate:
        camera = FeederCamera()
        camera.run_calibration()
        return

    # Normal run
    global _identifier
    if config.ANTHROPIC_API_KEY and config.ANTHROPIC_API_KEY != "sk-ant-your-key-here":
        try:
            _identifier = BirdIdentifier()
            _log("Claude AI bird identifier ready.")
        except ValueError as exc:
            _log(f"WARNING: {exc}")
    else:
        _log("WARNING: ANTHROPIC_API_KEY not set — bird identification disabled.")
        _log("         Add your API key to .env to enable species identification.")

    if not _camera.start():
        print("\nERROR: Could not connect to camera.")
        print("Check CAMERA_URL in your .env file, or run: python app.py --calibrate")
        sys.exit(1)

    # Start detection loop in background thread
    detection_thread = threading.Thread(target=_detection_loop, daemon=True)
    detection_thread.start()

    _log(f"Web dashboard ready at http://localhost:{config.FLASK_PORT}")
    _log("Open that URL in your browser to see the live feed.")

    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=False,
        threaded=True,
        use_reloader=False,   # disable reloader so background threads work correctly
    )


if __name__ == "__main__":
    main()
