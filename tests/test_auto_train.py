"""Tests for training/auto_train.py's logic (the parts that need no GPU)."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "training"))
import auto_train as at  # noqa: E402


class TempProject(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name)
        (self.project / "phone_videos").mkdir()
        (self.project / "models").mkdir()

    def clip(self, name):
        path = self.project / "phone_videos" / name
        path.write_bytes(b"x")
        return path


class ClipBookkeepingTest(TempProject):
    def test_new_clips_skip_the_used_ones(self):
        self.clip("drone_a.mp4")
        self.clip("aircraft_b.mov")
        self.assertEqual([c.name for c in at.new_clips(self.project)], ["aircraft_b.mov", "drone_a.mp4"])
        at.save_used(self.project, {"drone_a.mp4"})
        self.assertEqual([c.name for c in at.new_clips(self.project)], ["aircraft_b.mov"])

    def test_manifest_survives_a_restart(self):
        at.save_used(self.project, {"x.mp4", "y.mp4"})
        self.assertEqual(at.load_used(self.project), {"x.mp4", "y.mp4"})
        json.loads((self.project / at.MANIFEST).read_text())      # plain, readable JSON

    def test_no_phone_videos_folder_is_fine(self):
        (self.project / "phone_videos").rmdir()
        self.assertEqual(at.new_clips(self.project), [])


class StartingModelTest(TempProject):
    def test_uses_the_newest_model_in_models(self):
        old = self.project / "models" / "a.pt"
        new = self.project / "models" / "b.pt"
        old.write_bytes(b"1")
        new.write_bytes(b"2")
        now = time.time()
        os.utime(old, (now - 100, now - 100))
        os.utime(new, (now, now))
        self.assertEqual(at.current_weights(self.project), new)

    def test_falls_back_to_the_starting_weights(self):
        self.assertEqual(at.current_weights(self.project), self.project / at.DEFAULT_START)


class SafetyGateTest(unittest.TestCase):
    def test_a_better_model_is_promoted(self):
        self.assertTrue(at.better_or_equal({"mAP50": (0.80, True)}, {"mAP50": (0.85, True)}))

    def test_an_equal_model_is_promoted(self):
        self.assertTrue(at.better_or_equal({"mAP50": (0.80, True)}, {"mAP50": (0.80, True)}))

    def test_a_worse_model_is_not(self):
        self.assertFalse(at.better_or_equal({"mAP50": (0.80, True)}, {"mAP50": (0.70, True)}))

    def test_tolerance_allows_small_wobble_only(self):
        self.assertTrue(at.better_or_equal({"mAP50": (0.80, True)}, {"mAP50": (0.79, True)}, tolerance=0.02))
        self.assertFalse(at.better_or_equal({"mAP50": (0.80, True)}, {"mAP50": (0.70, True)}, tolerance=0.02))

    def test_lower_is_better_measures(self):
        self.assertTrue(at.better_or_equal({"false_drone": (0.10, False)}, {"false_drone": (0.05, False)}))
        self.assertFalse(at.better_or_equal({"false_drone": (0.10, False)}, {"false_drone": (0.20, False)}))

    def test_nothing_to_compare_never_promotes(self):
        self.assertFalse(at.better_or_equal({}, {"mAP50": (0.9, True)}))
        self.assertFalse(at.better_or_equal({"mAP50": (0.5, True)}, {}))
        self.assertFalse(at.better_or_equal({"mAP50": (0.5, True)}, {"other": (0.9, True)}))


class PlanTest(TempProject):
    def test_plan_lists_what_will_happen(self):
        clip = self.clip("drone_x.mp4")
        plan = at.run_plan(self.project, [clip])
        self.assertEqual(plan["new_clips"], ["drone_x.mp4"])
        self.assertEqual(plan["already_used"], 0)
        self.assertTrue(plan["start_weights"].endswith(at.DEFAULT_START))

    def test_main_with_no_new_clips_stops_cleanly(self):
        import io
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = at.main(["--project", str(self.project)])
        self.assertEqual(code, 0)
        self.assertIn("No new clips", out.getvalue())


if __name__ == "__main__":
    unittest.main()
