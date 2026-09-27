"""Find objects in a camera frame with a YOLO model exported to ONNX.

Works with Ultralytics detection models (YOLOv8, YOLO11, YOLO26) exported by
`yolo export format=onnx`, whether that's the pretrained COCO model or your own.
The class names are stored inside the .onnx file, so swapping models needs no
code change.
"""
import ast
from dataclasses import dataclass

import cv2
import numpy as np
import onnxruntime as ort


@dataclass
class Detection:
    class_id: int
    class_name: str
    confidence: float                          # 0..1
    box: tuple[float, float, float, float]     # x1, y1, x2, y2 in frame pixels

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.box
        return (x1 + x2) / 2, (y1 + y2) / 2


class Detector:
    def __init__(self, model_path, min_confidence=0.35, iou_threshold=0.45):
        self.session = ort.InferenceSession(str(model_path),
                                            providers=ort.get_available_providers())
        model_input = self.session.get_inputs()[0]
        self.input_name = model_input.name
        # Input shape is [batch, channels, height, width], e.g. [1, 3, 640, 640].
        # Models exported with dynamic=True have names instead of numbers: use 640.
        _, _, height, width = model_input.shape
        self.input_size = (width if isinstance(width, int) else 640,
                           height if isinstance(height, int) else 640)
        self.class_names = read_class_names(self.session)
        self.min_confidence = min_confidence
        self.iou_threshold = iou_threshold

    def detect(self, frame):
        """Return every Detection in a BGR frame (as OpenCV delivers it), best first."""
        blob, scale, (pad_x, pad_y) = self.prepare(frame)
        output = self.session.run(None, {self.input_name: blob})[0][0]   # [0]: drop batch
        boxes, scores, class_ids = self.decode(output)

        # Undo the letterbox: model-input pixels -> original frame pixels
        boxes = (boxes - [pad_x, pad_y, pad_x, pad_y]) / scale
        height, width = frame.shape[:2]
        boxes = boxes.clip(0, [width, height, width, height])

        return [Detection(int(c), self.name_of(int(c)), float(s), tuple(float(v) for v in b))
                for b, s, c in zip(boxes, scores, class_ids)]

    def prepare(self, frame):
        """Letterbox the frame to the model's input size and turn it into a float tensor.

        Letterboxing = shrink to fit while keeping the aspect ratio, then pad the
        leftover space with gray. It's how YOLO models see images in training.
        """
        in_w, in_h = self.input_size
        height, width = frame.shape[:2]
        scale = min(in_w / width, in_h / height)
        new_w, new_h = round(width * scale), round(height * scale)
        pad_x, pad_y = (in_w - new_w) // 2, (in_h - new_h) // 2

        canvas = np.full((in_h, in_w, 3), 114, dtype=np.uint8)
        canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = cv2.resize(
            frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # BGR -> RGB, (height, width, channel) -> (channel, height, width),
        # 0..255 -> 0..1, then add the batch dimension in front.
        blob = canvas[:, :, ::-1].transpose(2, 0, 1)[np.newaxis].astype(np.float32) / 255.0
        return np.ascontiguousarray(blob), scale, (pad_x, pad_y)

    def decode(self, output):
        """Raw model output -> (boxes as x1 y1 x2 y2, scores, class_ids), best first."""
        if output.shape[-1] == 6:
            # Exported with nms=True: rows are finished boxes
            # [x1, y1, x2, y2, score, class_id], already de-duplicated.
            rows = output[output[:, 4] >= self.min_confidence]
            rows = rows[rows[:, 4].argsort()[::-1]]
            return rows[:, :4], rows[:, 4], rows[:, 5].astype(int)

        # Standard export, shape (4 + classes, candidates), e.g. (84, 8400):
        # each column is one candidate box [cx, cy, w, h, score_class0, score_class1, ...]
        candidates = output.T
        class_scores = candidates[:, 4:]
        class_ids = class_scores.argmax(axis=1)                  # best class per box
        scores = class_scores[np.arange(len(class_ids)), class_ids]
        keep = scores >= self.min_confidence
        cx, cy, w, h = candidates[keep, :4].T
        boxes = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1)
        scores, class_ids = scores[keep], class_ids[keep]

        best = nms(boxes, scores, class_ids, self.iou_threshold)
        return boxes[best], scores[best], class_ids[best]

    def name_of(self, class_id):
        if class_id < len(self.class_names):
            return self.class_names[class_id]
        return f"class{class_id}"


def read_class_names(session):
    """Class names Ultralytics stores in the model file, as a list indexed by class id."""
    raw = session.get_modelmeta().custom_metadata_map.get("names")
    if not raw:
        return []                                  # name_of() falls back to "class3" etc.
    names = ast.literal_eval(raw)    # "{0: 'person', ...}" -> dict; parses data, never runs code
    return [names[i] for i in sorted(names)]


def nms(boxes, scores, class_ids, iou_threshold):
    """Non-maximum suppression: where boxes of the same class overlap, keep only the best.

    YOLO proposes several slightly different boxes around each object; this
    keeps one per object. Returns the indices to keep, highest score first.
    """
    # Shift each class's boxes far apart, so boxes of different classes never
    # overlap and a plane can't suppress a bird sitting in front of it.
    shifted = boxes + class_ids[:, None] * 10_000.0
    order = scores.argsort()[::-1]
    keep = []
    while order.size:
        best, rest = order[0], order[1:]
        keep.append(best)
        order = rest[iou(shifted[best], shifted[rest]) < iou_threshold]
    return np.array(keep, dtype=int)


def iou(box, boxes):
    """Intersection over union of one box with many: 0 = no overlap, 1 = identical."""
    x1 = np.maximum(box[0], boxes[:, 0])
    y1 = np.maximum(box[1], boxes[:, 1])
    x2 = np.minimum(box[2], boxes[:, 2])
    y2 = np.minimum(box[3], boxes[:, 3])
    overlap = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area = (box[2] - box[0]) * (box[3] - box[1])
    areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    return overlap / (area + areas - overlap + 1e-9)
