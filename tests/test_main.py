"""Simulated run of pico/main.py on a laptop.

main.py is an endless loop built on MicroPython-only pieces (time.ticks_ms,
select.poll on stdin). Here we swap those for fakes, script what the "brain"
types and when, run the loop for a fixed number of ticks, and check what
the Pico printed back.
"""
import contextlib
import io
import os
import runpy
import sys
import tempfile
import types
import unittest
from unittest import mock

import fake_machine

MAIN_PY = os.path.join(fake_machine.PICO_DIR, "main.py")


class StopLoop(Exception):
    """Raised by the fake clock to break out of main.py's `while True`."""


class FakeSerial:
    """Stands in for sys.stdin plus select.poll: text arrives on a schedule."""

    def __init__(self, schedule):
        self.schedule = schedule    # list of (tick, text): text arrives at that tick
        self.tick = 0
        self.buffer = ""

    def arrive(self):
        while self.schedule and self.schedule[0][0] <= self.tick:
            self.buffer += self.schedule.pop(0)[1]

    # --- the bits of sys.stdin main.py uses
    def read(self, n):
        char, self.buffer = self.buffer[:n], self.buffer[n:]
        return char

    # --- the bits of select.poll() main.py uses
    def register(self, stream, flags):
        pass

    def poll(self, timeout):
        self.arrive()
        return [(self, 1)] if self.buffer else []


def run_main(schedule, ticks):
    """Run main.py for `ticks` loop iterations; return everything it printed."""
    serial = FakeSerial(schedule)
    clock = {"ms": 0}

    def sleep_ms(ms):
        clock["ms"] += ms
        serial.tick += 1
        if serial.tick >= ticks:
            raise StopLoop

    fake_time = types.SimpleNamespace(
        ticks_ms=lambda: clock["ms"],
        ticks_diff=lambda a, b: a - b,
        sleep_ms=sleep_ms,
    )
    fake_select = types.SimpleNamespace(poll=lambda: serial, POLLIN=1)

    out = io.StringIO()
    old_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)                           # config.json lands in a scratch folder
        try:
            with mock.patch.dict(sys.modules, {"time": fake_time, "select": fake_select}), \
                    mock.patch.object(sys, "stdin", serial), \
                    contextlib.redirect_stdout(out):
                try:
                    runpy.run_path(MAIN_PY, run_name="__main__")
                except StopLoop:
                    pass
        finally:
            os.chdir(old_cwd)
    return out.getvalue().splitlines()


class MainLoopTest(unittest.TestCase):
    def test_boot_commands_and_smooth_motion(self):
        printed = run_main(
            schedule=[
                (0, "?\r\n"),                   # Thonny-style line ending
                (1, "P120 T30\n"),              # brain-style line ending
                (2, "bogus\n"),
                (3, "SPE"), (4, "ED 60\n"),     # a line split across two reads
                (60, "?\n"),                    # ~1.2 s later: move has finished
            ],
            ticks=70,
        )
        self.assertEqual(printed, [
            "READY skynode-pico",
            "POS P90.0 T45.0",
            "ERR unknown command BOGUS",
            "OK",
            "POS P120.0 T30.0",
        ])

    def test_overlong_line_is_truncated_not_crashing(self):
        printed = run_main(schedule=[(0, "P" + "9" * 500 + "\n"), (1, "?\n")], ticks=3)
        self.assertEqual(printed[0], "READY skynode-pico")
        self.assertEqual(len(printed), 2)       # no reply to the (silent) move, then POS
        self.assertTrue(printed[1].startswith("POS"))


if __name__ == "__main__":
    unittest.main()
