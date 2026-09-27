# brain/

Runs on the laptop now and on a Raspberry Pi 4 later. Every camera frame goes through four steps: **detect → track → control → send**.

| Module | Job |
|---|---|
| `detector.py` | Runs a YOLO model (ONNX) on a frame and returns detections: class, confidence, box |
| `tracker.py` | Picks one target and stays locked on it from frame to frame |
| `controller.py` | Proportional control: how far off-center the target is → new pan/tilt angles |
| `link.py` | Talks to the Pico over Wi-Fi (UDP), USB serial, or not at all |
| `overlay.py` | Draws boxes and status on the preview window |
| `config.py` + `config.toml` | Settings: defaults in code, your changes in the TOML file |
| `run.py` | The main loop that wires it all together |

Next up: `logger.py`, the sighting logger.

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

### 2. With the Pico

- **Wi-Fi:** set up the Pico's Wi-Fi (see [`pico/README.md`](../pico/README.md#5-wi-fi-optional)), then run `python -m brain.run --link wifi`. The brain finds the Pico automatically. To make Wi-Fi the default, set `type = "wifi"` under `[link]` in `config.toml`.
- **USB:** close Thonny, then run `python -m brain.run --link usb`.

When it connects, the brain reads the Pico's angle limits, home, and current position. That way both sides agree on where the camera is pointing.

### 3. First aiming test

1. With the camera on the pan-tilt mount, hold the airplane photo off to the **right** of the camera's view. The camera should turn right, toward it, and settle with the target near the center cross.
2. If it turns **away**, flip `pan_sign` in `config.toml` (`-1` ↔ `1`). Test tilt the same way, holding the photo above the camera and flipping `tilt_sign` if needed.
3. If it overshoots and wobbles, lower `gain` (try 0.2). If it's sluggish, raise `gain` (up to about 0.5) or raise `SPEED` on the Pico.
4. Set `hfov_deg` to your webcam's field of view, so that "20 pixels off-center" turns into the right number of degrees.

## Swap in your own model

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

## Tests

```
python -m unittest discover tests
```

The detector tests build tiny fake models, which needs one extra package: `pip install onnx`. Without it they're skipped.
