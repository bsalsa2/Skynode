"""Connections from the brain to the Pico: Wi-Fi (UDP), USB serial, or none.

All three share the same small interface, so the rest of the brain never
needs to know which one is in use:

    send(line)             fire and forget (used for moves)
    query(line) -> reply   send, then wait briefly for a one-line reply (None if none came)
    close()
    description            short text for status displays, e.g. "wifi 192.168.1.42:5005"

The commands themselves are documented in pico/README.md.
"""
import json
import socket
import time

WIFI_PORT = 5005
PICO_USB_VENDOR_ID = 0x2E8A          # Raspberry Pi's USB vendor ID


def open_link(kind, serial_port="auto", wifi_host="auto", wifi_port=WIFI_PORT):
    if kind == "wifi":
        return UdpLink(wifi_host, wifi_port)
    if kind == "usb":
        return SerialLink(serial_port)
    if kind == "none":
        return NullLink()
    raise ValueError(f'link type must be "wifi", "usb" or "none", not {kind!r}')


class UdpLink:
    """Wi-Fi: short UDP messages to the Pico's port 5005."""

    def __init__(self, host="auto", port=WIFI_PORT, timeout=0.5,
                 broadcast_address="255.255.255.255"):
        self.timeout = timeout
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        if host == "auto":
            self.address = self.discover((broadcast_address, port))
        else:
            self.address = (socket.gethostbyname(host), port)
        self.description = f"wifi {self.address[0]}:{port}"

    def discover(self, broadcast, attempts=3):
        """Send "?" to every device on the local network; the Pico answers from its own address."""
        for _ in range(attempts):
            self.sock.sendto(b"?\n", broadcast)
            reply = self._receive(expect_from=None)
            if reply and reply[0].startswith("POS"):
                return reply[1]
        raise ConnectionError(
            f"No Pico answered on UDP port {broadcast[1]}. Is it powered and showing "
            "'WIFI up' in Thonny, on the same network as this computer? You can also set "
            "wifi_host in brain/config.toml to the IP address it printed.")

    def send(self, line):
        try:
            self.sock.sendto((line + "\n").encode(), self.address)
        except ConnectionResetError:
            pass        # Windows reports an earlier undeliverable packet here; not fatal

    def query(self, line):
        self._drain()
        self.send(line)
        reply = self._receive(expect_from=self.address)
        return reply[0] if reply else None

    def close(self):
        self.sock.close()

    def _receive(self, expect_from):
        """Wait up to `timeout` for a message (only from `expect_from`, if given).

        Returns (text, sender), or None if nothing arrived in time.
        """
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            self.sock.settimeout(remaining)
            try:
                data, sender = self.sock.recvfrom(4096)
            except socket.timeout:
                return None
            except ConnectionResetError:        # Windows: "the Pico wasn't listening"
                continue
            if expect_from is None or sender == expect_from:
                return data.decode(errors="replace").strip(), sender

    def _drain(self):
        """Throw away anything already waiting, e.g. a late reply to an earlier query."""
        self.sock.setblocking(False)
        try:
            while True:
                self.sock.recvfrom(4096)
        except OSError:                         # nothing left (or a Windows reset report)
            pass


class SerialLink:
    """USB serial: the Pico shows up as a serial port (COM5, /dev/ttyACM0, ...)."""

    def __init__(self, port="auto", timeout=0.5):
        import serial                           # pyserial; only this link needs it
        if port == "auto":
            port = find_pico_port()
        try:
            self.serial = serial.Serial(port, 115200, timeout=timeout)  # USB ignores the baud rate
        except serial.SerialException as err:
            raise ConnectionError(f"Can't open {port}: {err}. If Thonny is open, close it: "
                                  "only one program can use the port at a time.") from err
        self.description = f"usb {port}"

    def send(self, line):
        self.serial.write((line + "\n").encode())

    def query(self, line):
        self.serial.reset_input_buffer()
        self.send(line)
        reply = self.serial.readline().decode(errors="replace").strip()
        return reply or None

    def close(self):
        self.serial.close()


def find_pico_port():
    """Find the Pico among the computer's serial ports by its USB vendor ID."""
    from serial.tools import list_ports
    for port in list_ports.comports():
        if port.vid == PICO_USB_VENDOR_ID:
            return port.device
    raise ConnectionError("No Pico found on USB. Is it plugged in with a data cable "
                          "(some cables only carry power)?")


class NullLink:
    """No Pico: detection and tracking only. Commands go nowhere."""

    description = "none"

    def send(self, line):
        pass

    def query(self, line):
        return None

    def close(self):
        pass


def read_pico_state(link):
    """Ask the Pico for its settings (CFG) and current angles (?).

    Returns (settings, (pan, tilt)). Either is None if the Pico didn't answer.
    """
    settings = position = None
    reply = link.query("CFG")
    if reply and reply.startswith("CFG "):
        try:
            settings = json.loads(reply[4:])
        except ValueError:
            pass
    reply = link.query("?")
    if reply and reply.startswith("POS "):
        _, pan, tilt = reply.split()             # "POS P90.0 T45.0"
        position = (float(pan[1:]), float(tilt[1:]))
    return settings, position
