// pantilt.scad — parametric two-axis pan-tilt mount for SG90 servos + a small USB webcam.
//
// Three printed parts (a two-axis mount needs three links: fixed, panning, tilting):
//   base        holds the pan servo, shaft up; screws down to a board
//   yoke        sits on the pan servo's horn; holds the tilt servo and the pivot
//   camera_arm  cradle for the webcam; hangs on the tilt horn and an M3 pivot
//
// Export one part from the command line:
//   openscad -D 'part="base"'       -o pantilt_base.stl       pantilt.scad
//   openscad -D 'part="yoke"'       -o pantilt_yoke.stl       pantilt.scad
//   openscad -D 'part="camera_arm"' -o pantilt_camera_arm.stl pantilt.scad
// part="assembly" (the default) shows everything put together, for previews.
//
// Print: PLA or PETG, 0.2 mm layers, 3 walls, 25-40 % infill, no supports.
// Each part is exported lying on its flat side. The yoke's servo window is
// a ~23 mm bridge, which most printers handle without supports.
//
// All sizes in mm. MEASURE YOUR SERVO: SG90 clones vary by a few tenths.

part = "assembly";          // "assembly" | "base" | "yoke" | "camera_arm"
pan_angle  = 30;            // assembly preview only
tilt_angle = 35;            // assembly preview only

// ---------- SG90 servo ----------
servo_l = 22.5;             // body length (along the mounting tabs)
servo_w = 12.0;             // body width
servo_h = 22.7;             // body height, bottom to top of case (without the gear boss)
tab_span = 32.3;            // length across both mounting tabs
tab_t = 2.5;                // tab thickness
tab_z = 15.9;               // servo bottom to the UNDERSIDE of the tabs
tab_hole_spacing = 27.8;    // center-to-center of the two tab screw holes
shaft_offset = 5.9;         // output shaft axis, measured from the near end of the body
horn_seat_z = 30.0;         // servo bottom to the underside of the fitted horn's arm

// ---------- Standard SG90 double-arm horn ----------
horn_len = 32.0;            // tip to tip
horn_hub_d = 7.4;           // arm width at the hub
horn_tip_d = 4.2;           // arm width at the tips
horn_t = 1.6;               // arm thickness
horn_hole_r = [8, 12];      // radii of screw holes that fix the horn to the part
horn_screw_d = 2.2;         // clearance for M2 self-tapping screws into the horn

// ---------- Webcam ----------
cam_w = 40;                 // across (side to side)
cam_h = 30;                 // tall
cam_d = 30;                 // deep (front to back, lens pointing forward)

// ---------- General ----------
wall = 3.0;                 // wall / plate thickness
clear = 0.25;               // fit clearance per side
screw_pilot_d = 1.7;        // pilot hole for M2 self-tapping screws (servo tabs)
m3_clear_d = 3.4;
m3_pilot_d = 2.6;           // M3 screw self-tapping into plastic
cable_slot_w = 6;
cable_slot_h = 8;           // above the servo bottom
floor_gap = 1.0;            // air under the pan servo
pivot_gap = 1.5;            // camera arm to the pivot upright (use a washer)

$fn = 48;
eps = 0.01;

// ---------- Derived ----------
tab_len = (tab_span - servo_l) / 2;
upright_t = servo_h - tab_z - tab_t;           // case top ends flush with the upright's inner face
cheek_x = cam_w / 2 + clear + wall;            // camera arm outer faces at +/- cheek_x
horn_gap = horn_seat_z - tab_z - tab_t - upright_t;   // tilt upright inner face to camera arm
swing_r = max(norm([cam_h / 2 + wall, cam_d / 2 + wall]), horn_len / 2 + 3);
axis_z = swing_r + 2;                          // tilt axis above the yoke plate's top
up_l_x = -cheek_x - horn_gap;                  // left upright inner face (tilt servo side)
up_r_x = cheek_x + pivot_gap;                  // right upright inner face (pivot side)
base_top = wall + floor_gap + tab_z;           // tabs rest here
yoke_z = wall + floor_gap + horn_seat_z;       // yoke plate underside, in the assembly

// =====================================================================
// Shared shapes
// =====================================================================

// 2D outline of the double horn, centered on the shaft, arms along X.
module horn_2d(extra = 0) {
    hull() {
        circle(d = horn_hub_d + 2 * extra);
        for (s = [-1, 1]) translate([s * (horn_len - horn_tip_d) / 2, 0])
            circle(d = horn_tip_d + 2 * extra);
    }
}

// Pocket for the horn on a face (face at z=0, material at z>0): recess,
// screw access hole in the middle, holes for the fixing screws.
module horn_socket(depth_through) {
    translate([0, 0, -eps]) linear_extrude(horn_t + 0.2 + eps) horn_2d(clear);
    translate([0, 0, -eps]) cylinder(d = 5.5, h = depth_through + 2 * eps);
    for (r = horn_hole_r, s = [-1, 1])
        translate([s * r, 0, -eps]) cylinder(d = horn_screw_d, h = depth_through + 2 * eps);
}

module rounded_box(size, r = 3) {
    hull() for (x = [r, size[0] - r], y = [r, size[1] - r])
        translate([x, y, 0]) cylinder(r = r, h = size[2]);
}

// Rough SG90 stand-in for the assembly view (shaft at the origin, pointing +Z).
module sg90_model() {
    color("RoyalBlue", 0.85) {
        translate([-shaft_offset, -servo_w / 2, 0]) cube([servo_l, servo_w, servo_h]);
        translate([-shaft_offset - tab_len, -servo_w / 2, tab_z]) cube([tab_span, servo_w, tab_t]);
        cylinder(d = servo_w, h = servo_h + 4);
    }
    color("White") translate([0, 0, horn_seat_z]) linear_extrude(horn_t) horn_2d();
}

// =====================================================================
// Part 1: base (pan servo, shaft on the Z axis)
// =====================================================================
module base() {
    body_cx = servo_l / 2 - shaft_offset;      // servo body center, relative to the shaft
    in_l = servo_l + 2 * clear;
    in_w = servo_w + 2 * clear;
    box_l = in_l + 2 * (tab_len + 1.5);
    box_w = in_w + 2 * wall;
    plate = [box_l + 22, box_w + 26, wall];
    difference() {
        union() {
            translate([-plate[0] / 2, -plate[1] / 2, 0]) rounded_box(plate, 4);
            translate([body_cx - box_l / 2, -box_w / 2, 0]) cube([box_l, box_w, base_top]);
        }
        // servo pocket
        translate([body_cx - in_l / 2, -in_w / 2, wall]) cube([in_l, in_w, base_top]);
        // tab screw pilot holes
        for (s = [-1, 1]) translate([body_cx + s * tab_hole_spacing / 2, 0, base_top - 10])
            cylinder(d = screw_pilot_d, h = 10 + eps);
        // cable slots, both ends (the lead exits low on one end of the case)
        for (s = [-1, 1]) translate([body_cx + s * (in_l / 2 + tab_len), 0, wall + (floor_gap + cable_slot_h) / 2])
            cube([2 * tab_len + 4, cable_slot_w, floor_gap + cable_slot_h], center = true);
        // M3 mounting holes in the corners
        for (x = [-1, 1], y = [-1, 1]) translate([x * (plate[0] / 2 - 5), y * (plate[1] / 2 - 5), -eps])
            cylinder(d = m3_clear_d, h = wall + 2 * eps);
    }
}

// =====================================================================
// Part 2: yoke (pan axis = Z, plate underside at z=0; tilt axis along X at y=0)
// =====================================================================
module yoke() {
    body_cy = -(servo_l / 2 - shaft_offset);   // tilt servo lies along Y, long end toward the back
    win_l = servo_l + 2 * clear;
    win_w = servo_w + 2 * clear;
    up_l_y0 = body_cy - tab_span / 2 - 3;
    up_l_y1 = body_cy + tab_span / 2 + 3;
    up_h = wall + axis_z + win_w / 2 + 5;
    x0 = up_l_x - upright_t;
    x1 = up_r_x + wall + 1;
    difference() {
        union() {
            // plate
            translate([x0, up_l_y0, 0]) rounded_box([x1 - x0, up_l_y1 - up_l_y0, wall + 1], 3);
            // left upright: holds the tilt servo
            translate([x0, up_l_y0, 0]) cube([upright_t, up_l_y1 - up_l_y0, up_h]);
            // right upright: pivot tower
            hull() {
                translate([up_r_x, -12, 0]) cube([wall + 1, 24, wall + 1]);
                translate([up_r_x, 0, wall + axis_z]) rotate([0, 90, 0]) cylinder(r = 7, h = wall + 1);
            }
            // gussets
            for (y = [up_l_y0, up_l_y1 - wall]) hull() {
                translate([x0, y, 0]) cube([upright_t, wall, up_h * 0.6]);
                translate([x0, y, 0]) cube([upright_t + 10, wall, wall + 1]);
            }
        }
        // pan horn socket in the underside
        horn_socket(wall + 1);
        // tilt servo window + tab screw holes
        translate([x0 - eps, body_cy - win_l / 2, wall + axis_z - win_w / 2])
            cube([upright_t + 2 * eps, win_l, win_w]);
        for (s = [-1, 1]) translate([x0 - eps, body_cy + s * tab_hole_spacing / 2, wall + axis_z])
            rotate([0, 90, 0]) cylinder(d = screw_pilot_d, h = upright_t + 2 * eps);
        // pivot hole
        translate([up_r_x - eps, 0, wall + axis_z]) rotate([0, 90, 0]) cylinder(d = m3_clear_d, h = wall + 2);
    }
}

// =====================================================================
// Part 3: camera arm (tilt axis = X through the origin, camera looks +Y)
// =====================================================================
module camera_arm() {
    fz = -(cam_h / 2) - wall;                  // floor underside
    dy = cam_d / 2 + wall;
    difference() {
        union() {
            // floor
            translate([-cheek_x, -dy, fz]) cube([2 * cheek_x, 2 * dy, wall]);
            // front and back lips
            for (y = [-dy, dy - wall]) translate([-cheek_x, y, fz]) cube([2 * cheek_x, wall, wall + 4]);
            // cheeks: side walls plus a disc around the axis for the horn / pivot
            for (s = [-1, 1]) translate([s > 0 ? cheek_x - wall : -cheek_x, 0, 0]) hull() {
                translate([0, -dy, fz]) cube([wall, 2 * dy, wall]);
                rotate([0, 90, 0]) cylinder(r = horn_len / 2 + 2, h = wall);
            }
            // pivot boss (bearing face against the right upright)
            translate([cheek_x - eps, 0, 0]) rotate([0, 90, 0]) cylinder(d = 9, h = pivot_gap - 0.5);
        }
        // tilt horn socket on the left cheek's outer face, arms along Y
        translate([-cheek_x, 0, 0]) rotate([0, 90, 0]) rotate([0, 0, 90]) horn_socket(wall);
        // M3 pivot pilot hole, right side
        translate([cheek_x - wall - eps, 0, 0]) rotate([0, 90, 0]) cylinder(d = m3_pilot_d, h = wall + pivot_gap + 1);
        // zip-tie slots (two ties wrap over the camera, under the floor)
        for (x = [-1, 1], y = [-1, 1]) translate([x * cam_w / 4, y * (cam_d / 2 - 3), fz - eps])
            translate([-2, -1, 0]) cube([4, 2, wall + 2 * eps]);
        // keep the inside clear for the camera
        translate([-cam_w / 2 - clear, -cam_d / 2, fz + wall]) cube([cam_w + 2 * clear, cam_d, cam_h + 50]);
    }
}

// =====================================================================
// Output
// =====================================================================
module assembly() {
    color("DimGray") base();
    translate([0, 0, wall + floor_gap]) sg90_model();
    translate([0, 0, yoke_z]) rotate([0, 0, pan_angle]) {
        color("SteelBlue") yoke();
        // tilt servo, shaft pointing +X toward the camera arm, long end toward the back
        translate([-cheek_x - horn_seat_z, 0, wall + axis_z]) rotate([0, 90, 0]) rotate([0, 0, -90]) sg90_model();
        translate([0, 0, wall + axis_z]) rotate([tilt_angle, 0, 0]) {
            color("DarkOrange") camera_arm();
            color("#222") translate([-cam_w / 2, -cam_d / 2, -cam_h / 2]) cube([cam_w, cam_d, cam_h]);
            color("#555") translate([0, cam_d / 2, 0]) rotate([-90, 0, 0]) cylinder(d = 12, h = 4);
        }
    }
}

if (part == "base") base();
else if (part == "yoke") yoke();
else if (part == "camera_arm") translate([0, 0, cam_h / 2 + wall]) camera_arm();
else assembly();
