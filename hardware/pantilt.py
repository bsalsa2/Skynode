"""pantilt.py — parametric two-axis pan-tilt mount for SG90 servos + a small USB webcam (CadQuery).

This is the source of truth for the printed parts. pantilt.scad is the
original OpenSCAD version, kept for reference; both use the same parameters.

Three printed parts (a two-axis mount needs three links: fixed, panning, tilting):
    base        holds the pan servo, shaft up; screws down to a board
    yoke        sits on the pan servo's horn; holds the tilt servo and the pivot
    camera_arm  cradle for the webcam; hangs on the tilt horn and an M3 pivot

Build everything (STEP + STL per part, plus a preview STL of the assembly):
    pip install cadquery
    python hardware/pantilt.py

All sizes in mm. MEASURE YOUR SERVO: SG90 clones vary by a few tenths.
"""
import math
from pathlib import Path

import cadquery as cq

# ---------- SG90 servo ----------
servo_l = 22.5            # body length (along the mounting tabs)
servo_w = 12.0            # body width
servo_h = 22.7            # body height, bottom to top of case (without the gear boss)
tab_span = 32.3           # length across both mounting tabs
tab_t = 2.5               # tab thickness
tab_z = 15.9              # servo bottom to the UNDERSIDE of the tabs
tab_hole_spacing = 27.8   # center-to-center of the two tab screw holes
shaft_offset = 5.9        # output shaft axis, measured from the near end of the body
horn_seat_z = 30.0        # servo bottom to the underside of the fitted horn's arm

# ---------- Standard SG90 double-arm horn ----------
horn_len = 32.0           # tip to tip
horn_hub_d = 7.4          # arm width at the hub
horn_tip_d = 4.2          # arm width at the tips
horn_t = 1.6              # arm thickness
horn_hole_r = (8, 12)     # radii of screw holes that fix the horn to the part
horn_screw_d = 2.2        # clearance for M2 self-tapping screws into the horn

# ---------- Webcam ----------
cam_w = 40                # across (side to side)
cam_h = 30                # tall
cam_d = 30                # deep (front to back, lens pointing forward)

# ---------- General ----------
wall = 3.0                # wall / plate thickness
clear = 0.25              # fit clearance per side
screw_pilot_d = 1.7       # pilot hole for M2 self-tapping screws (servo tabs)
m3_clear_d = 3.4
m3_pilot_d = 2.6          # M3 screw self-tapping into plastic
cable_slot_w = 6
cable_slot_h = 8          # above the servo bottom
floor_gap = 1.0           # air under the pan servo
pivot_gap = 1.5           # camera arm to the pivot upright (use a washer)

# ---------- Derived (same formulas as pantilt.scad) ----------
tab_len = (tab_span - servo_l) / 2
upright_t = servo_h - tab_z - tab_t            # case top ends flush with the upright's inner face
cheek_x = cam_w / 2 + clear + wall             # camera arm outer faces at +/- cheek_x
horn_gap = horn_seat_z - tab_z - tab_t - upright_t
swing_r = max(math.hypot(cam_h / 2 + wall, cam_d / 2 + wall), horn_len / 2 + 3)
axis_z = swing_r + 2                           # tilt axis above the yoke plate's top
up_l_x = -cheek_x - horn_gap                   # left upright inner face (tilt servo side)
up_r_x = cheek_x + pivot_gap                   # right upright inner face (pivot side)
base_top = wall + floor_gap + tab_z            # pan servo tabs rest here

X, Y, Z = cq.Vector(1, 0, 0), cq.Vector(0, 1, 0), cq.Vector(0, 0, 1)


# =====================================================================
# Helpers
# =====================================================================
def box(x0, y0, z0, dx, dy, dz):
    return cq.Workplane().box(dx, dy, dz, centered=False).translate((x0, y0, z0))


def cyl(d, h, at, axis=Z):
    return cq.Workplane().add(cq.Solid.makeCylinder(d / 2, h, cq.Vector(*at), axis))


def circle_pts(cx, cy, r, n=48):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def hull2d(points):
    """Convex hull (monotone chain) of 2D points, counter-clockwise."""
    pts = sorted(set((round(x, 6), round(y, 6)) for x, y in points))

    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and (out[-1][0] - out[-2][0]) * (p[1] - out[-2][1]) - \
                    (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0]) <= 0:
                out.pop()
            out.append(p)
        return out
    lower, upper = half(pts), half(reversed(pts))
    return lower[:-1] + upper[:-1]


def prism(profile, plane, start, length):
    """Extrude a 2D profile on a standard plane ("XY", "YZ", "XZ") by `length` from offset `start`."""
    wp = cq.Workplane(plane).workplane(offset=start).polyline(hull2d(profile)).close()
    return wp.extrude(length)


def rounded_plate(x0, y0, dx, dy, h, r):
    return box(x0, y0, 0, dx, dy, h).edges("|Z").fillet(r)


def horn_outline(extra=0.0):
    """2D outline of the double horn around the shaft, arms along local x."""
    pts = circle_pts(0, 0, horn_hub_d / 2 + extra)
    for s in (-1, 1):
        pts += circle_pts(s * (horn_len - horn_tip_d) / 2, 0, horn_tip_d / 2 + extra)
    return pts


def horn_socket(through):
    """Horn recess + center screw access + fixing holes, cut into material at z > 0 (face at z = 0)."""
    cutter = prism(horn_outline(clear), "XY", -0.01, horn_t + 0.21)
    cutter = cutter.union(cyl(5.5, through + 0.02, (0, 0, -0.01)))
    for r in horn_hole_r:
        for s in (-1, 1):
            cutter = cutter.union(cyl(horn_screw_d, through + 0.02, (s * r, 0, -0.01)))
    return cutter


# =====================================================================
# Part 1: base (pan servo shaft on the Z axis)
# =====================================================================
def base():
    body_cx = servo_l / 2 - shaft_offset
    in_l, in_w = servo_l + 2 * clear, servo_w + 2 * clear
    box_l = in_l + 2 * (tab_len + 1.5)
    box_w = in_w + 2 * wall
    px, py = box_l + 22, box_w + 26
    part = rounded_plate(-px / 2, -py / 2, px, py, wall, 4)
    part = part.union(box(body_cx - box_l / 2, -box_w / 2, 0, box_l, box_w, base_top))
    part = part.cut(box(body_cx - in_l / 2, -in_w / 2, wall, in_l, in_w, base_top))
    for s in (-1, 1):
        part = part.cut(cyl(screw_pilot_d, 10.01, (body_cx + s * tab_hole_spacing / 2, 0, base_top - 10)))
        sx = body_cx + s * (in_l / 2 + tab_len)
        part = part.cut(box(sx - tab_len - 2, -cable_slot_w / 2, wall, 2 * tab_len + 4,
                            cable_slot_w, floor_gap + cable_slot_h))
    for x in (-1, 1):
        for y in (-1, 1):
            part = part.cut(cyl(m3_clear_d, wall + 0.02, (x * (px / 2 - 5), y * (py / 2 - 5), -0.01)))
    return part


# =====================================================================
# Part 2: yoke (plate underside at z = 0; tilt axis along X at y = 0)
# =====================================================================
def yoke():
    body_cy = -(servo_l / 2 - shaft_offset)    # tilt servo lies along Y, long end toward the back
    win_l, win_w = servo_l + 2 * clear, servo_w + 2 * clear
    y0, y1 = body_cy - tab_span / 2 - 3, body_cy + tab_span / 2 + 3
    up_h = wall + axis_z + win_w / 2 + 5
    x0, x1 = up_l_x - upright_t, up_r_x + wall + 1
    pz = wall + axis_z                         # tilt axis height in part coordinates

    part = rounded_plate(x0, y0, x1 - x0, y1 - y0, wall + 1, 3)
    part = part.union(box(x0, y0, 0, upright_t, y1 - y0, up_h))                  # left upright
    tower = [(-12, 0), (12, 0), (-12, wall + 1), (12, wall + 1)] + circle_pts(0, pz, 7)
    part = part.union(prism(tower, "YZ", up_r_x, wall + 1))                       # right upright
    for gy in (y0, y1 - wall):                                                   # gussets
        g = [(x0, 0), (x0 + upright_t + 10, 0), (x0 + upright_t + 10, wall + 1),
             (x0 + upright_t, up_h * 0.6), (x0, up_h * 0.6)]
        part = part.union(prism(g, "XZ", -gy, -wall))
    part = part.cut(horn_socket(wall + 1))                                        # pan horn socket
    part = part.cut(box(x0 - 0.01, body_cy - win_l / 2, pz - win_w / 2, upright_t + 0.02, win_l, win_w))
    for s in (-1, 1):
        part = part.cut(cyl(screw_pilot_d, upright_t + 0.02,
                            (x0 - 0.01, body_cy + s * tab_hole_spacing / 2, pz), X))
    part = part.cut(cyl(m3_clear_d, wall + 2, (up_r_x - 0.01, 0, pz), X))         # pivot hole
    return part


# =====================================================================
# Part 3: camera arm (tilt axis = X through the origin, camera looks +Y)
# =====================================================================
def camera_arm():
    fz = -(cam_h / 2) - wall                   # floor underside
    dy = cam_d / 2 + wall
    part = box(-cheek_x, -dy, fz, 2 * cheek_x, 2 * dy, wall)                      # floor
    for y in (-dy, dy - wall):                                                   # front/back lips
        part = part.union(box(-cheek_x, y, fz, 2 * cheek_x, wall, wall + 4))
    cheek = [(-dy, fz), (dy, fz), (-dy, fz + wall), (dy, fz + wall)] + circle_pts(0, 0, horn_len / 2 + 2)
    for xs in (-cheek_x, cheek_x - wall):                                        # cheeks
        part = part.union(prism(cheek, "YZ", xs, wall))
    part = part.union(cyl(9, pivot_gap - 0.5, (cheek_x - 0.01, 0, 0), X))         # pivot boss

    # tilt horn socket on the left cheek's outer face, arms along Y
    socket = horn_socket(wall).rotate((0, 0, 0), (0, 0, 1), 90).rotate((0, 0, 0), (0, 1, 0), 90)
    part = part.cut(socket.translate((-cheek_x, 0, 0)))
    part = part.cut(cyl(m3_pilot_d, wall + pivot_gap + 1, (cheek_x - wall - 0.01, 0, 0), X))
    for x in (-1, 1):                                                            # zip-tie slots
        for y in (-1, 1):
            part = part.cut(box(x * cam_w / 4 - 2, y * (cam_d / 2 - 3) - 1, fz - 0.01, 4, 2, wall + 0.02))
    part = part.cut(box(-cam_w / 2 - clear, -cam_d / 2, fz + wall, cam_w + 2 * clear, cam_d, cam_h + 50))
    return part


# Print orientation: flat side down, sitting on z = 0
PARTS = {
    "pantilt_base": base,
    "pantilt_yoke": yoke,
    "pantilt_camera_arm": lambda: camera_arm().translate((0, 0, cam_h / 2 + wall)),
}


def assembly(pan_angle=30, tilt_angle=35):
    """Parts in their working positions, for previews."""
    yoke_z = wall + floor_gap + horn_seat_z
    tilt = camera_arm().rotate((0, 0, 0), (1, 0, 0), tilt_angle).translate((0, 0, wall + axis_z))
    moving = yoke().union(tilt).rotate((0, 0, 0), (0, 0, 1), pan_angle).translate((0, 0, yoke_z))
    return {"base": base(), "moving": moving}


if __name__ == "__main__":
    out = Path(__file__).parent
    for name, build in PARTS.items():
        solid = build()
        cq.exporters.export(solid, str(out / f"{name}.step"))
        cq.exporters.export(solid, str(out / f"{name}.stl"), tolerance=0.02, angularTolerance=0.1)
        bb = solid.val().BoundingBox()
        print(f"{name}: {bb.xlen:.1f} x {bb.ylen:.1f} x {bb.zlen:.1f} mm, "
              f"volume {solid.val().Volume() / 1000:.1f} cm3, valid={solid.val().isValid()}")
