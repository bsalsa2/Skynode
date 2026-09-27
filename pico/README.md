# pico/: servo firmware

MicroPython firmware for the Raspberry Pi Pico WH. It listens for text commands over USB serial and drives the **pan (GP0)** and **tilt (GP1)** servos. Motion is smooth and speed-limited, and angles stay inside calibrated limits.

| File | Job |
|---|---|
| `main.py` | Entry point, runs at power-up. A 50 Hz loop: read serial, run commands, step servos |
| `pantilt.py` | The two-servo mount: runs commands, loads/saves `config.json` |
| `servo.py` | One servo: pulse calibration, angle limits, smooth motion |
| `protocol.py` | Parses command text. No hardware code, so it runs on a laptop too |

## 1. Flash MicroPython (once)

1. Download the latest **Pico W** `.uf2` from <https://micropython.org/download/RPI_PICO_W/>. The WH is a Pico W with headers, so it takes the same firmware. Any version from 1.20 on works.
2. Hold the **BOOTSEL** button, plug the Pico into USB, then release. A drive called `RPI-RP2` appears.
3. Drag the `.uf2` onto that drive. The Pico reboots into MicroPython.

Any laptop works for this. If your main laptop's USB ports are unreliable, do it from the second one.

## 2. Copy the firmware onto the Pico

**Thonny:** in the bottom-right corner, pick *MicroPython (Raspberry Pi Pico)*. Open each of the four `.py` files here, choose *File → Save as… → Raspberry Pi Pico*, and keep the same name. Save `main.py` last.

**Or from the command line** (from the repo root):

```
pip install mpremote
mpremote cp pico/servo.py pico/protocol.py pico/pantilt.py pico/main.py :
mpremote reset
```

## 3. Test it

Wire the servos first (see the [top-level README](../README.md#wiring)). In Thonny, open `main.py` **from the Pico** and press Run (F5). The Shell prints `READY skynode-pico`. Then type:

```
?              → POS P90.0 T45.0
P0             pan swings to 0°
P180           …and across to 180°
T90            tilt to 90°
P90 T45        both at once
SPEED 30       slow down, then try P0 again
HOME           back to P90 T45
```

Moves print nothing on purpose (see the [protocol](#serial-protocol)). Use `?` to see where the servos are.

## 4. Calibrate (about 10 minutes, once per servo)

Every SG90 is a little different. Uncalibrated, "90°" might really be 84°, and each sighting logs these angles, so the log is only as accurate as this step.

Print any free paper protractor and center it under the servo horn.

1. `RAW P 1500` puts the servo roughly at center. Push the horn on so it points at 90°.
2. Lower the pulse step by step (`RAW P 1000`, `RAW P 700`, `RAW P 600`, …) until the horn points at **0°**, and note the number. If the servo **buzzes or stops moving** before it reaches 0°, it has hit its internal end stop. Back off about 30 µs and use that value.
3. Do the same upward for **180°** (`RAW P 2000`, `RAW P 2300`, …).
4. Enter both values, for example `CAL P 540 2380`. Check that `P0`, `P90`, and `P180` now land on the marks.
5. Repeat steps 1–4 for tilt, using `T` instead of `P`.
6. Once the servos are in the bracket, find any angle where parts bind or cables pull, and fence it off. For example, `LIM T 0 100` keeps tilt between 0° and 100°.
7. `SAVE` writes `config.json` to the Pico, and it loads at every boot. `CFG` prints the current settings.

To start over, delete `config.json` in Thonny's file panel (*View → Files*) and reset the Pico.

## Serial protocol

The protocol is one command per line, ended by `\n` or `\r\n`. Commands are case-insensitive, with at most 64 characters per line. Replies end in `\r\n`. At boot the Pico prints `READY skynode-pico`.

| Command | Example | Reply | Notes |
|---|---|---|---|
| `P<deg> T<deg>` | `P92.5 T47` | none | Either axis alone is fine. Out-of-limit values are clamped |
| `HOME` or `H` | | none | Home is pan 90°, tilt 45° (edit in `config.json`) |
| `?` or `STATUS` | | `POS P92.5 T47.0` | Current angles, which trail the target while moving |
| `SPEED <deg/s>` | `SPEED 120` | `OK` | 1–600, default 120 |
| `CAL <P\|T> <min_us> <max_us>` | `CAL P 540 2380` | `OK` | Pulse widths at 0° and 180°, each 400–2600 |
| `LIM <P\|T> <min_deg> <max_deg>` | `LIM T 0 100` | `OK` | 0–180 |
| `RAW <P\|T> <us>` | `RAW P 1500` | `OK` | Calibration only. The next move first snaps back to the last angle, then slews |
| `OFF` | | `OK` | Servos go limp. Any move wakes them |
| `CFG` | | `CFG {…}` | Current settings as JSON |
| `SAVE` | | `OK saved` | Stores settings in `config.json` |
| anything malformed | `P9x` | `ERR <reason>` | |

**Notes for the brain side:**

- Moves are silent, so the brain can stream them at camera frame rate without waiting for acknowledgements. Send `?` when you need the real position.
- Opening the serial port does **not** reboot the Pico (an Arduino does), so you will usually miss `READY`. Send `?` to check that it's alive.
- Only one program can hold the serial port at a time. **Close Thonny before running the brain.**

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Pico disconnects or resets when servos move | The 5 V rail is browning out. Add the capacitor, or use a separate supply (see the power notes in the top README) |
| Servo buzzes at one end | It's pushing against its end stop. Recalibrate (step 4) or tighten `LIM` |
| Servo jitters while idle | Noisy power or a loose ground wire. `OFF` also silences it |
| `WARN bad config.json, using defaults` at boot | The saved file has invalid values. Recalibrate, then `SAVE` |
| Typing in Thonny does nothing | `main.py` isn't running (the Shell shows `>>>` instead of `READY`). Press Run |

## Tests (on the laptop)

The firmware logic is tested with regular Python and a fake `machine` module, so no Pico is needed:

```
python -m unittest discover tests
```
