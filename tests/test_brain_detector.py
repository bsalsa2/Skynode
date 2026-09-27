"""Tests for brain/detector.py, using tiny hand-made ONNX "models".

Each fake model ignores the image and always outputs the same numbers, so we
know exactly which boxes the detector should report and where they should
land after undoing the letterbox. Needs numpy, opencv, onnxruntime, and onnx
(onnx is only for building the fakes: pip install onnx).
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

NEEDED = ("numpy", "cv2", "onnxruntime", "onnx")
if not all(importlib.util.find_spec(name) for name in NEEDED):
    raise unittest.SkipTest("needs " + ", ".join(NEEDED))

import numpy as np                                    # noqa: E402
import onnx                                           # noqa: E402
from onnx import TensorProto, helper, numpy_helper    # noqa: E402

from brain.detector import Detector, nms              # noqa: E402

NAMES = {0: "airplane", 1: "bird", 2: "car"}


def fake_model(folder, output, names=NAMES, size=64):
    """Write an ONNX model with a size x size input that always returns `output`."""
    image = helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, size, size])
    result = helper.make_tensor_value_info("output0", TensorProto.FLOAT, list(output.shape))
    constant = helper.make_node("Constant", [], ["output0"],
                                value=numpy_helper.from_array(output.astype(np.float32)))
    graph = helper.make_graph([constant], "fake_yolo", [image], [result])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8
    if names is not None:
        helper.set_model_props(model, {"names": repr(names)})
    path = Path(folder) / "fake.onnx"
    onnx.save(model, path)
    return path


def raw_output(candidates):
    """Build a standard (1, 4 + classes, N) output from (cx, cy, w, h, class_id, score) rows."""
    out = np.zeros((1, 4 + len(NAMES), len(candidates)), dtype=np.float32)
    for i, (cx, cy, w, h, class_id, score) in enumerate(candidates):
        out[0, :4, i] = [cx, cy, w, h]
        out[0, 4 + class_id, i] = score
    return out


class DetectorTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = tmp.name
        # A 128 x 64 frame shrinks by 0.5 into the 64 x 64 input, leaving 16 px of gray above and below.
        self.frame = np.zeros((64, 128, 3), dtype=np.uint8)

    def test_raw_output_scores_nms_and_letterbox(self):
        path = fake_model(self.folder, raw_output([
            (32, 32, 10, 8, 0, 0.9),    # airplane
            (33, 32, 10, 8, 0, 0.8),    # same airplane, slightly shifted: NMS removes it
            (32, 32, 10, 8, 1, 0.7),    # bird in the same spot: different class, kept
            (10, 40, 4, 4, 2, 0.1),     # car below min_confidence: dropped
        ]))
        detector = Detector(path, min_confidence=0.35, iou_threshold=0.45)
        self.assertEqual(detector.input_size, (64, 64))
        self.assertEqual(detector.class_names, ["airplane", "bird", "car"])

        found = detector.detect(self.frame)
        self.assertEqual([(d.class_name, round(d.confidence, 2)) for d in found],
                         [("airplane", 0.9), ("bird", 0.7)])
        # model box x 27..37, y 28..36 -> minus padding (0, 16) -> divided by 0.5
        np.testing.assert_allclose(found[0].box, (54, 24, 74, 40))
        self.assertEqual(found[0].center, (64, 32))

    def test_boxes_are_clipped_to_the_frame(self):
        path = fake_model(self.folder, raw_output([(2, 20, 10, 10, 0, 0.9)]))
        box = Detector(path).detect(self.frame)[0].box
        self.assertEqual(box[0], 0)                  # would be negative without clipping

    def test_nms_export_format(self):
        output = np.array([[[27, 28, 37, 36, 0.2, 1],    # below min_confidence
                            [27, 28, 37, 36, 0.9, 0],
                            [0, 0, 0, 0, 0.0, 0]]], dtype=np.float32)   # padding row
        found = Detector(fake_model(self.folder, output)).detect(self.frame)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].class_name, "airplane")
        np.testing.assert_allclose(found[0].box, (54, 24, 74, 40))

    def test_model_without_names_gets_numbered_classes(self):
        path = fake_model(self.folder, raw_output([(32, 32, 10, 8, 2, 0.9)]), names=None)
        self.assertEqual(Detector(path).detect(self.frame)[0].class_name, "class2")

    def test_nothing_found(self):
        path = fake_model(self.folder, raw_output([(32, 32, 10, 8, 0, 0.1)]))
        self.assertEqual(Detector(path).detect(self.frame), [])


class NmsTest(unittest.TestCase):
    def test_keeps_best_of_overlapping_same_class(self):
        boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], dtype=float)
        scores = np.array([0.8, 0.9, 0.5])
        keep = nms(boxes, scores, np.array([0, 0, 0]), iou_threshold=0.45)
        self.assertEqual(keep.tolist(), [1, 2])


if __name__ == "__main__":
    unittest.main()
