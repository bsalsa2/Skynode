"""Tests for training/skynode_data.py (the Colab notebook's bookkeeping).

Needs numpy and OpenCV (they make the tiny test videos and pictures).
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

if not all(importlib.util.find_spec(name) for name in ("numpy", "cv2")):
    raise unittest.SkipTest("needs numpy, cv2")

import cv2          # noqa: E402
import numpy as np  # noqa: E402

from training.skynode_data import (DatasetBuilder, class_hint, dataset_warnings, draw_preview,  # noqa: E402
                                   extract_frames, format_label, list_videos, make_contact_sheet,
                                   parse_label_lines, remap_labels, safe_name, split_frames, video_of)

CLASSES = ["drone", "airplane", "bird"]


def write_video(path, frames=60, fps=30, size=(320, 240)):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, size)
    for i in range(frames):
        writer.write(np.full((size[1], size[0], 3), i * 3 % 255, dtype=np.uint8))
    writer.release()


def write_image(path, size=(320, 240)):
    cv2.imwrite(str(path), np.full((size[1], size[0], 3), 90, dtype=np.uint8))


class TempCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)


class FramesTest(TempCase):
    def test_extracts_about_one_frame_per_interval(self):
        video = self.tmp / "drone_backyard.avi"
        write_video(video, frames=90, fps=30)               # 3 seconds
        frames = extract_frames(video, self.tmp / "out", every_s=1.0)
        self.assertEqual([p.name for p in frames],
                         ["drone-backyard__000000.jpg", "drone-backyard__000030.jpg",
                          "drone-backyard__000060.jpg"])
        self.assertTrue(all(p.exists() for p in frames))

    def test_max_frames_and_resize(self):
        video = self.tmp / "big.avi"
        write_video(video, frames=60, fps=30, size=(640, 480))
        frames = extract_frames(video, self.tmp / "out", every_s=0.1, max_frames=4, max_side=320)
        self.assertEqual(len(frames), 4)
        height, width = cv2.imread(str(frames[0])).shape[:2]
        self.assertEqual((width, height), (320, 240))

    def test_unreadable_video_is_a_clear_error(self):
        bad = self.tmp / "nope.mp4"
        bad.write_bytes(b"not a video")
        with self.assertRaises(ValueError):
            extract_frames(bad, self.tmp / "out")

    def test_list_videos_ignores_other_files(self):
        for name in ("b.MP4", "a.mov", "notes.txt", ".hidden.mp4"):
            (self.tmp / name).write_bytes(b"x")
        self.assertEqual([p.name for p in list_videos(self.tmp)], ["a.mov", "b.MP4"])

    def test_names(self):
        self.assertEqual(safe_name("My Clip (1)"), "My-Clip--1")
        self.assertEqual(class_hint("Drone_garden.mp4", CLASSES), "drone")
        self.assertIsNone(class_hint("sky_morning.mp4", CLASSES))
        self.assertIsNone(class_hint("IMG_1234.MOV", CLASSES))
        self.assertEqual(video_of("drone-backyard__000030.jpg"), "drone-backyard")


class LabelTest(unittest.TestCase):
    def test_format_label_normalises(self):
        self.assertEqual(format_label(1, 100, 50, 200, 150, 400, 200), "1 0.375000 0.500000 0.250000 0.500000")

    def test_format_label_clamps_and_rejects_specks(self):
        self.assertEqual(format_label(0, -50, 0, 100, 100, 200, 100), "0 0.250000 0.500000 0.500000 1.000000")
        self.assertIsNone(format_label(0, 10, 10, 11, 50, 200, 100))          # 1 px wide
        self.assertIsNone(format_label(0, 300, 10, 400, 50, 200, 100))        # fully off the image

    def test_parse_skips_damaged_lines(self):
        lines = ["0 0.5 0.5 0.2 0.2", "", "x 0.5 0.5 0.2 0.2", "0 0.5 0.5 0.2", "1 1.5 0.5 0.2 0.2",
                 "2 0.5 0.5 0 0.2", "-1 0.5 0.5 0.1 0.1"]
        self.assertEqual(parse_label_lines(lines), [(0, 0.5, 0.5, 0.2, 0.2)])

    def test_remap_matches_by_name_and_drops_unknown(self):
        source = ["person", "Airplane", "bird", "car"]
        lines = ["1 0.1 0.2 0.3 0.4", "2 0.5 0.5 0.1 0.1", "0 0.5 0.5 0.1 0.1", "9 0.5 0.5 0.1 0.1"]
        new, dropped = remap_labels(lines, source, CLASSES)
        self.assertEqual(new, ["1 0.1 0.2 0.3 0.4", "2 0.5 0.5 0.1 0.1"])
        self.assertEqual(dropped, 2)


class SplitTest(unittest.TestCase):
    def frames(self, **counts):
        return [f"{video}__{i:06d}.jpg" for video, n in counts.items() for i in range(n)]

    def test_whole_videos_never_straddle_the_split(self):
        names = self.frames(a=10, b=10, c=10, d=10, e=10)
        train, val = split_frames(names, val_fraction=0.2, seed=1)
        self.assertEqual(len(val), 10)
        self.assertFalse({video_of(n) for n in train} & {video_of(n) for n in val})
        self.assertEqual(sorted(train + val), sorted(names))

    def test_two_videos_gives_one_each(self):
        train, val = split_frames(self.frames(a=5, b=5), val_fraction=0.2)
        self.assertEqual(len({video_of(n) for n in val}), 1)
        self.assertEqual(len({video_of(n) for n in train}), 1)

    def test_one_video_validates_on_its_tail_with_a_gap(self):
        names = self.frames(solo=50)
        train, val = split_frames(names, val_fraction=0.2, gap=5)
        self.assertEqual(val, names[-10:])
        self.assertEqual(train, names[:35])
        self.assertEqual(max(train) < min(val), True)

    def test_deterministic_and_validates_input(self):
        names = self.frames(a=4, b=4, c=4)
        self.assertEqual(split_frames(names, seed=3), split_frames(list(reversed(names)), seed=3))
        with self.assertRaises(ValueError):
            split_frames(["a__000000.jpg"])


class DatasetTest(TempCase):
    def setUp(self):
        super().setUp()
        self.images = self.tmp / "frames"
        self.images.mkdir()
        for name in ("a__000000.jpg", "a__000030.jpg", "b__000000.jpg"):
            write_image(self.images / name)

    def build(self):
        builder = DatasetBuilder(self.tmp / "ds", CLASSES)
        builder.add("train", self.images / "a__000000.jpg", ["0 0.5 0.5 0.1 0.1", "1 0.2 0.2 0.1 0.1"])
        builder.add("train", self.images / "a__000030.jpg", [])
        builder.add("val", self.images / "b__000000.jpg", ["0 0.4 0.4 0.2 0.2"])
        return builder

    def test_layout_labels_and_empty_images(self):
        ds = self.build().root
        self.assertTrue((ds / "images" / "train" / "a__000000.jpg").exists())
        self.assertEqual((ds / "labels" / "train" / "a__000000.txt").read_text().splitlines(),
                         ["0 0.5 0.5 0.1 0.1", "1 0.2 0.2 0.1 0.1"])
        self.assertEqual((ds / "labels" / "train" / "a__000030.txt").read_text(), "")

    def test_yaml_and_summary(self):
        builder = self.build()
        import yaml
        data = yaml.safe_load(builder.write_yaml().read_text())
        self.assertEqual(data["names"], {0: "drone", 1: "airplane", 2: "bird"})
        self.assertEqual((data["train"], data["val"]), ("images/train", "images/val"))
        self.assertTrue(Path(data["path"]).is_dir())
        summary = builder.summary()
        self.assertEqual(summary["train"], {"images": 2, "empty": 1,
                                            "instances": {"drone": 1, "airplane": 1, "bird": 0}})
        self.assertEqual(summary["val"]["instances"]["drone"], 1)

    def test_rejects_duplicates_bad_splits_and_bad_class_ids(self):
        builder = self.build()
        with self.assertRaises(ValueError):
            builder.add("train", self.images / "a__000000.jpg", [])
        with self.assertRaises(ValueError):
            builder.add("test", self.images / "b__000000.jpg", [])
        with self.assertRaises(ValueError):
            builder.add("val", self.images / "a__000030.jpg", ["7 0.5 0.5 0.1 0.1"])

    def test_fresh_build_removes_leftovers(self):
        self.build()
        (self.tmp / "ds" / "images" / "train" / "stale.jpg").write_bytes(b"x")
        again = DatasetBuilder(self.tmp / "ds", CLASSES)
        self.assertEqual(again.summary()["train"]["images"], 0)

    def test_merges_an_existing_dataset_by_class_name(self):
        old = self.tmp / "old"
        for split in ("train", "valid"):
            (old / "images" / split).mkdir(parents=True)
            (old / "labels" / split).mkdir(parents=True)
        write_image(old / "images" / "train" / "p.jpg")
        (old / "labels" / "train" / "p.txt").write_text("1 0.5 0.5 0.2 0.2\n0 0.1 0.1 0.1 0.1\n")   # plane, car
        write_image(old / "images" / "valid" / "q.jpg")                                            # no label file
        builder = DatasetBuilder(self.tmp / "ds", CLASSES)
        added, dropped = builder.add_existing(old, ["car", "airplane"])
        self.assertEqual((added, dropped), (2, 1))
        self.assertEqual((builder.root / "labels" / "train" / "ext__train-p.txt").read_text(),
                         "1 0.5 0.5 0.2 0.2\n")
        self.assertTrue((builder.root / "images" / "val" / "ext__valid-q.jpg").exists())

    def test_warnings(self):
        text = " ".join(dataset_warnings(self.build().summary()))
        self.assertIn("Only 1 validation images", text)
        self.assertIn("No 'bird' boxes in training", text)
        self.assertIn("Only 1 'drone' boxes in training", text)
        self.assertIn("No 'airplane' boxes in validation", text)
        self.assertEqual(dataset_warnings({"train": {"images": 0, "instances": {}},
                                           "val": {"images": 99, "instances": {}}}),
                         ["There are no training images."])


class PreviewTest(TempCase):
    def test_preview_and_contact_sheet(self):
        image = self.tmp / "x.jpg"
        write_image(image, size=(640, 480))
        one = draw_preview(image, ["0 0.5 0.5 0.2 0.2"], CLASSES, cell_width=200, caption="#1")
        self.assertEqual(one.shape, (150, 200, 3))
        self.assertGreater(int(one.max()), 90)              # a box and caption were drawn
        two = draw_preview(image, [], CLASSES, cell_width=100)
        sheet = make_contact_sheet([one, two, one], columns=2)
        self.assertEqual(sheet.shape, (300, 400, 3))
        with self.assertRaises(ValueError):
            make_contact_sheet([])


if __name__ == "__main__":
    unittest.main()
