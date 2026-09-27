"""Tests for pico/pantilt.py. Run from the repo root: python -m unittest discover tests"""
import json
import os
import tempfile
import unittest

import fake_machine  # noqa: F401  (must come before importing pico code)
from pantilt import DEFAULTS, PanTilt, default_config, load_config


class PanTiltTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "config.json")
        self.rig = PanTilt(default_config(), config_path=self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_starts_at_home(self):
        self.assertEqual(self.rig.handle("?"), "POS P90.0 T45.0")

    def test_moves_are_silent_and_smooth(self):
        self.assertIsNone(self.rig.handle("P120 T30"))
        self.rig.update(0.1)                      # 120 deg/s * 0.1 s = 12 deg max
        self.assertEqual(self.rig.handle("?"), "POS P102.0 T33.0")
        self.rig.update(1.0)
        self.assertEqual(self.rig.handle("?"), "POS P120.0 T30.0")

    def test_home(self):
        self.rig.handle("P0 T0")
        self.rig.update(5)
        self.assertIsNone(self.rig.handle("HOME"))
        self.rig.update(5)
        self.assertEqual(self.rig.handle("?"), "POS P90.0 T45.0")

    def test_speed(self):
        self.assertEqual(self.rig.handle("SPEED 60"), "OK")
        self.assertEqual(self.rig.speed, 60)
        self.assertTrue(self.rig.handle("SPEED 0").startswith("ERR"))
        self.assertTrue(self.rig.handle("SPEED 9000").startswith("ERR"))
        self.assertEqual(self.rig.speed, 60)

    def test_calibration_and_limits(self):
        self.assertEqual(self.rig.handle("CAL P 600 2300"), "OK")
        self.assertEqual(self.rig.servos["pan"].min_us, 600)
        self.assertTrue(self.rig.handle("CAL P 2300 600").startswith("ERR"))
        self.assertEqual(self.rig.handle("LIM T 0 90"), "OK")
        self.rig.handle("T150")
        self.assertEqual(self.rig.servos["tilt"].target, 90)

    def test_raw_and_off(self):
        self.assertEqual(self.rig.handle("RAW P 1500"), "OK")
        self.assertEqual(self.rig.servos["pan"].pwm.duty, 1_500_000)
        self.assertEqual(self.rig.handle("OFF"), "OK")
        self.assertEqual(self.rig.servos["pan"].pwm.duty, 0)
        self.assertEqual(self.rig.servos["tilt"].pwm.duty, 0)

    def test_errors_and_blank_lines(self):
        self.assertEqual(self.rig.handle("bogus"), "ERR unknown command BOGUS")
        self.assertIsNone(self.rig.handle(""))

    def test_cfg_reports_json(self):
        reply = self.rig.handle("CFG")
        self.assertTrue(reply.startswith("CFG "))
        self.assertEqual(json.loads(reply[4:]), DEFAULTS)

    def test_save_then_load_round_trip(self):
        for line in ["CAL P 600 2300", "LIM T 5 95", "SPEED 90"]:
            self.assertEqual(self.rig.handle(line), "OK")
        self.assertEqual(self.rig.handle("SAVE"), "OK saved")

        reloaded = PanTilt(load_config(self.path), config_path=self.path)
        self.assertEqual(reloaded.settings(), self.rig.settings())
        self.assertEqual(reloaded.servos["pan"].max_us, 2300)
        self.assertEqual(reloaded.servos["tilt"].max_deg, 95)
        self.assertEqual(reloaded.speed, 90)


class LoadConfigTest(unittest.TestCase):
    def test_missing_or_corrupt_file_gives_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            self.assertEqual(load_config(path), DEFAULTS)
            with open(path, "w") as f:
                f.write("{not json")
            self.assertEqual(load_config(path), DEFAULTS)

    def test_partial_file_keeps_other_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            with open(path, "w") as f:
                json.dump({"tilt": {"max_deg": 90}}, f)
            config = load_config(path)
            self.assertEqual(config["tilt"]["max_deg"], 90)
            self.assertEqual(config["tilt"]["pin"], 1)
            self.assertEqual(config["pan"], DEFAULTS["pan"])

    def test_default_config_is_a_copy(self):
        config = default_config()
        config["pan"]["min_us"] = 1
        self.assertEqual(DEFAULTS["pan"]["min_us"], 500)


if __name__ == "__main__":
    unittest.main()
