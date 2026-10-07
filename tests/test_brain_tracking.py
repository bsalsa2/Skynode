"""Tests for brain/tracker.py and brain/controller.py (no extra packages needed)."""
import unittest
from types import SimpleNamespace

from brain.controller import PanTiltController
from brain.tracker import Tracker

WIDTH, HEIGHT = 1000, 600


def det(name, confidence, x, y):
    """A stand-in detection: the tracker only needs class_name, confidence and center."""
    return SimpleNamespace(class_name=name, confidence=confidence, center=(x, y))


class TrackerTest(unittest.TestCase):
    def setUp(self):
        self.tracker = Tracker(["airplane", "bird"], max_missed_frames=2, max_jump=0.25)

    def test_ignores_other_classes_and_picks_most_confident(self):
        person = det("person", 0.99, 100, 100)
        bird = det("bird", 0.5, 200, 200)
        plane = det("airplane", 0.8, 800, 300)
        self.assertIs(self.tracker.update([person, bird, plane], WIDTH), plane)
        self.assertTrue(self.tracker.locked)

    def test_stays_on_nearest_not_most_confident(self):
        self.tracker.update([det("airplane", 0.6, 500, 300)], WIDTH)
        near = det("airplane", 0.4, 520, 310)
        far_but_confident = det("airplane", 0.95, 100, 100)
        self.assertIs(self.tracker.update([far_but_confident, near], WIDTH), near)

    def test_big_jump_is_not_the_same_target(self):
        self.tracker.update([det("airplane", 0.9, 100, 300)], WIDTH)
        self.assertIsNone(self.tracker.update([det("airplane", 0.9, 900, 300)], WIDTH))
        self.assertTrue(self.tracker.locked)            # still waiting for the original

    def test_lock_drops_after_max_missed_frames(self):
        self.tracker.update([det("bird", 0.9, 100, 300)], WIDTH)
        for _ in range(2):
            self.assertIsNone(self.tracker.update([], WIDTH))
            self.assertTrue(self.tracker.locked)
        self.tracker.update([], WIDTH)                  # third miss: over the limit
        self.assertFalse(self.tracker.locked)
        new = det("airplane", 0.7, 900, 300)
        self.assertIs(self.tracker.update([new], WIDTH), new)

    def test_short_gap_keeps_lock(self):
        first = det("bird", 0.9, 100, 300)
        self.tracker.update([first], WIDTH)
        self.tracker.update([], WIDTH)
        back = det("bird", 0.8, 110, 300)
        self.assertIs(self.tracker.update([back], WIDTH), back)
        self.assertEqual(self.tracker.missed, 0)


class ControllerTest(unittest.TestCase):
    def make(self, **kwargs):
        settings = dict(hfov_deg=90.0, gain=0.5, deadband_deg=0.5, max_step_deg=10.0,
                        pan_sign=1, tilt_sign=1, home=(90.0, 45.0))
        settings.update(kwargs)
        return PanTiltController(**settings)

    def test_offset_uses_pinhole_geometry(self):
        c = self.make(hfov_deg=90.0)
        right, up = c.offset_deg((WIDTH, HEIGHT / 2), (WIDTH, HEIGHT))   # right edge
        self.assertAlmostEqual(right, 45.0)            # half of the 90 deg field of view
        self.assertAlmostEqual(up, 0.0)
        right, up = c.offset_deg((WIDTH / 2, 0), (WIDTH, HEIGHT))        # top edge
        self.assertAlmostEqual(up, 30.96, places=2)    # atan(300 / 500) in degrees
        self.assertAlmostEqual(right, 0.0)

    def test_moves_gain_share_toward_target(self):
        c = self.make(hfov_deg=90.0, gain=0.5)
        # Target 45 deg right and ~31 deg up; max_step caps pan at 10, tilt 0.5*31 = 15.5 -> 10
        pan, tilt = c.update((WIDTH, 0), (WIDTH, HEIGHT))
        self.assertEqual((pan, tilt), (100.0, 55.0))

    def test_small_offsets_stay_uncapped(self):
        c = self.make(hfov_deg=90.0, gain=0.5)
        focal = (WIDTH / 2) / 1.0                      # tan(45 deg) = 1
        x = WIDTH / 2 + focal * 0.0874887               # tan(5 deg): 5 deg right
        pan, _ = c.update((x, HEIGHT / 2), (WIDTH, HEIGHT))
        self.assertAlmostEqual(pan, 92.5, places=3)

    def test_signs_flip_direction(self):
        c = self.make(pan_sign=-1, tilt_sign=-1)
        pan, tilt = c.update((WIDTH, 0), (WIDTH, HEIGHT))
        self.assertEqual((pan, tilt), (80.0, 35.0))

    def test_deadband_ignores_tiny_errors(self):
        c = self.make()
        pan, tilt = c.update((WIDTH / 2 + 1, HEIGHT / 2 - 1), (WIDTH, HEIGHT))
        self.assertEqual((pan, tilt), (90.0, 45.0))

    def test_simulated_aim_is_home_plus_the_offset_and_does_not_add_up(self):
        c = self.make(pan_sign=-1, tilt_sign=1)
        right, up = c.offset_deg((960, 100), (1280, 720))      # right of centre and above it
        self.assertGreater(right, 0)
        self.assertGreater(up, 0)
        first = c.simulate_aim((960, 100), (1280, 720))
        for _ in range(50):                                     # the same frame, again and again
            again = c.simulate_aim((960, 100), (1280, 720))
        self.assertEqual(first, again)                          # no wind-up
        self.assertAlmostEqual(again[0], 90.0 - right)          # pan_sign = -1: right turns it down
        self.assertAlmostEqual(again[1], 45.0 + up)
        self.assertEqual(c.simulate_aim((640, 360), (1280, 720)), (90.0, 45.0))   # dead centre = home

    def test_simulated_aim_stays_inside_the_limits(self):
        c = self.make()
        c.pan_limits, c.tilt_limits = (80.0, 100.0), (40.0, 50.0)
        pan, tilt = c.simulate_aim((1279, 0), (1280, 720))
        self.assertTrue(80.0 <= pan <= 100.0 and 40.0 <= tilt <= 50.0)

    def test_limits_and_home_come_from_the_pico(self):
        c = self.make()
        c.apply_pico_settings({
            "speed": 120,
            "pan": {"min_deg": 20, "max_deg": 160, "home": 90},
            "tilt": {"min_deg": 0, "max_deg": 50, "home": 30},
        })
        for _ in range(20):                            # keep pushing up and right
            c.update((WIDTH, 0), (WIDTH, HEIGHT))
        self.assertEqual((c.pan, c.tilt), (160, 50))
        self.assertEqual(c.go_home(), (90, 30))

    def test_command_format(self):
        c = self.make(home=(92.54, 47.0))
        self.assertEqual(c.command(), "P92.5 T47.0")


if __name__ == "__main__":
    unittest.main()
