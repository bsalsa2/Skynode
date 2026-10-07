"""Tests for brain/config.py and the shipped brain/config.toml."""
import os
import tempfile
import unittest
from pathlib import Path

from brain.config import Config, load_config

REPO = Path(__file__).resolve().parent.parent


class ConfigTest(unittest.TestCase):
    def write(self, text):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "config.toml"
        path.write_text(text)
        return path

    def test_shipped_config_loads_and_matches_defaults(self):
        cfg = load_config(REPO / "brain" / "config.toml")
        defaults = Config()
        # The model path and the log folder get resolved against brain/,
        # everything else should be a default
        self.assertEqual(Path(cfg.model.path), REPO / "brain" / "models" / "yolov8n.onnx")
        self.assertEqual(Path(cfg.logger.folder), REPO / "logs")
        cfg.model.path = defaults.model.path
        cfg.logger.folder = defaults.logger.folder
        self.assertEqual(cfg, defaults)

    def test_logger_and_dashboard_defaults(self):
        cfg = Config()
        self.assertTrue(cfg.logger.enabled)
        self.assertEqual(cfg.logger.min_duration_s, 0.5)
        self.assertEqual(cfg.logger.heartbeat_min, 60)
        self.assertEqual(cfg.logger.drone_classes, ["drone"])
        self.assertEqual(cfg.logger.aircraft_classes, ["airplane", "aircraft", "helicopter"])
        self.assertEqual((cfg.dashboard.host, cfg.dashboard.port), ("127.0.0.1", 8080))
        self.assertEqual(cfg.dashboard.node_name, "NODE-01")
        # Each Config gets its own lists, so changing one never changes another
        cfg.logger.drone_classes.append("kite")
        self.assertEqual(Config().logger.drone_classes, ["drone"])

    def test_partial_file_keeps_other_defaults(self):
        cfg = load_config(self.write('[link]\ntype = "wifi"\n[model]\ntarget_classes = ["drone"]\n'))
        self.assertEqual(cfg.link.type, "wifi")
        self.assertEqual(cfg.link.wifi_port, 5005)
        self.assertEqual(cfg.model.target_classes, ["drone"])
        self.assertEqual(cfg.control.gain, Config().control.gain)

    def test_model_path_is_relative_to_the_config_file(self):
        path = self.write('[model]\npath = "custom/drone.onnx"\n')
        self.assertEqual(load_config(path).model.path, str(path.parent / "custom" / "drone.onnx"))

    def test_absolute_model_path_is_kept(self):
        absolute = os.path.abspath(os.sep + "models" + os.sep + "x.onnx")
        cfg = load_config(self.write(f"[model]\npath = '{absolute}'\n"))   # '...' = no escapes
        self.assertEqual(cfg.model.path, absolute)

    def test_log_folder_is_relative_to_the_config_file(self):
        path = self.write('[logger]\nfolder = "../my-logs"\n')
        self.assertEqual(load_config(path).logger.folder,
                         os.path.normpath(path.parent.parent / "my-logs"))
        # Left out, it's the default "../logs" next to the config file's folder
        self.assertEqual(load_config(self.write("")).logger.folder,
                         os.path.normpath(path.parent.parent / "logs"))

    def test_absolute_log_folder_is_kept(self):
        absolute = os.path.abspath(os.sep + "data" + os.sep + "skynode-logs")
        cfg = load_config(self.write(f"[logger]\nfolder = '{absolute}'\n"))
        self.assertEqual(cfg.logger.folder, absolute)

    def test_dashboard_settings_load(self):
        cfg = load_config(self.write('[dashboard]\nhost = "0.0.0.0"\nport = 9000\n'
                                     'location = "BACKYARD"\n'))
        self.assertEqual((cfg.dashboard.host, cfg.dashboard.port), ("0.0.0.0", 9000))
        self.assertEqual(cfg.dashboard.location, "BACKYARD")
        self.assertEqual(cfg.dashboard.stream_fps, 12.0)

    def test_typos_are_errors(self):
        with self.assertRaises(ValueError):
            load_config(self.write("[control]\ngian = 0.5\n"))
        with self.assertRaises(ValueError):
            load_config(self.write("[contrl]\ngain = 0.5\n"))
        with self.assertRaises(ValueError):
            load_config(self.write("[dashboard]\nprot = 8081\n"))


if __name__ == "__main__":
    unittest.main()
