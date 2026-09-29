# hardware/

Parametric pan-tilt mount for two SG90 servos and a small USB webcam.

**Source of truth: [`pantilt.py`](pantilt.py) (CadQuery).** It builds every printed part as an editable STEP file plus an STL. [`pantilt.scad`](pantilt.scad) is the original OpenSCAD version, kept for reference: same parameters and identical geometry, but edit the CadQuery script first, and copy any change to the SCAD file only if you still use it.

| File | What it is |
|---|---|
| `pantilt.py` | The design (CadQuery). All dimensions are parameters at the top |
| `pantilt.scad` | Original OpenSCAD version (reference only) |
| `pantilt_base.step` / `.stl` | Base: holds the pan servo (shaft up) and screws down with 4× M3 |
| `pantilt_yoke.step` / `.stl` | Yoke: sits on the pan horn, holds the tilt servo, carries the M3 pivot |
| `pantilt_camera_arm.step` / `.stl` | Camera arm: webcam cradle on the tilt horn and pivot. Strap the camera with two zip ties |

A two-axis mount needs three moving links (fixed, panning, tilting), so it prints as three parts.

## Before printing

Measure your servo and camera with calipers and edit the parameters: `servo_l/w/h`, `tab_z`, `horn_seat_z`, the horn sizes, and `cam_w/h/d`. Then rebuild all STEP and STL files from the repo root:

```
pip install cadquery
python hardware/pantilt.py
```

The STEP files open in FreeCAD, Fusion 360, Onshape, or SolidWorks for further editing.

Print in PLA or PETG, 0.2 mm layers, 3 walls, 25–40 % infill, no supports. The parts are already oriented flat side down.

## Assembly

1. **Base:** drop the pan servo into the base, with its lead through a cable slot, and screw the tabs down (M2 self-tapping; SG90s come with these).
2. **Yoke:** press a double-arm horn into the recess under the yoke and fix it with two M2 screws from the top. Center the pan servo (`HOME`, 90°), set the yoke facing forward, press the horn onto the spline, and drive the horn screw through the center hole.
3. **Tilt servo:** push it through the yoke's window from the outside, shaft pointing in, and screw its tabs to the upright.
4. **Camera arm:** fix a horn into the left cheek's recess, put the arm between the uprights, press the horn onto the tilt servo (servo at its level angle), and add the horn screw. On the other side, an M3 × 12 screw with a washer goes through the yoke's pivot hole into the arm.
5. Zip-tie the webcam into the cradle, lens forward.
