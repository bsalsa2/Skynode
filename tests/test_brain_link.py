"""Tests for brain/link.py.

The Wi-Fi tests talk to the REAL Pico command code (pico/pantilt.py, on a fake
`machine` module) behind a UDP socket on this computer, so they also check
that the brain and the Pico agree on the protocol.
"""
import importlib.util
import os
import socket
import tempfile
import threading
import time
import unittest
from unittest import mock

import fake_machine  # noqa: F401  (puts pico/ on sys.path)
from pantilt import PanTilt, default_config

from brain.link import NullLink, UdpLink, find_pico_port, open_link, read_pico_state

HAS_PYSERIAL = importlib.util.find_spec("serial") is not None


class FakePico:
    """pico/pantilt.py answering UDP on 127.0.0.1, like main.py does over Wi-Fi."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rig = PanTilt(default_config(), config_path=os.path.join(self.tmp.name, "c.json"))
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.received = []
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        while True:
            try:
                data, sender = self.sock.recvfrom(256)
            except OSError:                 # socket closed: test is over
                return
            for line in data.decode().split("\n"):
                if line:
                    self.received.append(line)
                reply = self.rig.handle(line)
                if reply:
                    self.sock.sendto((reply + "\n").encode(), sender)

    def close(self):
        self.sock.close()
        self.tmp.cleanup()


class UdpLinkTest(unittest.TestCase):
    def setUp(self):
        self.pico = FakePico()
        self.addCleanup(self.pico.close)

    def test_query_and_send(self):
        link = UdpLink("127.0.0.1", self.pico.port)
        self.addCleanup(link.close)
        self.assertEqual(link.query("?"), "POS P90.0 T45.0")
        link.send("P100 T50")
        deadline = time.monotonic() + 2
        while "P100 T50" not in self.pico.received and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(self.pico.rig.servos["pan"].target, 100)

    def test_discovery_finds_the_pico(self):
        # Real use broadcasts to 255.255.255.255; localhost stands in for "the network" here.
        link = UdpLink("auto", self.pico.port, broadcast_address="127.0.0.1")
        self.addCleanup(link.close)
        self.assertEqual(link.address, ("127.0.0.1", self.pico.port))

    def test_read_pico_state(self):
        self.pico.rig.handle("LIM T 0 90")
        self.pico.rig.handle("P120")
        self.pico.rig.update(5)
        link = UdpLink("127.0.0.1", self.pico.port)
        self.addCleanup(link.close)
        settings, position = read_pico_state(link)
        self.assertEqual(settings["tilt"]["max_deg"], 90)
        self.assertEqual(position, (120.0, 45.0))


class NoPicoTest(unittest.TestCase):
    def test_discovery_gives_up_with_a_helpful_error(self):
        silent = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        silent.bind(("127.0.0.1", 0))               # a port where nobody answers
        self.addCleanup(silent.close)
        with self.assertRaises(ConnectionError) as ctx:
            UdpLink("auto", silent.getsockname()[1], timeout=0.05, broadcast_address="127.0.0.1")
        self.assertIn("No Pico answered", str(ctx.exception))

    def test_null_link(self):
        link = open_link("none")
        self.assertIsInstance(link, NullLink)
        link.send("P90")
        self.assertIsNone(link.query("?"))
        self.assertEqual(read_pico_state(link), (None, None))

    def test_unknown_link_type(self):
        with self.assertRaises(ValueError):
            open_link("bluetooth")


@unittest.skipUnless(HAS_PYSERIAL, "pyserial not installed")
class SerialLinkTest(unittest.TestCase):
    def test_finds_pico_by_usb_vendor_id(self):
        from serial.tools import list_ports_common
        other = list_ports_common.ListPortInfo("/dev/ttyUSB0")
        other.vid = 0x1A86
        pico = list_ports_common.ListPortInfo("/dev/ttyACM0")
        pico.vid = 0x2E8A
        with mock.patch("serial.tools.list_ports.comports", return_value=[other, pico]):
            self.assertEqual(find_pico_port(), "/dev/ttyACM0")
        with mock.patch("serial.tools.list_ports.comports", return_value=[other]):
            with self.assertRaises(ConnectionError):
                find_pico_port()

    def test_send_and_query_over_a_loopback_port(self):
        import serial
        loop = serial.serial_for_url("loop://", timeout=0.2)    # echoes what we write
        with mock.patch("serial.Serial", return_value=loop):
            link = open_link("usb", serial_port="loop")
        self.assertEqual(link.query("?"), "?")                   # the echo comes back as the "reply"
        link.close()


if __name__ == "__main__":
    unittest.main()
