"""Brain settings: the defaults live here, your changes go in brain/config.toml.

The TOML file only needs the settings you want to change. A misspelled
setting name is an error, not something that gets silently ignored.
"""
import os
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path


@dataclass
class CameraConfig:
    source: int | str = 0             # webcam number (0 = first camera) or a video file
    width: int = 1280                 # requested capture size; the camera picks the nearest it has
    height: int = 720
    hfov_deg: float = 70.0            # horizontal field of view in degrees


@dataclass
class ModelConfig:
    path: str = "models/yolov8n.onnx"     # relative to the config file
    target_classes: list = field(default_factory=lambda: ["airplane", "bird"])
    min_confidence: float = 0.35
    iou_threshold: float = 0.45


@dataclass
class TrackerConfig:
    max_missed_frames: int = 15
    max_jump: float = 0.25


@dataclass
class ControlConfig:
    gain: float = 0.35
    deadband_deg: float = 0.5
    max_step_deg: float = 8.0
    pan_sign: int = -1
    tilt_sign: int = 1
    home_after_s: float = 10.0


@dataclass
class LinkConfig:
    type: str = "none"                # "wifi", "usb", or "none"
    serial_port: str = "auto"
    wifi_host: str = "auto"
    wifi_port: int = 5005


@dataclass
class DisplayConfig:
    show: bool = True


@dataclass
class LoggerConfig:
    enabled: bool = True
    folder: str = "../logs"           # relative to the config file -> <repo>/logs (gitignored)
    min_duration_s: float = 0.5       # locks shorter than this aren't logged (detector blinks)
    snapshots: bool = True            # save a JPEG of the best frame of each sighting
    heartbeat_min: int = 60           # log a "clear" sky check this often while nothing is
                                      # tracked; 0 turns it off
    drone_classes: list = field(default_factory=lambda: ["drone"])
    aircraft_classes: list = field(default_factory=lambda: ["airplane", "aircraft", "helicopter"])


@dataclass
class DashboardConfig:
    enabled: bool = True
    host: str = "127.0.0.1"           # "0.0.0.0" = reachable from other devices on your Wi-Fi
    port: int = 8080
    node_name: str = "NODE-01"
    location: str = ""                # optional label shown in the header, e.g. "BACKYARD"
    stream_fps: float = 12.0          # max frames per second sent to the browser
    stream_width: int = 960           # stream frames are shrunk to this width


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    tracker: TrackerConfig = field(default_factory=TrackerConfig)
    control: ControlConfig = field(default_factory=ControlConfig)
    link: LinkConfig = field(default_factory=LinkConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    logger: LoggerConfig = field(default_factory=LoggerConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)


def load_config(path):
    """Defaults, overridden by whatever the TOML file at `path` sets."""
    path = Path(path)
    config = Config()
    with open(path, "rb") as f:
        data = tomllib.load(f)

    sections = {f.name for f in fields(config)}
    for section_name, values in data.items():
        if section_name not in sections or not isinstance(values, dict):
            raise ValueError(f"{path}: unknown section [{section_name}]")
        section = getattr(config, section_name)
        known = {f.name for f in fields(section)}
        for key, value in values.items():
            if key not in known:
                raise ValueError(f"{path}: unknown setting '{key}' in [{section_name}]")
            setattr(section, key, value)

    # A relative model path means "relative to the config file", not to
    # wherever you happen to run the command from.
    model_path = Path(config.model.path)
    if not model_path.is_absolute():
        config.model.path = str(path.parent / model_path)

    # Same for the log folder. normpath tidies "brain/../logs" into "logs",
    # so the folder printed at start-up is easy to find.
    log_folder = Path(config.logger.folder)
    if not log_folder.is_absolute():
        config.logger.folder = os.path.normpath(path.parent / log_folder)
    return config
