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
        # The model path gets resolved against brain/, everything else should be a default
        self.assertEqual(Path(cfg.model.path), REPO / "brain" / "models" / "yolov8n.onnx")
        cfg.model.path = defaults.model.path
        self.assertEqual(cfg, defaults)

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

    def test_typos_are_errors(self):
        with self.assertRaises(ValueError):
            load_config(self.write("[control]\ngian = 0.5\n"))
        with self.assertRaises(ValueError):
            load_config(self.write("[contrl]\ngain = 0.5\n"))


if __name__ == "__main__":
    unittest.main()
