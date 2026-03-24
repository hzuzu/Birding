"""
camera.py — Camera connection, ROI masking, and motion detection
for the Bird Feeder Camera App.

The feeder is viewed from the side, so the ring appears as an arc/ellipse
in the frame (not a full circle from above). Detection uses either:
  - A rectangle (default, easy to configure)
  - An ellipse (optional, better fits the arc shape when tuned)
"""
import os
import threading
import time
from datetime import datetime

import cv2
import numpy as np

import config


class FeederCamera:
    def __init__(self):
        self.cap = None
        self._frame = None
        self._frame_lock = threading.Lock()
        self._running = False
        self._thread = None

    # ── Connection ───────────────────────────────────────────────────────────

    def connect(self):
        """
        Open the camera. Tries the configured CAMERA_URL first.
        If that is an RTSP URL and it fails, falls back to USB webcam (index 0).
        Returns True on success.
        """
        self.cap = cv2.VideoCapture(config.CAMERA_URL)
        if self.cap.isOpened():
            print(f"[camera] Connected to: {config.CAMERA_URL}")
            return True

        # Fallback to USB webcam
        if config.CAMERA_URL != 0:
            print(f"[camera] Could not open {config.CAMERA_URL} — trying USB webcam (index 0)")
            self.cap = cv2.VideoCapture(0)
            if self.cap.isOpened():
                print("[camera] Connected to USB webcam (index 0)")
                return True

        print("[camera] ERROR: No camera available. Check CAMERA_URL in .env")
        return False

    def start(self):
        """Start background thread that continuously reads frames."""
        if not self.connect():
            return False
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._running = False
        if self.cap:
            self.cap.release()

    def _read_loop(self):
        while self._running:
            ret, frame = self.cap.read()
            if ret:
                with self._frame_lock:
                    self._frame = frame
            else:
                time.sleep(0.05)

    def get_frame(self):
        """Return the latest frame (numpy BGR array) or None."""
        with self._frame_lock:
            return self._frame.copy() if self._frame is not None else None

    # ── ROI mask ─────────────────────────────────────────────────────────────

    def create_roi_mask(self, frame):
        """
        Build a binary mask covering the feeder area.
        Uses an ellipse if all ellipse params are set in .env, otherwise a rectangle.
        """
        h, w = frame.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)

        if config.USE_ELLIPSE_ROI:
            cv2.ellipse(
                mask,
                (config.ROI_CENTER_X, config.ROI_CENTER_Y),
                (config.ROI_SEMI_MAJOR, config.ROI_SEMI_MINOR),
                config.ROI_ANGLE,
                0, 360,
                255, -1,
            )
        else:
            x, y = config.ROI_X, config.ROI_Y
            mask[y : y + config.ROI_HEIGHT, x : x + config.ROI_WIDTH] = 255

        return mask

    def draw_roi_overlay(self, frame):
        """Draw the ROI region on a frame for calibration / live display."""
        overlay = frame.copy()
        color = (0, 200, 255)   # orange-yellow
        thickness = 2

        if config.USE_ELLIPSE_ROI:
            cv2.ellipse(
                overlay,
                (config.ROI_CENTER_X, config.ROI_CENTER_Y),
                (config.ROI_SEMI_MAJOR, config.ROI_SEMI_MINOR),
                config.ROI_ANGLE,
                0, 360,
                color, thickness,
            )
            cv2.putText(
                overlay, "Feeder ROI (ellipse)",
                (config.ROI_CENTER_X - 80, config.ROI_CENTER_Y - config.ROI_SEMI_MINOR - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2,
            )
        else:
            x, y = config.ROI_X, config.ROI_Y
            cv2.rectangle(
                overlay,
                (x, y),
                (x + config.ROI_WIDTH, y + config.ROI_HEIGHT),
                color, thickness,
            )
            cv2.putText(
                overlay, "Feeder ROI (rectangle)",
                (x, y - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2,
            )

        return overlay

    # ── Motion detection ─────────────────────────────────────────────────────

    def detect_motion(self, frame, prev_frame):
        """
        Compare two frames inside the feeder ROI.
        Returns True if motion exceeds the configured threshold.
        """
        mask = self.create_roi_mask(frame)

        gray      = cv2.cvtColor(frame,      cv2.COLOR_BGR2GRAY)
        gray_prev = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

        gray      = cv2.GaussianBlur(gray,      (21, 21), 0)
        gray_prev = cv2.GaussianBlur(gray_prev, (21, 21), 0)

        diff = cv2.absdiff(gray_prev, gray)
        diff = cv2.bitwise_and(diff, diff, mask=mask)

        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        thresh = cv2.dilate(thresh, None, iterations=2)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        motion_area = sum(cv2.contourArea(c) for c in contours
                         if cv2.contourArea(c) >= config.MIN_CONTOUR_AREA)

        return motion_area >= config.MOTION_THRESHOLD

    # ── Snapshot saving ──────────────────────────────────────────────────────

    def capture_snapshot(self, frame, species_hint="bird"):
        """
        Save a JPEG of the current frame to photos/YYYY-MM-DD/.
        Returns the saved file path.
        """
        now = datetime.now()
        date_dir = os.path.join(config.PHOTOS_DIR, now.strftime("%Y-%m-%d"))
        os.makedirs(date_dir, exist_ok=True)

        safe_species = "".join(c if c.isalnum() or c in "-_" else "_" for c in species_hint)
        filename = f"{safe_species}_{now.strftime('%H-%M-%S')}.jpg"
        path = os.path.join(date_dir, filename)

        cv2.imwrite(path, frame)
        return path

    # ── MJPEG frame encoding ─────────────────────────────────────────────────

    def encode_jpeg(self, frame):
        """Encode a BGR frame to JPEG bytes for the live stream."""
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return buf.tobytes()

    # ── Calibration mode ─────────────────────────────────────────────────────

    def run_calibration(self):
        """
        Show a live window with the ROI overlay drawn.
        Lets the user visually verify that the ROI covers the feeder ring.
        Press 'q' to quit.
        """
        print("\n[calibration] Opening camera window — press Q to quit.")
        print("[calibration] Adjust ROI_X/Y/WIDTH/HEIGHT (or ellipse params)")
        print("[calibration] in your .env file until the box covers the feeder ring.\n")

        if not self.connect():
            return

        while True:
            ret, frame = self.cap.read()
            if not ret:
                continue

            annotated = self.draw_roi_overlay(frame)
            cv2.putText(
                annotated,
                "CALIBRATION — press Q to quit",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2,
            )
            cv2.imshow("Bird Feeder Calibration", annotated)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        cv2.destroyAllWindows()
        self.cap.release()
        print("[calibration] Done. Edit .env and run again to refine.")
