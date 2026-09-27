# brain/

Runs on the laptop now and on a Raspberry Pi 4 later. It turns camera frames into servo commands and sighting records.

Planned modules. Each one is small and has a single job, so it can be reused on other platforms:

| Module | Job |
|---|---|
| `detector.py` | Load the ONNX model and turn a frame into a list of detections (class, confidence, box) |
| `tracker.py` | Pick one target across frames and report its pixel offset from frame center |
| `controller.py` | Proportional control: pixel offset → pan/tilt angle correction |
| `link.py` | USB serial connection to the Pico (`P<deg> T<deg>` protocol, see `pico/README.md`) |
| `logger.py` | Write sightings (time, class, confidence, pan, tilt) to disk |
| `run.py` | The main loop that wires them together |
