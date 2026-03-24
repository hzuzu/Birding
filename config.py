"""
config.py — Central configuration for the Bird Feeder Camera App.
Reads settings from the .env file. All other modules import from here.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _int(key, default):
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


def _float(key, default):
    try:
        return float(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


def _optional_int(key):
    val = os.getenv(key)
    if val is None or val.strip() == "":
        return None
    try:
        return int(val)
    except ValueError:
        return None


# ── Camera ──────────────────────────────────────────────────────────────────
_raw_url = os.getenv("CAMERA_URL", "0")
try:
    CAMERA_URL = int(_raw_url)   # "0" → use USB webcam
except ValueError:
    CAMERA_URL = _raw_url        # RTSP URL string

# ── Region of Interest (rectangle, always used) ─────────────────────────────
ROI_X      = _int("ROI_X",      320)
ROI_Y      = _int("ROI_Y",      180)
ROI_WIDTH  = _int("ROI_WIDTH",  640)
ROI_HEIGHT = _int("ROI_HEIGHT", 360)

# ── Region of Interest (ellipse, optional — overrides rectangle when set) ───
ROI_CENTER_X  = _optional_int("ROI_CENTER_X")
ROI_CENTER_Y  = _optional_int("ROI_CENTER_Y")
ROI_SEMI_MAJOR = _optional_int("ROI_SEMI_MAJOR")
ROI_SEMI_MINOR = _optional_int("ROI_SEMI_MINOR")
ROI_ANGLE      = _int("ROI_ANGLE", 0)

# True when all ellipse params are provided
USE_ELLIPSE_ROI = all(
    v is not None
    for v in [ROI_CENTER_X, ROI_CENTER_Y, ROI_SEMI_MAJOR, ROI_SEMI_MINOR]
)

# ── Motion detection ────────────────────────────────────────────────────────
MOTION_THRESHOLD     = _int("MOTION_THRESHOLD",     500)
MOTION_COOLDOWN_SECS = _int("MOTION_COOLDOWN_SECS", 10)
MIN_CONTOUR_AREA     = _int("MIN_CONTOUR_AREA",      300)

# ── Claude AI ───────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

# ── Flask web server ─────────────────────────────────────────────────────────
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = _int("FLASK_PORT", 5000)
MAX_SIGHTINGS_DISPLAY = _int("MAX_SIGHTINGS_DISPLAY", 50)

# ── Storage ──────────────────────────────────────────────────────────────────
PHOTOS_DIR = os.getenv("PHOTOS_DIR", "./photos")
DB_PATH    = os.getenv("DB_PATH",    "./birding.db")
