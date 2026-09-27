"""Tests for pico/protocol.py. Run from the repo root: python -m unittest discover tests"""
import unittest

import fake_machine  # noqa: F401  (puts pico/ on sys.path)
from protocol import parse


class ParseMoveTest(unittest.TestCase):
    def test_both_axes(self):
        self.assertEqual(parse("P90 T45"), ("move", {"pan": 90.0, "tilt": 45.0}))

    def test_either_order_one_axis_decimals_and_case(self):
        self.assertEqual(parse("t45.5 p90"), ("move", {"pan": 90.0, "tilt": 45.5}))
        self.assertEqual(parse("P-3"), ("move", {"pan": -3.0}))
        self.assertEqual(parse("  T12\r\n"), ("move", {"tilt": 12.0}))

    def test_blank_line_is_ignored(self):
        self.assertIsNone(parse(""))
        self.assertIsNone(parse("   \r\n"))

    def test_malformed_moves_are_rejected(self):
        for line in ["X90", "P", "Pabc", "P90 Q1", "Pnan", "Tinf", "HELLO"]:
            with self.assertRaises(ValueError, msg=line):
                parse(line)


class ParseOtherCommandsTest(unittest.TestCase):
    def test_simple_commands(self):
        self.assertEqual(parse("?"), ("status", ()))
        self.assertEqual(parse("status"), ("status", ()))
        self.assertEqual(parse("H"), ("home", ()))
        self.assertEqual(parse("home"), ("home", ()))
        self.assertEqual(parse("CFG"), ("config", ()))
        self.assertEqual(parse("OFF"), ("off", ()))
        self.assertEqual(parse("save"), ("save", ()))

    def test_simple_commands_take_no_arguments(self):
        with self.assertRaises(ValueError):
            parse("HOME 5")

    def test_speed(self):
        self.assertEqual(parse("SPEED 120"), ("speed", (120.0,)))
        with self.assertRaises(ValueError):
            parse("SPEED")

    def test_cal_lim_raw(self):
        self.assertEqual(parse("CAL P 500 2400"), ("cal", ("pan", 500.0, 2400.0)))
        self.assertEqual(parse("lim tilt 0 90"), ("lim", ("tilt", 0.0, 90.0)))
        self.assertEqual(parse("RAW T 1500"), ("raw", ("tilt", 1500.0)))

    def test_bad_arguments_give_usage(self):
        with self.assertRaises(ValueError) as ctx:
            parse("CAL P 500")
        self.assertIn("usage", str(ctx.exception))
        with self.assertRaises(ValueError):
            parse("LIM X 0 90")          # bad axis
        with self.assertRaises(ValueError):
            parse("RAW P lots")          # bad number


if __name__ == "__main__":
    unittest.main()
