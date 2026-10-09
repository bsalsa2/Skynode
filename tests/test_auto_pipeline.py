"""Tests for training/automation (Drive watcher, Kaggle job, kernel layout).

Drive and Kaggle are faked: nothing here touches a network or needs the Google or Kaggle
libraries. The live calls are checked by real runs of .github/workflows/auto-train.yml.
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "training" / "automation"))
import drive_watch as dw  # noqa: E402
import kaggle_train as kt  # noqa: E402
import run_pipeline as rp  # noqa: E402

FULL_ENV = {
    "GOOGLE_SERVICE_ACCOUNT_JSON": "{}", "KAGGLE_USERNAME": "someone", "KAGGLE_KEY": "k",
    "DRIVE_CLIP_FOLDER_IDS": "folderA, folderB", "DRIVE_START_WEIGHTS_FILE_ID": "weights1",
}


def clip(name, size=10):
    return {"id": f"id-{name}", "name": name, "size": size, "folder": "folderA"}


class FakeRequest:
    def __init__(self, reply):
        self.reply = reply

    def execute(self):
        return self.reply


class FakeDrive:
    """A fake Drive: one list of pages per folder id."""

    def __init__(self, pages_by_folder):
        self.pages_by_folder = pages_by_folder
        self.queries = []

    def files(self):
        return self

    def list(self, q, pageToken=None, **_):
        self.queries.append(q)
        folder = q.split("'")[1]
        return FakeRequest(self.pages_by_folder[folder][pageToken])


class Config(unittest.TestCase):
    def test_missing_pieces_are_named_and_stop_quietly(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = rp.main([], environ={"KAGGLE_USERNAME": "x"})
        self.assertEqual(code, 0)
        for name in ("GOOGLE_SERVICE_ACCOUNT_JSON", "KAGGLE_KEY", "DRIVE_CLIP_FOLDER_IDS"):
            self.assertIn(name, out.getvalue())
        self.assertNotIn("KAGGLE_USERNAME,", out.getvalue())

    def test_a_full_config_is_parsed(self):
        config = rp.read_config(FULL_ENV)
        self.assertEqual(config["folders"], ["folderA", "folderB"])
        self.assertEqual(config["user"], "someone")

    def test_odd_ids_are_refused(self):
        for bad in ("a' or '1'='1", "../x", "a b/c"):
            with self.assertRaises(ValueError):
                rp.read_config({**FULL_ENV, "DRIVE_CLIP_FOLDER_IDS": bad})
        with self.assertRaises(ValueError):
            rp.read_config({**FULL_ENV, "DRIVE_START_WEIGHTS_FILE_ID": "x y"})


class Planning(unittest.TestCase):
    def test_used_clips_are_skipped(self):
        batch, later = rp.pick_new([clip("a.mp4"), clip("b.mp4")], {"a.mp4"})
        self.assertEqual([c["name"] for c in batch], ["b.mp4"])
        self.assertEqual(later, [])

    def test_the_batch_is_capped_and_the_rest_waits(self):
        clips = [clip("a.mp4", 60), clip("b.mp4", 60), clip("c.mp4", 10)]
        batch, later = rp.pick_new(clips, set(), cap=100)
        self.assertEqual([c["name"] for c in batch], ["a.mp4"])
        self.assertEqual([c["name"] for c in later], ["b.mp4", "c.mp4"])

    def test_one_huge_clip_is_still_taken(self):
        batch, later = rp.pick_new([clip("big.mp4", 999)], set(), cap=100)
        self.assertEqual([c["name"] for c in batch], ["big.mp4"])
        self.assertEqual(later, [])

    def test_kaggle_status_words(self):
        self.assertEqual(rp.parse_status('u/skynode-train has status "KernelWorkerStatus.COMPLETE"'), "COMPLETE")
        self.assertEqual(rp.parse_status('u/skynode-train has status "running"'), "RUNNING")
        self.assertEqual(rp.parse_status('has status "KernelWorkerStatus.ERROR"'), "ERROR")
        self.assertEqual(rp.parse_status("nothing useful"), "UNKNOWN")

    def test_a_recent_failure_pauses_retries(self):
        now = datetime.now(timezone.utc)
        recent = json.dumps({"time": (now - timedelta(hours=2)).isoformat()})
        old = json.dumps({"time": (now - timedelta(hours=30)).isoformat()})
        self.assertTrue(rp.recently_failed(recent, now))
        self.assertFalse(rp.recently_failed(old, now))
        for junk in ("", "not json", "{}", '{"time": "yesterday"}'):
            self.assertFalse(rp.recently_failed(junk, now))

    def test_metadata_asks_for_a_private_gpu_kernel_on_our_dataset(self):
        kernel = rp.kernel_metadata("someone")
        self.assertTrue(kernel["enable_gpu"] and kernel["enable_internet"] and kernel["is_private"])
        self.assertEqual(kernel["dataset_sources"], [f"someone/{rp.DATASET_SLUG}"])
        self.assertEqual(kernel["code_file"], "kaggle_train.py")
        self.assertEqual(rp.dataset_metadata("someone")["id"], f"someone/{rp.DATASET_SLUG}")
        self.assertTrue((rp.HERE / kernel["code_file"]).is_file())

    def test_summary_line(self):
        self.assertEqual(rp.run_summary({"status": "promoted", "new": {"mAP50": [0.8123, True]}}),
                         "promoted, mAP50 0.812")
        self.assertEqual(rp.run_summary({"status": "kept old model"}), "kept old model")
        self.assertEqual(rp.run_summary({}), "unknown")


class DriveListing(unittest.TestCase):
    def test_videos_only_across_pages_and_folders(self):
        pages = {
            "folderA": {None: {"files": [{"id": "1", "name": "b.MOV", "size": "5"},
                                         {"id": "2", "name": "notes.txt"}],
                               "nextPageToken": "p2"},
                        "p2": {"files": [{"id": "3", "name": "a.mp4", "size": "7"},
                                         {"id": "4", "name": ".hidden.mp4"}]}},
            "folderB": {None: {"files": [{"id": "5", "name": "a.mp4", "size": "9"},
                                         {"id": "6", "name": "c.webm"}]}},
        }
        drive = FakeDrive(pages)
        found = dw.list_clips(drive, ["folderA", "folderB"])
        self.assertEqual([c["name"] for c in found], ["a.mp4", "b.MOV", "c.webm"])
        self.assertEqual(found[0]["id"], "3")           # the first folder wins a repeated name
        self.assertEqual(found[0]["size"], 7)
        self.assertTrue(all("trashed = false" in q for q in drive.queries))

    def test_a_dodgy_folder_id_never_reaches_the_query(self):
        with self.assertRaises(ValueError):
            dw.list_clips(FakeDrive({}), ["x' or name contains 'a"])

    def test_the_scope_is_read_only(self):
        self.assertTrue(dw.SCOPE.endswith("drive.readonly"))


class DryRun(unittest.TestCase):
    def setUp(self):
        self.drive = FakeDrive({"folderA": {None: {"files": [{"id": "1", "name": "new.mp4", "size": "5"},
                                                               {"id": "2", "name": "old.mp4", "size": "5"}]}},
                                "folderB": {None: {"files": []}}})

    def run_main(self, used='{"used": ["old.mp4"]}', failure="", argv=("--dry-run",)):
        def fake_state(tag, name, folder):
            return failure if name == rp.FAILURE_FILE else used
        out = io.StringIO()
        with mock.patch.object(rp.dw, "drive_service", return_value=self.drive), \
             mock.patch.object(rp, "read_state_file", side_effect=fake_state), \
             mock.patch.object(rp, "sh", side_effect=AssertionError("must not run commands")), \
             contextlib.redirect_stdout(out):
            code = rp.main(list(argv), environ=FULL_ENV)
        return code, out.getvalue()

    def test_dry_run_reports_and_changes_nothing(self):
        code, text = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("1 new now", text)
        self.assertIn("new.mp4", text)
        self.assertIn("Look-only run", text)
        self.assertIn("train_for_real", text)

    def test_nothing_new_stops_early(self):
        code, text = self.run_main(used='{"used": ["old.mp4", "new.mp4"]}', argv=())
        self.assertEqual(code, 0)
        self.assertIn("0 new now", text)

    def test_a_recent_failure_stops_a_real_run(self):
        failure = json.dumps({"time": datetime.now(timezone.utc).isoformat()})
        code, text = self.run_main(failure=failure, argv=())
        self.assertEqual(code, 0)
        self.assertIn("not retrying", text)


class KernelLayout(unittest.TestCase):
    def test_the_dataset_becomes_a_project_auto_train_understands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "input" / "skynode-train-input"
            (dataset / "clips").mkdir(parents=True)
            (dataset / "clips" / "a.mp4").write_bytes(b"video")
            (dataset / "current.pt").write_bytes(b"weights")
            (dataset / "used_clips.json").write_text('{"used": ["old.mp4"]}')
            self.assertEqual(kt.find_dataset(root / "input"), dataset)

            project = root / "project"
            kt.prepare_project(dataset, project)
            self.assertEqual((project / "phone_videos" / "a.mp4").read_bytes(), b"video")
            self.assertEqual((project / "models" / "current.pt").read_bytes(), b"weights")

            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "training"))
            import auto_train as at
            self.assertEqual([c.name for c in at.new_clips(project)], ["a.mp4"])
            self.assertEqual(at.current_weights(project).name, "current.pt")
            self.assertEqual(at.load_used(project), {"old.mp4"})

    def test_no_dataset_is_a_clear_stop(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(SystemExit):
            kt.find_dataset(Path(tmp))


if __name__ == "__main__":
    unittest.main()
