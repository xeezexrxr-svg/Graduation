"""Object detections: box maths, the closest-object rule, and merging the two detectors.

A detection is a dict: {"label": str, "confidence": float, "coordinates": [x1, y1, x2, y2]}.
The phone site applies the same rules in phone-web/public/detector.js.
"""
from .config import APP_DIR, YOLO26_MODEL_FILE
from .deps import YOLO

PEOPLE_LABELS = {"person", "people", "hand"}
# Clothes and accessories: when they sit on a person, they aren't what the user
# is pointing the camera at.
WORN_ITEMS = {
    "glasses", "sunglasses", "hat", "cap", "headphones", "earphones", "shirt", "jacket",
    "shoes", "shoe", "sock", "belt", "watch", "ring", "necklace", "face mask",
}
# YOLO26's names, written the way vocabulary.txt writes them.
COCO_TO_EVERYDAY = {
    "mouse": "computer mouse",
    "remote": "remote control",
    "couch": "sofa",
    "dining table": "table",
    "donut": "doughnut",
    "sports ball": "ball",
    "hair drier": "hair dryer",
}
SAME_OBJECT_IOU = 0.45


def plain_label(detection):
    return detection["label"].strip().lower().replace("_", " ")


def is_person(detection):
    return plain_label(detection) in PEOPLE_LABELS


def area(box):
    return max(0, box[2] - box[0]) * max(0, box[3] - box[1])


def box_area(detection):
    return area(detection["coordinates"])


def intersection(first, second):
    width = max(0, min(first[2], second[2]) - max(first[0], second[0]))
    height = max(0, min(first[3], second[3]) - max(first[1], second[1]))
    return width * height


def box_iou(first, second):
    shared = intersection(first, second)
    union = area(first) + area(second) - shared
    return shared / union if union > 0 else 0.0


def read_detections(result, offset=(0, 0)):
    """Turn an Ultralytics result into detection dicts (shifted by offset for crops)."""
    if result.boxes is None:
        return []
    offset_x, offset_y = offset
    detections = []
    for index in range(len(result.boxes)):
        x1, y1, x2, y2 = result.boxes.xyxy[index].tolist()
        class_id = int(result.boxes.cls[index].item())
        detections.append({
            "label": str(result.names.get(class_id, "object")),
            "confidence": float(result.boxes.conf[index].item()),
            "coordinates": [x1 + offset_x, y1 + offset_y, x2 + offset_x, y2 + offset_y],
        })
    return detections


def merge_with_coco(everyday, coco, coco_names):
    """Combine the everyday-object model's detections with YOLO26's.

    YOLO26 knows only 80 object types but is more reliable on them, so when both
    find the same object, YOLO26's name wins if the everyday model also thought it
    was one of YOLO26's types (a mouse seen from above called a cell phone gets
    corrected). Objects YOLO26 doesn't know (wallet, keys) keep their name. And
    when the everyday model alone reports one of YOLO26's own types where YOLO26
    saw nothing, that guess is dropped: on the COCO benchmark those were mostly
    wrong (evaluation/coco-results.md).
    """
    known_to_coco = {COCO_TO_EVERYDAY.get(name, name) for name in coco_names}
    merged = [dict(detection, source="everyday") for detection in everyday]
    for detection in coco:
        label = COCO_TO_EVERYDAY.get(detection["label"], detection["label"])
        match = max(
            merged,
            key=lambda candidate: box_iou(candidate["coordinates"], detection["coordinates"]),
            default=None,
        )
        if match and box_iou(match["coordinates"], detection["coordinates"]) >= SAME_OBJECT_IOU:
            if match["label"] in known_to_coco and (
                match["source"] == "everyday" or detection["confidence"] > match["confidence"]
            ):
                match.update(label=label, confidence=detection["confidence"], source="coco")
        else:
            merged.append(dict(detection, label=label, source="coco"))
    return [d for d in merged if d["source"] == "coco" or d["label"] not in known_to_coco]


def drop_worn_items(detections):
    """Remove clothes and accessories that sit on a person in the photo.

    People point the camera at an object, not at someone's hat, so a worn item
    shouldn't become the closest object just because its box is big (a skier's
    hat beat the skis in testing). Returns the list unchanged if that would leave
    no objects at all.
    """
    people = [d for d in detections if is_person(d)]
    if not people:
        return detections

    def on_a_person(item):
        item_area = box_area(item)
        return item_area > 0 and any(
            intersection(item["coordinates"], person["coordinates"]) / item_area >= 0.5
            for person in people
        )

    kept = [d for d in detections if not (plain_label(d) in WORN_ITEMS and on_a_person(d))]
    if any(not is_person(d) for d in kept):
        return kept
    return detections


def _touching(first, second):
    """True when the boxes overlap by at least 10% of the smaller box."""
    smaller = min(box_area(first), box_area(second))
    return smaller > 0 and intersection(first["coordinates"], second["coordinates"]) / smaller >= 0.1


def select_closest(detections):
    """Pick the object the user is most likely pointing at.

    Worn items on people are ignored. If someone is holding something, that wins;
    otherwise something worn (such as glasses) never beats an object touching it.
    Among what's left, the largest box is the best proxy for the closest object.
    """
    if not detections:
        return None
    detections = drop_worn_items(detections)
    objects = [d for d in detections if not is_person(d)]
    not_worn = [d for d in objects if plain_label(d) not in WORN_ITEMS]
    people = [d for d in detections if is_person(d)]

    if not_worn and people:
        held = [d for d in not_worn if any(_touching(d, person) for person in people)]
        if held:
            objects = held
    elif not_worn:
        worn = [d for d in objects if plain_label(d) in WORN_ITEMS]
        touching_worn = [d for d in not_worn if any(_touching(d, item) for item in worn)]
        if touching_worn:
            objects = touching_worn

    return max(objects or detections, key=box_area)


def list_labels(detections):
    """Every distinct object name, biggest first, without people."""
    labels = []
    for detection in sorted(detections, key=box_area, reverse=True):
        label = plain_label(detection)
        if label not in PEOPLE_LABELS and label not in labels:
            labels.append(label)
    return labels


def load_coco_model():
    """YOLO26 for the combined detector, or None if it can't be loaded."""
    if YOLO is None:
        return None
    try:
        local = APP_DIR / YOLO26_MODEL_FILE
        return YOLO(str(local) if local.exists() else YOLO26_MODEL_FILE)
    except Exception:
        return None
