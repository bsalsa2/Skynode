# brain/

Runs on the laptop now and on a Raspberry Pi 4 later. Every camera frame goes through four steps: **detect → track → control → send**.

| Module | Job |
|---|---|
| `detector.py` | Runs a YOLO model (ONNX) on a frame and returns detections: class, confidence, box |
| `tracker.py` | Picks one target and stays locked on it from frame to frame |
| `controller.py` | Proportional control: how far off-center the target is → new pan/tilt angles |
| `link.py` | Talks to the Pico over Wi-Fi (UDP), USB serial, or not at all |
| `overlay.py` | Draws boxes and status on the preview window |
| `logger.py` | Logs every sighting (plus an hourly "sky clear" check) to `logs/`, with a snapshot of its best moment |
| `dashboard.py` | The live dashboard: a small web server inside the brain, for your browser |
| `dashboard/` | The dashboard page itself: HTML, CSS, JavaScript and fonts, all served locally |
| `config.py` + `config.toml` | Settings: defaults in code, your changes in the TOML file |
| `run.py` | The main loop that wires it all together |

An ADS-B logger and comparison tool are written (see "Compare with real flights" below) but have not yet been run against a real feed.

## Setup

You need Python **3.11 or newer**. From the repo root:

```
python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # Mac / Linux
pip install -r brain/requirements.txt
```

## Get a model

Start with the pretrained **YOLOv8n** COCO model. It has 80 everyday classes, including `airplane` and `bird`. Export it to ONNX once:

**Option A: Google Colab** (nothing to install locally). In a new notebook, run:

```
!pip install ultralytics
!yolo export model=yolov8n.pt format=onnx
from google.colab import files; files.download("yolov8n.onnx")
```

**Option B: locally**, with `pip install ultralytics` and then `yolo export model=yolov8n.pt format=onnx`. Ultralytics pulls in PyTorch, which is a big download, and you only need it for this one step.

Save the file as **`brain/models/yolov8n.onnx`**. YOLO11 and YOLO26 exports work too (`model=yolo11n.pt`); just change `path` in `config.toml`.

## Run it

### 1. Detection only, no Pico needed

```
python -m brain.run
```

A preview window opens with the webcam. Hold up your phone showing a photo of an airplane or a bird. Target-class detections get a **yellow** box, and the locked target turns **green**. Press `q` to quit. To test on footage instead, use `--source planes.mp4`.

While it runs, open **http://localhost:8080/** in your browser for the [live dashboard](#live-dashboard).

### 2. With the Pico

- **Wi-Fi:** set up the Pico's Wi-Fi (see [`pico/README.md`](../pico/README.md#5-wi-fi-optional)), then run `python -m brain.run --link wifi`. The brain finds the Pico automatically. To make Wi-Fi the default, set `type = "wifi"` under `[link]` in `config.toml`.
- **USB:** close Thonny, then run `python -m brain.run --link usb`.

When it connects, the brain reads the Pico's angle limits, home, and current position. That way both sides agree on where the camera is pointing.

### 3. First aiming test

1. With the camera on the pan-tilt mount, hold the airplane photo off to the **right** of the camera's view. The camera should turn right, toward it, and settle with the target near the center cross.
2. If it turns **away**, flip `pan_sign` in `config.toml` (`-1` ↔ `1`). Test tilt the same way, holding the photo above the camera and flipping `tilt_sign` if needed.
3. If it overshoots and wobbles, lower `gain` (try 0.2). If it's sluggish, raise `gain` (up to about 0.5) or raise `SPEED` on the Pico.
4. Set `hfov_deg` to your webcam's field of view, so that "20 pixels off-center" turns into the right number of degrees.

## Live dashboard

While the brain runs, open **http://localhost:8080/** in a browser on the same computer. The brain prints the address when it starts:

```
Logging sightings to C:\Users\you\Skynode\logs
Dashboard: http://localhost:8080/
```

The page comes from the brain itself: no internet, no cloud, no account. It has four tabs:

- **Overview:** the live camera with a box around everything the model sees (the locked target gets a solid label), plus pan, tilt and frames per second. Next to it: sightings, drones and aircraft over the last 24 hours, the most recent sightings, and a chart of sightings by hour.
- **Sightings:** the whole log as cards with snapshots. Filter by time (24 hours, 7 days, all) and category (drone, aircraft, other, sky checks). Click a sighting to see all its details.
- **Nodes:** this node's status: online or offline, uptime, how much of that time the camera was actually watching, and which model, camera and link it uses.
- **Settings:** the settings the brain is running with, read-only. To change them, edit `config.toml` and restart the brain.

The dashboard's settings are under `[dashboard]` in `config.toml`. For one run on another port: `python -m brain.run --port 8081`. Without the dashboard: `--no-dashboard` (or `enabled = false`). The logger keeps working either way.

### Demo mode: your own test videos

No Pico, no camera, no real node yet? Run the whole thing (detector, tracker, logger and dashboard) on a folder of videos:

```
python -m brain.demo C:\Users\you\skynode-videos --model models\your-model.onnx --classes drone,aircraft
```

Then open the dashboard as usual. The videos play one after another, in file-name order, and everything on the dashboard comes from this run:

- It's the same code as `python -m brain.run`. Only the camera is different.
- The dashboard says **DEMO · TEST VIDEOS** at the top, because it isn't a live camera.
- There's no Pico, so **pan and tilt are simulated** from where the target is in the picture: the angles the camera *would* point at to center it.
- It logs to `logs/demo/`, apart from your real log, and **starts that log afresh every time**. Add `--keep-logs` to keep the last demo's sightings.
- Time in the demo is the video's time. A 4-second clip is a 4-second sighting, even with `--fast`.

Options: `--classes` (the model's class names to track, like `drone,aircraft`; the default is `target_classes` in `config.toml`), `--fast` (don't wait for each video's own speed), `--loop` (play the folder again and again), `--port`, `--show` (also open the preview window), and `--exit-when-done` (quit after one pass instead of keeping the dashboard open).

**Keep the videos outside the repo folder.** They're never copied or changed, and the demo refuses a folder inside the repo that git doesn't ignore, so they can't be committed by accident. (`demo_videos/`, `test_videos/` and `videos/` in the repo folder are ignored.) The demo only looks at video files directly in the folder you give it (`.mp4 .mov .m4v .avi .mkv .webm`), not in sub-folders.

### What counts as a sighting

A sighting is one continuous lock: from the frame the tracker locks on to the frame it gives up (after `max_missed_frames` frames without seeing the target). Locks shorter than `min_duration_s` (half a second) are most likely the detector blinking, so they aren't logged. For each sighting the log keeps when it started and ended, what the model called it, its best confidence, where the camera pointed at that best moment, and a snapshot of that frame. The terminal shows each one as it's saved:

```
LOGGED airplane 4.2s peak 0.91
```

The model's class decides the category: names in `drone_classes` are **drone**, names in `aircraft_classes` are **aircraft**, and anything else is **other**. With the COCO model that means `bird` sightings are filed under *other*, even though small drones often show up as birds. A custom drone model fixes that.

While nothing is being tracked, the logger also writes a **sky check** once an hour, on the hour (`heartbeat_min = 60`). It proves the node was watching and saw nothing, so a gap in the log means "the brain wasn't running", not "empty sky".

### Where the logs go

```
logs/skynode.db                          every sighting and sky check (SQLite)
logs/snapshots/20261007-140217-001.jpg   the best frame of that sighting
```

`logs/` sits in the repo folder, and git ignores it, so your sightings never end up on GitHub. `skynode.db` is one ordinary SQLite file, and each record is committed the moment a sighting ends, so a crash or a power cut loses nothing that was already logged. The dashboard shows the last 7 days; older sightings stay in the database. To start fresh, delete the folder while the brain isn't running.

To look at it yourself, open it with any SQLite tool (DB Browser for SQLite, or `sqlite3 logs/skynode.db`). One row per sighting or sky check, in a table called `sightings`; `started` and `ended` are unix times in seconds:

```
sqlite3 logs/skynode.db "SELECT id, category, class_name, confidence FROM sightings WHERE kind = 'sighting' ORDER BY started DESC LIMIT 5"
```

Earlier versions wrote one `sightings-YYYY-MM-DD.jsonl` file per day. If you have those, they're imported into the database the first time you start the brain, then renamed to `.jsonl.imported`.

### Export a spreadsheet (to compare with ADS-B)

On the **Sightings** tab, pick a time range and a category, then click **Export CSV**. You get `skynode-sightings.csv`, one row per sighting, newest first:

```
id,kind,category,class_name,start_iso,end_iso,duration_s,confidence,pan,tilt,frames,snapshot
```

`start_iso` and `end_iso` are your local time with its offset from UTC, like `2026-10-07T14:02:17+02:00`. ADS-B flight data is usually in UTC, and the offset makes the conversion exact. Line the times up, then use `pan` and `tilt` to check that the aircraft was where the camera pointed. The export covers what the dashboard shows (the last 7 days, up to 10,000 rows); for anything older, query `logs/skynode.db`.

### Compare with real flights (ADS-B)

Planes broadcast their position, and free public feeds (adsb.lol, airplanes.live) share it with no account. The feeds only show what is flying *now*, so a small logger has to run next to the brain and write it down:

```
python -m brain.adsb             # leave it running while the brain runs
python -m brain.adsb_compare     # afterwards: which sightings does the flight record explain?
```

**Tell it where the camera is, without putting your home on GitHub.** Set `SKYNODE_LAT`, `SKYNODE_LON` (and optionally `SKYNODE_ALT_M`), or create `brain/location.local.toml` with `lat = ...`, `lon = ...`, `alt_m = ...`. Git ignores that file, and the location is never read from `config.toml`. By default the request to the feed uses your position rounded to about 1 km, with a slightly larger radius, and the exact distances are worked out on your computer. Add `--exact` to send the precise position instead.

It writes `logs/adsb_log.csv` (every aircraft within 25 km, with its azimuth and elevation in your sky) and `logs/adsb_polls.csv` (each time the feed answered). The second file is what tells "no aircraft overhead" from "the logger wasn't running". Those sightings are reported as `no_data` and left out of every percentage.

`adsb_compare` reports how many aircraft sightings had a real flight nearby, and how many drone sightings did (possible misclassifications). Two honest limits: it means an aircraft was *nearby*, not that the camera was pointed at it, and planes without a transponder, such as gliders and most drones, never show up. It measures agreement with the public flight record, not accuracy. Treat each mismatch as a lead to check in the snapshot.

### Open it from your phone

By default only the computer running the brain can open the dashboard. To open it from a phone or another laptop on the same Wi-Fi:

1. Set `host = "0.0.0.0"` under `[dashboard]` in `config.toml`, then restart the brain.
2. Find the computer's IP address. Windows: run `ipconfig` and look for *IPv4 Address*. Mac: System Settings → Wi-Fi → Details. Linux or the Pi: `hostname -I`.
3. On the phone, open `http://<that address>:8080/`, for example `http://192.168.1.42:8080/`.

> **Privacy warning:** with `host = "0.0.0.0"`, **anyone on the same network can open the dashboard and watch your camera. There is no password.** Only do this on your own home network, never on school, café or other public Wi-Fi, and set it back to `"127.0.0.1"` when you're done. Point the camera at the sky, not at the neighbours' windows.

On Windows, the firewall may block the phone. Allow Python through it for **Private** networks, the same as for the Pico's Wi-Fi link.

Other web sites can't use the dashboard, even while you have it open. A page somewhere else can't show your camera inside itself, peek at your snapshots, or take up the live stream's places (there are 4). The brain only answers the dashboard's own page, an address you type in or bookmark, and plain links to its front page.

### Try it in the cloud (GitHub Codespaces)

No install and nothing stored on your own computer. A Codespace is a computer GitHub runs for you, and the dashboard opens in a browser tab. It uses a video file as the camera (a cloud computer has no webcam).

1. Download two files to your device: the model `skynode-v3-<date>.onnx` (from Drive ▸ skynode ▸ models) and one short video of a plane or drone.
2. On github.com open the repo, use the branch menu to pick the branch you want, then **Code ▸ Codespaces ▸ Create codespace**. Wait about 2 minutes: `.devcontainer/devcontainer.json` installs the packages for you.
3. In the file list on the left, drag the `.onnx` into `brain/models/` and the video into the top folder (call it `clip.mp4`).
4. Open the terminal (Terminal ▸ New Terminal) and run:
   ```
   python -m brain.run --config brain/config.v3.toml --source clip.mp4 --loop
   ```
   If your model file has a different name, edit `path` in `brain/config.v3.toml`.
5. When it prints `In GitHub Codespaces, open https://...`, click that link (or open the **Ports** tab and click the globe next to port 8080).
6. Press Ctrl+C in the terminal to stop. **Stop the Codespace** when you're done (github.com/codespaces ▸ the `...` menu ▸ Stop). It also stops itself after a while, and the free monthly allowance is limited.

How it stays safe: the dashboard answers only your own Codespace's address, not the rest of `app.github.dev`. Codespaces ports are private (you must be signed in to GitHub) unless you change them to Public, so **don't make port 8080 public**.

Not verified: the live camera picture goes through GitHub's proxy, and I couldn't test how it handles a continuous stream. If the picture stalls, the stat tiles, sightings and chart still work.

## Swap in your own model

No local GPU? Train in Google Colab with phone videos: see [`training/`](../training/README.md).

1. Train with Ultralytics (YOLOv8, YOLO11, or YOLO26), then export: `yolo export model=best.pt format=onnx`.
2. Copy the `.onnx` file into `brain/models/` and update `config.toml`:
   ```toml
   [model]
   path = "models/skynode-drone.onnx"
   target_classes = ["drone", "airplane", "helicopter"]
   ```
3. That's it. The class names are stored inside the `.onnx` file. If a target class isn't in the model, the brain stops and lists the classes the model does know.

Exports made with `nms=True` work too.

## What to expect from the COCO model

- **COCO has no `drone` or `helicopter` class.** Small drones tend to show up as `bird` (sometimes `airplane` or `kite`), which is why `bird` is a default target. It's also the main reason to train your own model.
- **Real birds will trigger it too.** That's the cost of using a stand-in class.
- **Small targets are hard.** A distant aircraft may be only a few pixels wide once the frame is shrunk to 640 × 640. A narrower camera lens (zoom) gains more range than a bigger model does.
- **On a Pi 4**, export with `imgsz=320`. That's roughly 4× faster than 640, at the cost of detection range.

## License note

Ultralytics YOLO weights and anything exported from them are licensed **AGPL-3.0**. Skynode's code never imports Ultralytics (it runs the exported file with ONNX Runtime), but the model file itself comes under Ultralytics' license. That's fine for a personal or open-source project. For a commercial product, plan on either an Ultralytics Enterprise license or training an Apache-2.0 detector (such as YOLOX or RT-DETR) on your own dataset.

## Troubleshooting

| Message or symptom | Fix |
|---|---|
| `No Pico answered on UDP port 5005` | Make sure the Pico shows `WIFI up` and is on the same network. On Windows, allow Python through the firewall for **Private** networks and set your Wi-Fi's network profile to Private. Or set `wifi_host` to the IP address the Pico printed |
| `No Pico found on USB` | Some USB cables only carry power; use a data cable |
| `Can't open COM…` / `/dev/ttyACM0` | Thonny is holding the port; close it |
| `Can't open camera` | Another app (Zoom, Teams, …) has the webcam. For a second camera, use `source = 1` |
| Camera swings away from the target | Flip `pan_sign` or `tilt_sign` |
| Camera wobbles around the target | Lower `gain` |
| `Target class(es) … aren't in this model` | Check the spelling. The message lists every class the model knows |
| Pan/tilt run to their limits when testing on a video file | Expected: a video can't move, so the target never gets centered |
| `WARN the dashboard can't start on 127.0.0.1:8080` | Another program (or a second copy of the brain) is using port 8080. Run with `--port 8081`, or change `port` in `config.toml`. Tracking and logging keep going without the dashboard |
| The dashboard says OFFLINE | The brain isn't running, or the camera stopped sending frames. Check the terminal |
| The phone can't open the dashboard | Set `host = "0.0.0.0"`, use the computer's IP address (not `localhost`), and stay on the same Wi-Fi. On Windows, allow Python through the firewall for Private networks |
| `403`: *Open the dashboard by this computer's address* | You opened it by a name with a real domain, like a custom DNS name `skynode.example.com`. To block a trick called DNS rebinding, the dashboard only answers to `localhost`, an IP address (`http://192.168.1.42:8080/`), the computer's plain name (`raspberrypi`) or a home-network name like `raspberrypi.local`. Use one of those, or list the one exact name you trust in `allowed_hosts` in `config.toml` (GitHub Codespaces addresses are added for you) |
| `403`: *Only the dashboard's own page can load this* | Another web site (or another app on this computer) tried to load the camera or the log. That's blocked on purpose. Open the dashboard itself, e.g. `http://localhost:8080/` |

## Tests

```
python -m unittest discover tests
```

The detector tests build tiny fake models, which needs one extra package: `pip install onnx`. Without it they're skipped. The demo tests make their own tiny videos, and need numpy, OpenCV and onnxruntime (the same as running the brain).
