"""File paths, detector names and thresholds shared across the app."""
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
# One descriptions file for both apps; the phone site serves it from here.
DESCRIPTIONS_FILE = APP_DIR / "phone-web" / "public" / "object_descriptions.json"
SETTINGS_FILE = APP_DIR / "settings.json"

YOLO_WORLD_MODEL_FILE = "yolov8s-worldv2.pt"
YOLO26_MODEL_FILE = "yolo26n.pt"
# Built from vocabulary.txt by build_detector.py; the phone uses the same list.
CLEARVIEW_MODEL_FILE = "clearview-detector.pt"

DETECTOR_CLEARVIEW = "clearview"
DETECTOR_YOLO26 = "yolo26"
DETECTOR_YOLO_WORLD = "yolo-world"
DETECTOR_NAMES = {
    DETECTOR_CLEARVIEW: "the everyday-object detector",
    DETECTOR_YOLO26: "YOLO26",
    DETECTOR_YOLO_WORLD: "the YOLO-World backup",
}

MIN_CONFIDENCE = 0.30
# The open-vocabulary detector makes more weak guesses, so it needs a higher bar.
DETECTOR_CONFIDENCE = {
    DETECTOR_CLEARVIEW: 0.40,
    DETECTOR_YOLO26: MIN_CONFIDENCE,
    DETECTOR_YOLO_WORLD: MIN_CONFIDENCE,
}
# Below this detector confidence, and with no cloud description, the result is
# worded as a guess ("This might be a …").
UNSURE_BELOW = 0.6

CLOUD_VISION_API_URL = "https://graduation-6j1.pages.dev/api/identify"
PREVIEW_SIZE = (800, 480)
