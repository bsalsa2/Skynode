"""Simulated runs of pico/main.py on a laptop.

main.py is an endless loop built on MicroPython-only pieces (time.ticks_ms,
select.poll on stdin, network.WLAN, lwIP sockets). Sim swaps those for fakes,
scripts what arrives over USB and Wi-Fi and when, runs the loop for a fixed
number of ticks, and records everything the Pico printed or sent back.
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
BRAIN = ("192.168.1.10", 50000)     # the address Wi-Fi packets "come from"


class StopLoop(Exception):
    """Raised by the fake clock to break out of main.py's `while True`."""


class Sim:
    """A fake Pico world: clock, USB serial, Wi-Fi radio and UDP socket.

    usb     -- list of (tick, text): text arrives on USB serial at that tick
    packets -- list of (tick, text): a UDP datagram from BRAIN arrives at that tick
    wifi    -- False: no wifi_secrets.py on the Pico. Otherwise the tick at
               which the network comes up (None = never).
    """

    def __init__(self, usb=(), packets=(), wifi=False, wifi_down_at=None):
        self.tick = 0
        self.ms = 0
        self.usb_schedule = list(usb)
        self.usb_buffer = ""
        self.packets = list(packets)
        self.wifi_up_at = wifi
        self.wifi_down_at = wifi_down_at
        self.sent = []              # (text, address) replies sent over Wi-Fi
        self.connect_calls = 0
        self.has_wifi = wifi is not False

    # ---- fake time --------------------------------------------------------
    def ticks_ms(self):
        return self.ms

    def sleep_ms(self, ms):
        self.ms += ms
        self.tick += 1
        if self.tick >= self.stop_at:
            raise StopLoop

    # ---- fake USB serial (sys.stdin + select.poll) ------------------------
    def read(self, n):
        char, self.usb_buffer = self.usb_buffer[:n], self.usb_buffer[n:]
        return char

    def register(self, stream, flags):
        pass

    def poll(self, timeout):
        while self.usb_schedule and self.usb_schedule[0][0] <= self.tick:
            self.usb_buffer += self.usb_schedule.pop(0)[1]
        return [(self, 1)] if self.usb_buffer else []

    # ---- fake network.WLAN ------------------------------------------------
    def wifi_is_up(self):
        up = self.wifi_up_at is not None and self.tick >= self.wifi_up_at
        down = self.wifi_down_at is not None and self.tick >= self.wifi_down_at
        return up and not down

    def make_wlan(self, interface):
        sim = self
        return types.SimpleNamespace(
            active=lambda on: None,
            config=lambda **settings: None,
            connect=lambda ssid, password: setattr(sim, "connect_calls", sim.connect_calls + 1),
            isconnected=sim.wifi_is_up,
            status=lambda: 3 if sim.wifi_is_up() else -2,      # -2 = network not found
            ifconfig=lambda: ("192.168.1.50", "255.255.255.0", "192.168.1.1", "192.168.1.1"),
        )

    # ---- fake UDP socket --------------------------------------------------
    def make_socket(self, family, kind):
        sim = self

        def recvfrom(size):
            if sim.packets and sim.packets[0][0] <= sim.tick:
                return sim.packets.pop(0)[1].encode(), BRAIN
            raise OSError(11, "EAGAIN")     # what a non-blocking socket says when empty

        return types.SimpleNamespace(
            bind=lambda address: None,
            setblocking=lambda flag: None,
            recvfrom=recvfrom,
            sendto=lambda data, address: sim.sent.append((data.decode(), address)),
        )

    # ---- run main.py ------------------------------------------------------
    def run(self, ticks):
        """Run main.py for `ticks` loop iterations; return the lines it printed."""
        self.stop_at = ticks
        modules = {
            "time": types.SimpleNamespace(ticks_ms=self.ticks_ms, sleep_ms=self.sleep_ms,
                                          ticks_diff=lambda a, b: a - b),
            "select": types.SimpleNamespace(poll=lambda: self, POLLIN=1),
            "network": types.SimpleNamespace(STA_IF=0, STAT_CONNECTING=1,
                                             hostname=lambda name: None, WLAN=self.make_wlan),
            "socket": types.SimpleNamespace(AF_INET=2, SOCK_DGRAM=2, socket=self.make_socket),
            # None in sys.modules makes `import wifi_secrets` raise ImportError
            "wifi_secrets": (types.SimpleNamespace(SSID="home", PASSWORD="pw")
                             if self.has_wifi else None),
        }
        out = io.StringIO()
        old_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)                       # config.json lands in a scratch folder
            try:
                with mock.patch.dict(sys.modules, modules), \
                        mock.patch.object(sys, "stdin", self), \
                        contextlib.redirect_stdout(out):
                    try:
                        runpy.run_path(MAIN_PY, run_name="__main__")
                    except StopLoop:
                        pass
            finally:
                os.chdir(old_cwd)
        return out.getvalue().splitlines()


class UsbTest(unittest.TestCase):
    def test_boot_commands_and_smooth_motion(self):
        printed = Sim(usb=[
            (0, "?\r\n"),                   # Thonny-style line ending
            (1, "P120 T30\n"),              # brain-style line ending
            (2, "bogus\n"),
            (3, "SPE"), (4, "ED 60\n"),     # a line split across two reads
            (60, "?\n"),                    # ~1.2 s later: move has finished
        ]).run(ticks=70)
        self.assertEqual(printed, [
            "READY skynode-pico",
            "POS P90.0 T45.0",
            "ERR unknown command BOGUS",
            "OK",
            "POS P120.0 T30.0",
        ])

    def test_overlong_line_is_truncated_not_crashing(self):
        printed = Sim(usb=[(0, "P" + "9" * 500 + "\n"), (1, "?\n")]).run(ticks=3)
        self.assertEqual(printed[0], "READY skynode-pico")
        self.assertEqual(len(printed), 2)       # no reply to the (silent) move, then POS
        self.assertTrue(printed[1].startswith("POS"))


class WifiTest(unittest.TestCase):
    def test_commands_over_wifi_reply_to_sender(self):
        sim = Sim(wifi=5, packets=[
            (6, "?\n"),
            (7, "P120\nT30\n"),             # two commands in one datagram
            (8, "bogus"),                   # no newline at all is fine too
            (60, "?\n"),
        ])
        printed = sim.run(ticks=70)
        self.assertEqual(printed, ["READY skynode-pico", "WIFI up 192.168.1.50 port 5005"])
        self.assertEqual(sim.sent, [
            ("POS P90.0 T45.0\n", BRAIN),
            ("ERR unknown command BOGUS\n", BRAIN),
            ("POS P120.0 T30.0\n", BRAIN),
        ])

    def test_usb_still_works_alongside_wifi(self):
        sim = Sim(wifi=0, usb=[(3, "P10\n")], packets=[(40, "?\n")])
        sim.run(ticks=50)
        self.assertEqual(sim.sent, [("POS P10.0 T45.0\n", BRAIN)])

    def test_link_drop_is_reported_and_retried(self):
        sim = Sim(wifi=5, wifi_down_at=20)
        printed = sim.run(ticks=20 + 15000 // 20 + 10)     # past one 15 s retry window
        self.assertEqual(printed, [
            "READY skynode-pico",
            "WIFI up 192.168.1.50 port 5005",
            "WIFI down",
            "WIFI retry (last status -2)",
        ])
        self.assertEqual(sim.connect_calls, 2)              # boot + one retry

    def test_no_secrets_file_means_usb_only(self):
        sim = Sim(wifi=False, packets=[(1, "?\n")])
        printed = sim.run(ticks=5)
        self.assertEqual(printed, ["READY skynode-pico"])
        self.assertEqual(sim.sent, [])


if __name__ == "__main__":
    unittest.main()
