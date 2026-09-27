"""Tests for pico/servo.py. Run from the repo root: python -m unittest discover tests"""
import unittest

import fake_machine  # noqa: F401  (must come before importing pico code)
from servo import Servo


def pulse_us(servo):
    """The pulse width (us) the fake hardware was last told to send."""
    return servo.pwm.duty / 1000


class ServoTest(unittest.TestCase):
    def test_starts_at_50hz_and_start_angle(self):
        s = Servo(0, min_us=500, max_us=2400, start_deg=90)
        self.assertEqual(s.pwm.frequency, 50)
        self.assertEqual(pulse_us(s), 1450)      # halfway between 500 and 2400

    def test_angle_maps_linearly_onto_calibration(self):
        s = Servo(0, min_us=600, max_us=2300)
        self.assertEqual(s.angle_to_us(0), 600)
        self.assertEqual(s.angle_to_us(180), 2300)
        self.assertEqual(s.angle_to_us(90), 1450)

    def test_targets_are_clamped_to_limits(self):
        s = Servo(0, min_deg=10, max_deg=170)
        s.set_target(200)
        self.assertEqual(s.target, 170)
        s.set_target(-5)
        self.assertEqual(s.target, 10)

    def test_update_moves_at_most_speed_times_dt(self):
        s = Servo(0, start_deg=90)
        s.set_target(180)
        s.update(0.1, speed=100)                 # 100 deg/s for 0.1 s = 10 deg
        self.assertAlmostEqual(s.angle, 100)
        s.set_target(0)
        s.update(0.1, speed=100)
        self.assertAlmostEqual(s.angle, 90)

    def test_update_lands_exactly_on_target_without_overshoot(self):
        s = Servo(0, start_deg=90)
        s.set_target(93)
        s.update(0.1, speed=100)                 # step would be 10, only 3 needed
        self.assertEqual(s.angle, 93)
        self.assertAlmostEqual(pulse_us(s), s.angle_to_us(93), places=2)   # ns rounding

    def test_reaches_far_target_after_enough_ticks(self):
        s = Servo(0, start_deg=0)
        s.set_target(180)
        for _ in range(100):                     # 100 ticks x 20 ms = 2 s at 120 deg/s
            s.update(0.02, speed=120)
        self.assertEqual(s.angle, 180)

    def test_relax_stops_pulses_and_next_target_wakes_it(self):
        s = Servo(0, start_deg=45)
        s.relax()
        self.assertEqual(s.pwm.duty, 0)
        s.update(0.1, speed=100)                 # relaxed servo ignores updates
        self.assertEqual(s.pwm.duty, 0)
        s.set_target(90)
        self.assertTrue(s.active)
        self.assertEqual(pulse_us(s), s.angle_to_us(45))   # resumes where it was

    def test_calibrate_applies_immediately(self):
        s = Servo(0, start_deg=0)
        s.calibrate(700, 2300)
        self.assertEqual(pulse_us(s), 700)

    def test_bad_calibration_is_rejected(self):
        s = Servo(0)
        for lo, hi in [(2400, 500), (100, 2400), (500, 3000), (1500, 1500)]:
            with self.assertRaises(ValueError):
                s.calibrate(lo, hi)
        self.assertEqual((s.min_us, s.max_us), (500, 2400))   # unchanged

    def test_new_limits_pull_target_back_in_range(self):
        s = Servo(0, start_deg=170)
        s.set_limits(0, 90)
        self.assertEqual(s.target, 90)
        self.assertEqual(s.angle, 170)           # not a jump: update() eases it in
        s.update(1.0, speed=500)
        self.assertEqual(s.angle, 90)

    def test_bad_limits_are_rejected(self):
        s = Servo(0)
        for lo, hi in [(90, 10), (-1, 90), (0, 181), (45, 45)]:
            with self.assertRaises(ValueError):
                s.set_limits(lo, hi)

    def test_raw_pulse_is_bounded(self):
        s = Servo(0)
        s.raw_us(1500)
        self.assertEqual(pulse_us(s), 1500)
        with self.assertRaises(ValueError):
            s.raw_us(3000)


if __name__ == "__main__":
    unittest.main()
