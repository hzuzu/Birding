# Bird Feeder Camera App

An AI-powered bird identification system for your backyard feeder. The app connects to an outdoor IP camera, watches for birds landing on your circular ring feeder, automatically takes a photo, and uses Claude AI to identify the species. A live web dashboard shows the camera stream and a running log of every bird sighting.

---

## What You Need

| Item | Purpose | Where to Get |
|------|---------|-------------|
| **Outdoor IP camera** | Films the feeder | Amazon / Best Buy (see recommendations below) |
| **A computer** (Windows/Mac/Linux) | Runs the app | Your existing computer or a Raspberry Pi |
| **Python 3.11 or newer** | Runs the app code | python.org (free) |
| **Anthropic API key** | Claude AI bird ID | console.anthropic.com (free tier available) |
| **Home WiFi router** | Connects camera to computer | You already have this |

---

## Camera Recommendations

### Best Choice for Beginners: Reolink E1 Outdoor (~$60)

**Why choose this:** It works with this app out of the box — no special configuration needed beyond setting a password.

- Fully weatherproof (IP67) — handles Kansas heat (131°F) and cold (-14°F)
- Night vision for dawn/dusk bird activity
- Connects to your home WiFi
- Video streaming (RTSP) works without any firmware modification

**RTSP URL format:**
```
rtsp://admin:YOUR_PASSWORD@192.168.1.X//h264Preview_01_main
```

### Budget Option: Wyze Cam v3 (~$35)

Works well but requires a **one-time firmware flash** to enable RTSP streaming:
1. Download RTSP firmware v4.61.0.1 from Wyze's website
2. Copy `demo.bin` to a microSD card → insert into camera while unplugged → plug in
3. Once flashed, enable RTSP in the Wyze app under Advanced Settings

**RTSP URL format:**
```
rtsp://admin:YOUR_PASSWORD@192.168.1.X/live
```

### Premium Option: Reolink RLC-810A (~$90)

One ethernet cable provides both power and internet (PoE) — no outdoor outlet needed. 4K resolution gives the best bird identification accuracy. Same setup as the E1 Outdoor.

### Camera Placement

- **Position:** Mount the camera on the side of the feeder at roughly ring height, 2–5 feet away
- **Angle:** Point slightly inward so the feeder ring fills most of the frame
- **Sun:** Avoid pointing toward the east (morning sun) or west (afternoon sun) — glare makes identification harder; north-facing works best in Kansas
- Birds will appear in profile or from behind — the AI handles this fine

---

## Step-by-Step Setup

### Step 1: Install Python

1. Go to [python.org/downloads](https://python.org/downloads)
2. Download Python 3.11 or newer
3. **Windows:** during install, check "Add Python to PATH"
4. Verify: open a terminal (Command Prompt on Windows, Terminal on Mac) and type:
   ```
   python --version
   ```
   You should see `Python 3.11.x` or higher.

### Step 2: Download the App

```bash
git clone https://github.com/hzuzu/Birding.git
cd Birding
```

Or download the ZIP from GitHub and extract it.

### Step 3: Install Required Libraries

```bash
pip install -r requirements.txt
```

This installs: Flask (web server), OpenCV (camera/video), Anthropic (AI), and a few others.

### Step 4: Get Your Claude AI API Key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up for a free account
3. Click **"API Keys"** in the left menu
4. Click **"Create Key"** → copy the key (starts with `sk-ant-`)
5. Keep this key private — treat it like a password

### Step 5: Set Up Your Configuration File

```bash
cp .env.example .env
```

Now open `.env` in a text editor (Notepad on Windows, TextEdit on Mac). Fill in:

```dotenv
# Your camera's RTSP URL — replace the IP and password:
CAMERA_URL=rtsp://admin:mypassword@192.168.1.100//h264Preview_01_main

# Your Claude AI API key:
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**To find your camera's IP address:**
- Log into your router (usually at 192.168.1.1 or 192.168.0.1 in your browser)
- Look for "Connected Devices" or "DHCP Clients"
- Find your camera by its name (e.g., "Reolink-E1")

**To test the RTSP URL before running the app:**
- Download [VLC Media Player](https://www.videolan.org/vlc/) (free)
- Open VLC → Media → Open Network Stream → paste your RTSP URL → Play
- You should see your camera feed

### Step 6: Calibrate the Detection Zone

The app needs to know where your feeder ring appears in the camera frame. Run:

```bash
python app.py --calibrate
```

An orange/yellow rectangle will appear on the camera feed. This is the "Region of Interest" — the zone where the app watches for motion.

Adjust the rectangle in your `.env` file so it tightly covers the feeder ring:

```dotenv
ROI_X=320      # left edge of box (pixels from left side of image)
ROI_Y=180      # top edge of box (pixels from top of image)
ROI_WIDTH=640  # width of box in pixels
ROI_HEIGHT=360 # height of box in pixels
```

Run `python app.py --calibrate` again after each change to see the result.
Press **Q** to close the calibration window.

**Tips:**
- Make the box just big enough to cover the feeder ring — don't include background trees
- If leaves/wind keep triggering false detections, increase `MOTION_THRESHOLD` in `.env`

### Step 7: Start the App

```bash
python app.py
```

You'll see:
```
[HH:MM:SS] Claude AI bird identifier ready.
[HH:MM:SS] Web dashboard ready at http://localhost:5000
```

### Step 8: Open the Dashboard

Open your web browser and go to:
```
http://localhost:5000
```

You'll see:
- **Left side:** Live camera feed with the detection zone outlined
- **Right side:** Sightings log (updates automatically every 5 seconds)
- **Status bar:** Camera connection status, birds seen today, last species spotted

When a bird lands on the feeder:
1. Motion is detected in the feeder zone
2. A photo is saved to `photos/YYYY-MM-DD/`
3. Claude AI identifies the species (takes 2–5 seconds)
4. A toast notification pops up and the sighting appears in the log

---

## Common Kansas Birds to Expect

Based on your Overland Park location, you'll likely spot:

| Bird | Season | Notes |
|------|---------|-------|
| Northern Cardinal | Year-round | Bright red males, brown females |
| American Goldfinch | Year-round | Bright yellow in summer |
| House Sparrow | Year-round | Small, brown, very common |
| Carolina Chickadee | Year-round | Black cap, white cheeks |
| White-breasted Nuthatch | Year-round | Walks down tree trunks headfirst |
| American Robin | Year-round | Orange-red breast |
| Mourning Dove | Year-round | Soft gray, feeds on ground |
| Blue Jay | Year-round | Bright blue, noisy |
| Dark-eyed Junco | Winter | Slate gray with white belly |
| White-throated Sparrow | Winter | Migrant, white throat stripe |

---

## Troubleshooting

### Camera won't connect

1. **Check RTSP URL:** Open VLC → Media → Open Network Stream → paste the URL. If VLC can't connect, the URL or password is wrong.
2. **Check IP address:** Camera IPs can change after reboot. Check your router's device list again.
3. **Enable RTSP:** In the Reolink app → Camera Settings → Advanced → make sure RTSP is ON.
4. **Firewall:** On Windows, allow Python through Windows Firewall if prompted.
5. **Try webcam:** Temporarily set `CAMERA_URL=0` in `.env` to test with your laptop camera.

### No birds being detected / too many false alarms

- **Too sensitive** (wind, leaves triggering): Increase `MOTION_THRESHOLD` (try 1000–2000) and `MIN_CONTOUR_AREA` (try 500–1000) in `.env`
- **Not sensitive enough** (birds not detected): Decrease `MOTION_THRESHOLD` (try 200–300)
- **Wrong zone:** Run `python app.py --calibrate` and adjust ROI values until the box covers only the feeder ring

### Bird identification says "Unknown"

- **Check API key:** Make sure `ANTHROPIC_API_KEY` in `.env` starts with `sk-ant-` and has no extra spaces
- **Check internet:** The app needs internet to reach the Claude API
- **Image too dark:** Consider adding a spotlight near the feeder for nighttime use (the AI needs a reasonably lit image)

### "Module not found" error

Run `pip install -r requirements.txt` again. Make sure you're in the `Birding` folder.

### Dashboard shows "Camera stream unavailable"

The MJPEG stream isn't reachable. Make sure `python app.py` is running and try refreshing the browser page. Check the terminal window for error messages.

---

## Optional: Run on Raspberry Pi

A Raspberry Pi 4 (2GB RAM minimum) works well for 24/7 operation:

1. Install Raspberry Pi OS (64-bit)
2. Follow the same setup steps above
3. To start on boot, create a systemd service or use `cron @reboot`
4. Access the dashboard from any device on your network at `http://raspberrypi.local:5000`

---

## File Structure

```
Birding/
├── app.py              # Main app — run this to start
├── camera.py           # Camera connection and motion detection
├── bird_identifier.py  # Claude AI species identification
├── database.py         # Stores sightings history
├── config.py           # Reads settings from .env
├── requirements.txt    # Python libraries to install
├── .env.example        # Settings template (copy to .env)
├── .env                # Your private settings (NOT in git)
├── templates/
│   └── index.html      # Web dashboard
├── static/
│   └── style.css       # Dashboard styling
├── photos/             # Saved bird photos (created automatically)
│   └── YYYY-MM-DD/
│       └── robin_14-32-05.jpg
└── birding.db          # SQLite sightings database (created automatically)
```

---

## Privacy and Cost

- **Photos** are saved only on your computer — never uploaded anywhere except the image sent to Claude API for identification
- **Claude API cost** is very low — about $0.001 per identification (roughly 1,000 birds for $1). The free tier covers getting started.
- **No subscription** — you pay only for what you use

---

## Questions?

Open an issue on GitHub or check [Anthropic's documentation](https://docs.anthropic.com) for API help.
