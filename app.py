"""Accessible camera assistant: identify common objects and describe them aloud."""

from __future__ import annotations

import json
import queue
import re
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

try:
    import comtypes
    from comtypes.client import CreateObject
except ImportError:
    comtypes = None
    CreateObject = None

try:
    from ultralytics import YOLO, YOLOWorld
except ImportError:
    YOLO = None
    YOLOWorld = None


APP_DIR = Path(__file__).resolve().parent
DESCRIPTIONS_FILE = APP_DIR / "object_descriptions.json"
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
CLOUD_VISION_API_URL = "https://graduation-6j1.pages.dev/api/identify"
MIN_CONFIDENCE = 0.30
# The open-vocabulary detector makes more weak guesses, so it needs a higher bar.
DETECTOR_CONFIDENCE = {
    DETECTOR_CLEARVIEW: 0.40,
    DETECTOR_YOLO26: MIN_CONFIDENCE,
    DETECTOR_YOLO_WORLD: MIN_CONFIDENCE,
}
PREVIEW_SIZE = (800, 480)

DEFAULT_DESCRIPTIONS = {
    "bottle": "It can hold drinks, such as water.",
    "cup": "It is used for drinking hot or cold drinks.",
    "plate": "It is used to hold and serve food.",
    "book": "It contains pages that people can read to learn or enjoy a story.",
    "toothbrush": "It is used with toothpaste to clean teeth.",
    "toothpaste": "It is put on a toothbrush to help clean teeth.",
    "cell phone": "It can be used to call or message people.",
    "spoon": "It helps people eat or serve food.",
    "fork": "It helps people pick up and eat food.",
    "knife": "It is used to cut food. Handle it carefully.",
    "chair": "It is used for sitting.",
    "dining table": "It is a flat surface where people can eat or work.",
    "mouse": "It helps control a pointer on a computer screen.",
    "keyboard": "It is used to type letters and numbers into a computer.",
    "laptop": "It is a portable computer for work, learning, and communication.",
    "tv": "It can show programs, films, and other videos.",
    "clock": "It shows the time.",
    "backpack": "It is used to carry items on your back.",
    "handbag": "It is used to carry personal items.",
    "umbrella": "It helps protect people from rain or strong sun.",
    "bicycle": "It is a vehicle people pedal to travel.",
    "bus": "It carries people from one place to another.",
    "scissors": "They are used to cut paper and other materials. Handle them carefully.",
    "remote": "It is used to control a device from a short distance.",
    "refrigerator": "It keeps food and drinks cold.",
    "microwave": "It heats food.",
    "toilet": "It is used for going to the bathroom.",
    "sink": "It is used for washing hands, dishes, or other items.",
    "person": "A person is someone you can talk with or ask for help.",
    "hand": "It is the part of the body at the end of an arm, used to hold and touch things.",
    "pen": "It is a writing tool that uses ink to make marks on paper.",
    "apple": "It is a crisp fruit that people can eat as a snack or add to a meal.",
    "banana": "It is a soft, sweet fruit with a yellow peel.",
    "orange": "It is a round citrus fruit with a juicy inside.",
    "lemon": "It is a sour citrus fruit used in drinks and cooking.",
    "grapes": "They are small, juicy fruits that grow in bunches.",
    "strawberry": "It is a sweet red fruit often eaten fresh or in desserts.",
    "blueberry": "It is a small blue fruit often added to cereal or desserts.",
    "watermelon": "It is a large fruit with a juicy red or pink inside.",
    "pineapple": "It is a sweet tropical fruit with a spiky outer skin.",
    "mango": "It is a sweet tropical fruit with soft orange flesh.",
    "pear": "It is a sweet fruit that is wider at the bottom.",
    "peach": "It is a soft, juicy fruit with fuzzy skin.",
    "tomato": "It is a soft red fruit often used in salads and cooking.",
    "potato": "It is a starchy vegetable that can be baked, boiled, or fried.",
    "onion": "It is a vegetable used to add flavor to many meals.",
    "carrot": "It is a crunchy orange vegetable.",
    "broccoli": "It is a green vegetable with a thick stem and small florets.",
    "lettuce": "It is a leafy green vegetable often used in salads.",
    "cucumber": "It is a long, crisp vegetable often eaten fresh.",
    "bell pepper": "It is a crisp vegetable that can be green, red, yellow, or orange.",
    "corn": "It is a yellow grain that can be eaten from a cob or added to meals.",
    "avocado": "It is a soft green fruit often spread on bread or added to salads.",
    "bread": "It is a baked food often used for sandwiches or toast.",
    "rice": "It is a small grain commonly served as part of a meal.",
    "pasta": "It is a flour-based food cooked in water and often served with sauce.",
    "pizza": "It is a baked flatbread often topped with cheese and other ingredients.",
    "sandwich": "It is a meal made with filling between slices of bread.",
    "egg": "It is a food that can be boiled, fried, or used in cooking.",
    "cheese": "It is a dairy food often added to meals or sandwiches.",
    "milk": "It is a drink that can also be used in cooking and cereal.",
    "yogurt": "It is a soft dairy food that can be eaten plain or with fruit.",
    "butter": "It is a dairy spread used on bread and in cooking.",
    "cereal": "It is a grain-based breakfast food often eaten with milk.",
    "soup": "It is a warm, liquid meal made with ingredients such as vegetables or meat.",
    "salad": "It is a meal or side dish often made with fresh vegetables.",
    "chicken": "It is poultry meat that is commonly cooked for meals.",
    "beef": "It is meat from cattle used in many cooked dishes.",
    "pork": "It is meat from a pig used in many cooked dishes.",
    "fish": "It is aquatic animal meat that people cook and eat.",
    "salmon": "It is a pink-fleshed fish commonly cooked for meals.",
    "shrimp": "It is a small seafood often cooked and served in meals.",
    "sausage": "It is seasoned meat packed into a casing.",
    "bacon": "It is thin, salted pork that is often fried.",
    "steak": "It is a cut of meat, commonly beef, cooked as a meal.",
    "turkey": "It is poultry meat often served roasted or in sandwiches.",
    "ham": "It is salted or cooked pork often served in sandwiches or meals.",
    "beans": "They are small edible seeds used in soups, salads, and other meals.",
    "cookie": "It is a small sweet baked snack.",
    "cake": "It is a sweet baked dessert often served at celebrations.",
    "doughnut": "It is a sweet fried or baked ring-shaped treat.",
    "hamburger": "It is a cooked patty often served in a bun.",
    "hot dog": "It is a cooked sausage often served in a long bun.",
    "french fries": "They are strips of potato that are usually fried.",
    "pancake": "It is a flat, round breakfast food cooked on a hot surface.",
    "cupcake": "It is a small individual cake, often topped with frosting.",
    "chocolate": "It is a sweet food made from cacao and used in snacks or desserts.",
    "ice cream": "It is a frozen dairy dessert served cold.",
    "peanut butter": "It is a spread made from ground peanuts.",
    "mushroom": "It is an edible fungus used in many cooked meals.",
    "garlic": "It is a strongly flavored bulb used to season food.",
    "wallet": "It is a small case used to carry money and cards.",
    "keys": "They are small metal objects used to lock or unlock things.",
    "glasses": "They help people see more clearly when worn in front of the eyes.",
    "shoes": "They protect the feet and are worn for walking.",
    "shirt": "It is a piece of clothing worn on the upper body.",
    "hat": "It is worn on the head for warmth, shade, or style.",
    "pillow": "It is a soft cushion used to support the head while resting.",
    "towel": "It is used to dry the body or other items.",
    "soap": "It is used with water to clean hands or the body.",
    "headphones": "They are worn over or in the ears to listen to sound.",
}

def _mix(first, second, amount):
    """Blend two #rrggbb colours; amount 0 keeps first, 1 gives second."""
    channels = [
        round(int(first[i:i + 2], 16) * (1 - amount) + int(second[i:i + 2], 16) * amount)
        for i in (1, 3, 5)
    ]
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def _reading_palette(ground, paper, raised, line, ink, muted, dark=False):
    """Build a full palette from one reading tint, matching the phone app.

    Soft tinted backgrounds and dark grey (never pure black) text follow
    dyslexia style guidance. Every value must be unique, because theme
    switching recolours widgets by mapping old colour values to new ones.
    """
    if dark:
        accent, accent_hover, on_accent = "#8fb8f2", "#a9c9f6", "#10233f"
        success, warning, error = "#8fe3b0", "#ffc27a", "#ff9c8f"
    else:
        accent, accent_hover, on_accent = "#1f4f8f", "#173d70", "#ffffff"
        success, warning, error = "#1e6b3a", "#8a5300", "#a3261b"
    palette = {
        "background": ground,
        "panel": paper,
        "reading_panel": _mix(paper, ground, 0.3),
        "preview": raised,
        "control": _mix(raised, line, 0.3),
        "status_panel": _mix(ground, raised, 0.5),
        "border": line,
        "trough": _mix(line, raised, 0.5),
        "text": ink,
        "muted": muted,
        "accent": accent,
        "accent_hover": accent_hover,
        "button_text": on_accent,
        "selection_sentence": _mix(paper, accent, 0.16),
        "selection_word": _mix(accent, ink, 0.06),
        "success": success,
        "warning": warning,
        "error": error,
    }
    assert len(set(palette.values())) == len(palette), "palette colours must be unique"
    return palette


APP_COLOR_PRESETS = {
    "Cream": _reading_palette("#faf6ec", "#fffcf4", "#f1ead8", "#d9cfb8", "#2b2a28", "#5c584f"),
    "Yellow": _reading_palette("#fcf5c7", "#fffadb", "#f3e9ae", "#dccf8a", "#2b2a26", "#5b5640"),
    "Blue": _reading_palette("#e3eef8", "#f1f6fc", "#d2e2f1", "#b3c8dd", "#24292f", "#4d5a68"),
    "Mint": _reading_palette("#e6f2e4", "#f2f8f0", "#d5e8d2", "#b6cfb2", "#263026", "#4e5c4c"),
    "Peach": _reading_palette("#fcebdd", "#fff5ec", "#f4dcc8", "#dfc2a9", "#2e2925", "#62554a"),
    "Dark": _reading_palette(
        "#1e2227", "#2a3038", "#282d34", "#3a414b", "#e8e4d9", "#b0b4ba", dark=True
    ),
}
DEFAULT_APP_COLOR = "Cream"
PALETTE = dict(APP_COLOR_PRESETS[DEFAULT_APP_COLOR])

# Interface font; upgraded at start-up if a dyslexia-friendly face is installed.
UI_FONT = "Segoe UI"
PREFERRED_UI_FONTS = ("Atkinson Hyperlegible Next", "Atkinson Hyperlegible", "Segoe UI")


SETTINGS_FILE = APP_DIR / "settings.json"
# Tk variables on the app that are remembered between runs.
SAVED_SETTINGS = (
    "app_color_choice",
    "font_family",
    "font_size",
    "bold_reading_text",
    "letter_spacing",
    "line_spacing",
    "speech_rate",
    "volume",
    "voice_name",
    "auto_speak",
    "detector_choice",
    "brightness",
)


def load_settings(path=None):
    """Read saved preferences; a missing or damaged file just means defaults."""
    try:
        with (path or SETTINGS_FILE).open("r", encoding="utf-8") as settings_file:
            loaded = json.load(settings_file)
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def save_settings(settings, path=None):
    try:
        with (path or SETTINGS_FILE).open("w", encoding="utf-8") as settings_file:
            json.dump(settings, settings_file, indent=2, ensure_ascii=False)
    except OSError:
        pass  # Not being able to save preferences must never block closing the app.


CHINESE_CHARACTER = re.compile(r"[㐀-鿿豈-﫿]")
LATIN_LETTER = re.compile(r"[A-Za-z]")
# SAPI voice "Language" attributes are hex LCIDs: zh-TW first, then HK, CN, SG, MO.
CHINESE_LANGUAGE_IDS = ("404", "c04", "804", "1004", "1404")


def is_mostly_chinese(text):
    """True when Chinese characters dominate, so an English voice would garble it."""
    chinese = len(CHINESE_CHARACTER.findall(text))
    latin = len(LATIN_LETTER.findall(text))
    return chinese > 0 and chinese * 3 >= latin


def find_chinese_sapi_voice(voices):
    """Return the best installed Chinese SAPI voice (Traditional first), or None."""
    by_language = {}
    for index in range(voices.Count):
        voice = voices.Item(index)
        try:
            languages = str(voice.GetAttribute("Language")).lower().split(";")
        except Exception:
            continue
        for language_id in CHINESE_LANGUAGE_IDS:
            if language_id in languages:
                by_language.setdefault(language_id, voice)
    for language_id in CHINESE_LANGUAGE_IDS:
        if language_id in by_language:
            return by_language[language_id]
    return None


def load_descriptions():
    """Load the editable object explanations, or provide useful defaults."""
    if not DESCRIPTIONS_FILE.exists():
        return dict(DEFAULT_DESCRIPTIONS), ""

    try:
        with DESCRIPTIONS_FILE.open("r", encoding="utf-8") as description_file:
            loaded = json.load(description_file)
    except (OSError, json.JSONDecodeError) as error:
        return dict(DEFAULT_DESCRIPTIONS), (
            f"Could not read {DESCRIPTIONS_FILE.name}: {error}. Using built-in descriptions."
        )

    if not isinstance(loaded, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in loaded.items()
    ):
        return dict(DEFAULT_DESCRIPTIONS), (
            f"{DESCRIPTIONS_FILE.name} must contain object names and description text. "
            "Using built-in descriptions."
        )

    descriptions = {key.strip().lower(): value.strip() for key, value in loaded.items()}
    descriptions = {key: value for key, value in descriptions.items() if key and value}
    return descriptions, ""


class CameraWorker(threading.Thread):
    """Capture frames away from Tk's UI thread."""

    def __init__(self, camera_index=0):
        super().__init__(daemon=True, name="camera-worker")
        self.camera_index = camera_index
        self.stop_event = threading.Event()
        self.frame_lock = threading.Lock()
        self.latest_frame = None
        self.events = queue.Queue()

    def get_frame(self):
        with self.frame_lock:
            if self.latest_frame is None:
                return None
            return self.latest_frame.copy()

    def stop(self):
        self.stop_event.set()

    def run(self):
        if cv2 is None:
            self.events.put(("error", "OpenCV is not installed. Install the requirements first."))
            return

        try:
            capture = cv2.VideoCapture(self.camera_index)
        except Exception as error:
            self.events.put(("error", f"Could not open the camera: {error}"))
            return
        if not capture.isOpened():
            capture.release()
            self.events.put(("error", "Camera unavailable. Check its connection and permissions."))
            return

        try:
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.events.put(("ready", "Camera ready. Point it at one object, then choose Identify object."))

            while not self.stop_event.is_set():
                success, frame = capture.read()
                if not success:
                    self.events.put(("error", "The camera stopped sending video frames."))
                    time.sleep(0.2)
                    continue

                with self.frame_lock:
                    self.latest_frame = frame
                time.sleep(0.02)
        except Exception as error:
            self.events.put(("error", f"Camera error: {error}"))
        finally:
            capture.release()


class AnalysisWorker(threading.Thread):
    """Load YOLO once, then process requested frames off the UI thread."""

    HUMAN_LABELS = {"person", "people", "hand"}
    WEARABLE_LABELS = {
        "glasses", "sunglasses", "hat", "cap", "headphones", "earphones", "shirt",
        "jacket", "shoes", "shoe", "sock", "belt", "watch", "ring", "necklace", "face mask",
    }

    def __init__(self, candidate_names, detector_choice=DETECTOR_CLEARVIEW):
        super().__init__(daemon=True, name="analysis-worker")
        self.requests = queue.Queue()
        self.events = queue.Queue()
        self.candidate_names = candidate_names
        self.detector_choice = detector_choice

    def identify(self, frame):
        self.requests.put(("identify", frame))

    def switch_detector(self, detector_choice):
        self.requests.put(("switch_detector", detector_choice))

    def stop(self):
        self.requests.put(None)

    def _load_detector(self, detector_choice):
        if detector_choice == DETECTOR_CLEARVIEW:
            if YOLO is None:
                raise RuntimeError("Ultralytics YOLO is unavailable.")
            if not (APP_DIR / CLEARVIEW_MODEL_FILE).exists():
                raise FileNotFoundError(
                    f"{CLEARVIEW_MODEL_FILE} is missing. Run build_detector.py to create it."
                )
            model = YOLO(str(APP_DIR / CLEARVIEW_MODEL_FILE))
            return model, f"everyday objects, {len(model.names)} types"

        if detector_choice == DETECTOR_YOLO26:
            if YOLO is None:
                raise RuntimeError("Ultralytics YOLO is unavailable.")
            model = YOLO(YOLO26_MODEL_FILE)
            return model, f"YOLO26 ({YOLO26_MODEL_FILE})"

        if detector_choice == DETECTOR_YOLO_WORLD:
            if YOLOWorld is None:
                raise RuntimeError("Ultralytics YOLO-World is unavailable.")
            if not self.candidate_names:
                raise ValueError(
                    "Add at least one object name to object_descriptions.json."
                )
            model = YOLOWorld(YOLO_WORLD_MODEL_FILE)
            model.set_classes(self.candidate_names)
            return model, f"YOLO-World backup ({YOLO_WORLD_MODEL_FILE})"

        raise ValueError(f"Unknown detector selection: {detector_choice}")

    @classmethod
    def _select_detection(cls, detections):
        if not detections:
            return None
        object_detections = [
            detection
            for detection in detections
            if detection["label"].strip().lower().replace("_", " ")
            not in cls.HUMAN_LABELS
        ]
        non_wearables = [
            detection
            for detection in object_detections
            if detection["label"].strip().lower().replace("_", " ")
            not in cls.WEARABLE_LABELS
        ]
        human_detections = [
            detection
            for detection in detections
            if detection["label"].strip().lower().replace("_", " ")
            in cls.HUMAN_LABELS
        ]

        def overlaps(first, second):
            first_x1, first_y1, first_x2, first_y2 = first["coordinates"]
            second_x1, second_y1, second_x2, second_y2 = second["coordinates"]
            intersection_width = max(
                0, min(first_x2, second_x2) - max(first_x1, second_x1)
            )
            intersection_height = max(
                0, min(first_y2, second_y2) - max(first_y1, second_y1)
            )
            smaller_area = min(
                max(0, first_x2 - first_x1) * max(0, first_y2 - first_y1),
                max(0, second_x2 - second_x1) * max(0, second_y2 - second_y1),
            )
            return smaller_area > 0 and (
                intersection_width * intersection_height / smaller_area >= 0.1
            )

        if non_wearables and human_detections:
            held_objects = [
                detection
                for detection in non_wearables
                if any(overlaps(detection, person) for person in human_detections)
            ]
            if held_objects:
                object_detections = held_objects
        elif non_wearables:
            wearable_detections = [
                detection
                for detection in object_detections
                if detection["label"].strip().lower().replace("_", " ")
                in cls.WEARABLE_LABELS
            ]
            overlapping_objects = [
                detection
                for detection in non_wearables
                if any(overlaps(detection, wearable) for wearable in wearable_detections)
            ]
            if overlapping_objects:
                object_detections = overlapping_objects

        # The largest box is the best available proxy for the closest object.
        return max(object_detections or detections, key=cls._box_area)

    @staticmethod
    def _box_area(detection):
        x1, y1, x2, y2 = detection["coordinates"]
        return max(0, x2 - x1) * max(0, y2 - y1)

    @classmethod
    def _list_labels(cls, detections):
        labels = []
        for detection in sorted(detections, key=cls._box_area, reverse=True):
            label = detection["label"].strip().lower().replace("_", " ")
            if label not in cls.HUMAN_LABELS and label not in labels:
                labels.append(label)
        return labels

    @staticmethod
    def _read_detections(result, offset=(0, 0)):
        if result.boxes is None:
            return []
        detections = []
        offset_x, offset_y = offset
        for index in range(len(result.boxes)):
            confidence = float(result.boxes.conf[index].item())
            class_id = int(result.boxes.cls[index].item())
            label = str(result.names.get(class_id, "object"))
            x1, y1, x2, y2 = result.boxes.xyxy[index].tolist()
            detections.append({
                "label": label,
                "confidence": confidence,
                "coordinates": [
                    x1 + offset_x,
                    y1 + offset_y,
                    x2 + offset_x,
                    y2 + offset_y,
                ],
            })
        return detections

    @staticmethod
    def _get_cloud_details(frame, detection):
        frame_height, frame_width = frame.shape[:2]
        x1, y1, x2, y2 = detection["coordinates"]
        padding_x = max(12, int((x2 - x1) * 0.08))
        padding_y = max(12, int((y2 - y1) * 0.08))
        crop_x1 = max(0, int(x1) - padding_x)
        crop_y1 = max(0, int(y1) - padding_y)
        crop_x2 = min(frame_width, int(x2) + padding_x)
        crop_y2 = min(frame_height, int(y2) + padding_y)
        if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
            raise ValueError("The detected object crop is empty.")

        crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]
        crop_height, crop_width = crop.shape[:2]
        scale = min(1.0, 960 / max(crop_width, crop_height))
        if scale < 1:
            crop = cv2.resize(
                crop,
                (round(crop_width * scale), round(crop_height * scale)),
            )
        success, encoded = cv2.imencode(
            ".jpg",
            crop,
            [cv2.IMWRITE_JPEG_QUALITY, 78],
        )
        if not success:
            raise ValueError("Could not encode the detected object for cloud analysis.")

        request = urllib.request.Request(
            CLOUD_VISION_API_URL,
            data=encoded.tobytes(),
            headers={"Content-Type": "image/jpeg", "X-ClearView-Client": "desktop"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Cloud vision returned an invalid response.")
        if not payload.get("found"):
            raise ValueError("Cloud vision could not add details for this object.")
        return payload

    def run(self):
        model = None
        active_detector = None
        model_label = ""
        ocr_reader = None
        ocr_error = None
        self.events.put(("model_loading", self.detector_choice))
        try:
            model, model_label = self._load_detector(self.detector_choice)
            active_detector = self.detector_choice
        except Exception as error:
            self.events.put((
                "model_error",
                {
                    "message": f"Could not load the selected detector: {error}",
                    "active_detector": None,
                },
            ))

        self.events.put(("ocr_loading", None))
        try:
            import easyocr

            ocr_reader = easyocr.Reader(["en", "ch_tra"], gpu=False, verbose=False)
        except Exception as error:
            ocr_error = (
                "Text reading is unavailable. Install the project requirements "
                f"and restart the app. {error}"
            )

        if model is not None:
            self.events.put((
                "model_ready",
                {
                    "message": f"AI model ready ({model_label}).",
                    "ocr_error": ocr_error,
                    "detector": active_detector,
                },
            ))

        while True:
            request = self.requests.get()
            if request is None:
                return

            command, payload = request
            if command == "switch_detector":
                requested_detector = payload
                self.events.put(("model_loading", requested_detector))
                try:
                    replacement, replacement_label = self._load_detector(
                        requested_detector
                    )
                except Exception as error:
                    self.events.put((
                        "model_switch_error",
                        {
                            "message": (
                                f"Could not load the requested detector: {error}"
                            ),
                            "active_detector": active_detector,
                        },
                    ))
                    continue
                model = replacement
                model_label = replacement_label
                active_detector = requested_detector
                self.events.put((
                    "model_ready",
                    {
                        "message": f"AI model ready ({model_label}).",
                        "ocr_error": ocr_error,
                        "detector": active_detector,
                    },
                ))
                continue

            frame = payload
            if model is None:
                continue
            try:
                min_confidence = DETECTOR_CONFIDENCE.get(active_detector, MIN_CONFIDENCE)
                results = model.predict(frame, verbose=False, conf=min_confidence)
                if not results or results[0].boxes is None or len(results[0].boxes) == 0:
                    self.events.put(("not_found", None))
                    continue

                detections = self._read_detections(results[0])
                human_detections = [
                    detection
                    for detection in detections
                    if detection["label"].strip().lower().replace("_", " ")
                    in self.HUMAN_LABELS
                ]
                if human_detections:
                    hand_detections = [
                        detection
                        for detection in human_detections
                        if detection["label"].strip().lower().replace("_", " ") == "hand"
                    ]
                    context_detection = max(
                        hand_detections or human_detections,
                        key=lambda candidate: candidate["confidence"],
                    )
                    frame_height, frame_width = frame.shape[:2]
                    x1, y1, x2, y2 = context_detection["coordinates"]
                    padding_x = max(24, int((x2 - x1) * 0.15))
                    padding_y = max(24, int((y2 - y1) * 0.15))
                    crop_x1 = max(0, int(x1) - padding_x)
                    crop_y1 = max(0, int(y1) - padding_y)
                    crop_x2 = min(frame_width, int(x2) + padding_x)
                    crop_y2 = min(frame_height, int(y2) + padding_y)
                    if crop_x2 > crop_x1 and crop_y2 > crop_y1:
                        crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]
                        crop_results = model.predict(
                            crop,
                            verbose=False,
                            conf=min_confidence * 0.7,
                        )
                        if crop_results and crop_results[0].boxes is not None:
                            crop_detections = self._read_detections(
                                crop_results[0],
                                offset=(crop_x1, crop_y1),
                            )
                            detections.extend(crop_detections)
                detection = self._select_detection(detections)
                detection["all_labels"] = self._list_labels(detections)
                recognized_text = ""
                detection_ocr_error = ocr_error
                if ocr_reader is not None:
                    try:
                        frame_height, frame_width = frame.shape[:2]
                        x1, y1, x2, y2 = detection["coordinates"]
                        padding_x = max(12, int((x2 - x1) * 0.08))
                        padding_y = max(12, int((y2 - y1) * 0.08))
                        crop_x1 = max(0, int(x1) - padding_x)
                        crop_y1 = max(0, int(y1) - padding_y)
                        crop_x2 = min(frame_width, int(x2) + padding_x)
                        crop_y2 = min(frame_height, int(y2) + padding_y)
                        if crop_x2 > crop_x1 and crop_y2 > crop_y1:
                            text_results = ocr_reader.readtext(
                                frame[crop_y1:crop_y2, crop_x1:crop_x2],
                                detail=1,
                            )
                            text_parts = []
                            seen_text = set()
                            for text_result in text_results:
                                text = text_result[1].strip()
                                confidence = float(text_result[2])
                                normalized_text = text.casefold()
                                if (
                                    text
                                    and confidence >= 0.30
                                    and normalized_text not in seen_text
                                ):
                                    text_parts.append(text)
                                    seen_text.add(normalized_text)
                            recognized_text = " ".join(text_parts)[:240]
                        detection_ocr_error = None
                    except Exception as error:
                        detection_ocr_error = f"Text reading failed: {error}"
                detection["recognized_text"] = recognized_text
                detection["ocr_error"] = detection_ocr_error
                try:
                    cloud_details = self._get_cloud_details(frame, detection)
                    detection["cloud_description"] = cloud_details.get("description", "")
                    detection["cloud_product"] = cloud_details.get("product", "")
                    cloud_text = cloud_details.get("recognizedText", "")
                    if isinstance(cloud_text, str) and cloud_text.strip():
                        if recognized_text and cloud_text.strip().casefold() not in recognized_text.casefold():
                            recognized_text = f"{recognized_text} {cloud_text.strip()}"
                        elif not recognized_text:
                            recognized_text = cloud_text.strip()
                    detection["recognized_text"] = recognized_text[:240]
                    detection["cloud_error"] = None
                except (
                    OSError,
                    TimeoutError,
                    ValueError,
                    json.JSONDecodeError,
                    urllib.error.URLError,
                ) as error:
                    detection["cloud_description"] = ""
                    detection["cloud_product"] = ""
                    detection["cloud_error"] = str(error)
                self.events.put((
                    "found",
                    detection,
                ))
            except Exception as error:
                self.events.put(("analysis_error", str(error)))


class SpeechWorker(threading.Thread):
    """Own the TTS engine on one thread to keep speech and UI responsive."""

    def __init__(self):
        super().__init__(daemon=True, name="speech-worker")
        self.requests = queue.Queue()
        self.events = queue.Queue()

    def speak(self, text, rate, voice_name=None, volume=100, request_id=0):
        self.requests.put(("speak", (text, rate, voice_name, volume, request_id)))

    def set_volume(self, volume):
        self.requests.put(("volume", int(volume)))

    def set_rate(self, rate):
        self.requests.put(("rate", float(rate)))

    def stop(self):
        self.requests.put(None)

    @staticmethod
    def _to_sapi_rate(rate):
        return max(-10, min(10, round((float(rate) - 1.0) * (5 / 0.3))))

    def run(self):
        if comtypes is None or CreateObject is None:
            self.events.put((
                "speech_error",
                "Windows text-to-speech is unavailable. Install the project requirements.",
            ))
            return

        com_initialized = False
        try:
            comtypes.CoInitialize()
            com_initialized = True
            speaker = CreateObject("SAPI.SpVoice")
            speaker.EventInterests = 32
            voices = speaker.GetVoices()
            default_voice = speaker.Voice
        except Exception as error:
            if com_initialized:
                comtypes.CoUninitialize()
            self.events.put(("speech_error", f"Could not start Windows text-to-speech: {error}"))
            return

        voice_lookup = {"Default": None}
        chinese_voice = find_chinese_sapi_voice(voices)
        try:
            for index in range(voices.Count):
                voice = voices.Item(index)
                raw_name = voice.GetDescription() or f"Voice {index + 1}"
                lower_name = raw_name.lower()
                female_markers = (
                    "female", "zira", "hazel", "heera", "susan", "sara",
                    "jenny", "aria", "eva", "samantha",
                )
                male_markers = (
                    "male", "david", "mark", "george", "guy", "ryan",
                    "james", "thomas", "andrew", "jason",
                )
                if any(marker in lower_name for marker in female_markers):
                    display_name = f"Female - {raw_name}"
                elif any(marker in lower_name for marker in male_markers):
                    display_name = f"Male - {raw_name}"
                else:
                    display_name = raw_name
                if display_name in voice_lookup:
                    display_name = f"{display_name} ({index + 1})"
                voice_lookup[display_name] = voice.Id
            options = list(voice_lookup)
            self.events.put((
                "voices_loaded",
                {
                    "options": options,
                    "lookup": voice_lookup,
                },
            ))
        except Exception:
            self.events.put((
                "voices_loaded",
                {
                    "options": ["Default"],
                    "lookup": {"Default": None},
                },
            ))

        self.events.put(("speech_ready", "Text-to-speech ready."))

        pending_requests = queue.Queue()
        try:
            while True:
                try:
                    request = pending_requests.get_nowait()
                except queue.Empty:
                    request = self.requests.get()
                if request is None:
                    speaker.Speak("", 2)
                    return

                command, payload = request
                try:
                    if command == "volume":
                        speaker.Volume = max(0, min(100, int(payload)))
                        continue
                    if command == "rate":
                        speaker.Rate = self._to_sapi_rate(payload)
                        continue

                    text, rate, voice_name, volume, request_id = payload
                    voice_id = voice_lookup.get(voice_name)
                    if voice_id is None and chinese_voice is not None and is_mostly_chinese(text):
                        speaker.Voice = chinese_voice
                    elif voice_id is None:
                        speaker.Voice = default_voice
                    else:
                        for index in range(voices.Count):
                            voice = voices.Item(index)
                            if voice.Id == voice_id:
                                speaker.Voice = voice
                                break
                    speaker.Rate = self._to_sapi_rate(rate)
                    speaker.Volume = max(0, min(100, int(volume)))
                    word_positions = self._speech_word_positions(text)
                    speaker.Speak(text, 1)
                    last_word = None
                    word_tracking_error_reported = False
                    while True:
                        speech_done = speaker.WaitUntilDone(25)
                        try:
                            status = speaker.Status
                            word_start = int(status.InputWordPosition)
                            word_length = int(status.InputWordLength)
                            word_span = word_positions.get((word_start, word_length))
                        except Exception as error:
                            if not word_tracking_error_reported:
                                self.events.put((
                                    "speech_error",
                                    f"Could not track the currently spoken word: {error}",
                                ))
                                word_tracking_error_reported = True
                            word_span = None
                        if word_span is not None and word_span != last_word:
                            last_word = word_span
                            self.events.put(("word", (request_id, word_span)))
                        if speech_done:
                            break
                        try:
                            update = self.requests.get_nowait()
                        except queue.Empty:
                            continue
                        if update is None:
                            speaker.Speak("", 2)
                            return
                        update_command, update_payload = update
                        if update_command == "volume":
                            speaker.Volume = max(0, min(100, int(update_payload)))
                        elif update_command == "rate":
                            speaker.Rate = self._to_sapi_rate(update_payload)
                        else:
                            pending_requests.put(update)
                    self.events.put(("spoken", request_id))
                except Exception as error:
                    self.events.put(("speech_error", f"Could not read the text aloud: {error}"))
        finally:
            comtypes.CoUninitialize()

    @staticmethod
    def _speech_word_positions(text):
        word_positions = {}
        for match in re.finditer(r"\w+(?:['’]\w+)*", text):
            start = len(text[:match.start()].encode("utf-16-le")) // 2
            length = len(match.group().encode("utf-16-le")) // 2
            word_positions[(start, length)] = (match.start(), match.end())
        return word_positions


class DyslexiaCameraApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ClearView - Everyday Object Assistant")
        self.root.geometry("1400x900")
        self.root.minsize(1120, 700)
        self.root.configure(bg=PALETTE["background"])

        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(
            "TCombobox",
            fieldbackground=PALETTE["control"],
            background=PALETTE["control"],
            foreground=PALETTE["text"],
            arrowcolor=PALETTE["text"],
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", PALETTE["control"])],
            foreground=[("readonly", PALETTE["text"])],
            selectbackground=[("readonly", PALETTE["control"])],
            selectforeground=[("readonly", PALETTE["text"])],
        )

        self.descriptions, description_warning = load_descriptions()
        installed_fonts = set(tkfont.families(root))
        global UI_FONT
        UI_FONT = next(
            (name for name in PREFERRED_UI_FONTS if name in installed_fonts), "Arial"
        )
        self.font_options = ["Verdana", "Arial", "Trebuchet MS"]
        for optional_font in ("OpenDyslexic", "Atkinson Hyperlegible", "Atkinson Hyperlegible Next"):
            if optional_font in installed_fonts:
                self.font_options.insert(0, optional_font)
        self.font_family = tk.StringVar(value="Verdana")
        self.font_size = tk.IntVar(value=22)
        self.bold_reading_text = tk.BooleanVar(value=False)
        self.app_color_choice = tk.StringVar(value=DEFAULT_APP_COLOR)
        self.letter_spacing = tk.IntVar(value=0)
        self.line_spacing = tk.IntVar(value=8)
        self.speech_rate = tk.DoubleVar(value=1.0)
        self.volume = tk.IntVar(value=100)
        self.voice_name = tk.StringVar(value="Default")
        self.detector_choice = tk.StringVar(value=DETECTOR_CLEARVIEW)
        self.brightness = tk.IntVar(value=100)
        self.auto_speak = tk.BooleanVar(value=True)
        self.current_sentence = "Point the camera at an object, then choose Identify object."
        self.speech_request_id = 0
        self.active_sentence_span = None
        self.active_word_span = None
        self.voice_lookup = {}
        self.model_ready = False
        self.model_error = None
        self.active_detector = None
        self.last_frame = None
        self.analysis_frame = None
        self.photo_image = None
        self.photo_mode = False
        self.is_analyzing = False
        self.closing = False
        self.brightness_window = None

        self._restore_settings()

        self.camera = CameraWorker()
        self.analysis = AnalysisWorker(
            list(self.descriptions),
            detector_choice=self.detector_choice.get(),
        )
        self.speech = SpeechWorker()

        self._build_ui()
        if self.app_color_choice.get() != DEFAULT_APP_COLOR:
            self._apply_theme()
        if self.bold_reading_text.get():
            self._update_reading_style()
        self.speed_value.set(f"{self.speech_rate.get():.1f}×")
        self.identify_button.configure(state="disabled")
        self.root.bind("<Configure>", self._on_window_resize)
        if description_warning:
            self._set_status(description_warning, "warning")
        self.camera.start()
        self.analysis.start()
        self.speech.start()
        self.root.after(30, self._poll_workers)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self):
        self.root.grid_columnconfigure(0, weight=2, uniform="main")
        self.root.grid_columnconfigure(1, weight=3, uniform="main")
        self.root.grid_rowconfigure(0, weight=1)

        left = tk.Frame(self.root, bg=PALETTE["background"], padx=18, pady=18)
        left.grid(row=0, column=0, sticky="nsew")
        right = tk.Frame(
            self.root,
            bg=PALETTE["background"],
            padx=12,
            pady=18,
        )
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 18), pady=18)

        title_bar = tk.Frame(left, bg=PALETTE["background"])
        title_bar.pack(fill="x", padx=4, pady=(0, 12))
        menu_button = tk.Menubutton(
            title_bar,
            text="☰",
            font=(UI_FONT, 23, "bold"),
            bg=PALETTE["background"],
            fg=PALETTE["text"],
            activebackground=PALETTE["accent_hover"],
            activeforeground=PALETTE["text"],
            relief="flat",
            bd=0,
            padx=8,
            cursor="hand2",
        )
        app_menu = tk.Menu(
            menu_button,
            tearoff=False,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            activebackground=PALETTE["accent"],
            activeforeground=PALETTE["button_text"],
        )
        self.app_menu = app_menu
        background_menu = tk.Menu(
            self.app_menu,
            tearoff=False,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            activebackground=PALETTE["accent"],
            activeforeground=PALETTE["button_text"],
        )
        self.background_menu = background_menu
        for color_name in APP_COLOR_PRESETS:
            background_menu.add_radiobutton(
                label=color_name,
                variable=self.app_color_choice,
                value=color_name,
                command=lambda choice=color_name: self._set_app_color(choice),
            )
        self.app_menu.add_cascade(
            label="Background colour",
            menu=background_menu,
        )
        self.app_menu.add_separator()
        app_menu.add_radiobutton(
            label="Everyday objects (default)",
            variable=self.detector_choice,
            value=DETECTOR_CLEARVIEW,
            command=self._on_detector_change,
        )
        app_menu.add_radiobutton(
            label="YOLO26 (80 types)",
            variable=self.detector_choice,
            value=DETECTOR_YOLO26,
            command=self._on_detector_change,
        )
        app_menu.add_radiobutton(
            label="YOLO-World backup",
            variable=self.detector_choice,
            value=DETECTOR_YOLO_WORLD,
            command=self._on_detector_change,
        )
        app_menu.add_separator()
        app_menu.add_command(
            label="Set camera brightness…",
            command=self.open_brightness_settings,
        )
        menu_button.configure(menu=app_menu)
        menu_button.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(0, 8))
        title_bar.grid_columnconfigure(1, weight=1)
        tk.Label(
            title_bar,
            text="ClearView",
            bg=PALETTE["background"],
            fg=PALETTE["text"],
            font=(UI_FONT, 26, "bold"),
            anchor="w",
        ).grid(row=0, column=1, sticky="ew")
        tk.Label(
            title_bar,
            text="Point the camera at something to hear what it is.",
            bg=PALETTE["background"],
            fg=PALETTE["muted"],
            font=(UI_FONT, 14),
            anchor="w",
            justify="left",
            wraplength=420,
        ).grid(row=1, column=1, sticky="ew")

        self.preview = tk.Label(
            left,
            text="Starting camera…",
            bg=PALETTE["preview"],
            fg=PALETTE["text"],
            font=(UI_FONT, 18),
            relief="flat",
            bd=0,
        )
        self.preview.pack(fill="both", expand=True, padx=4, pady=(0, 12))

        actions = tk.Frame(left, bg=PALETTE["background"])
        actions.pack(fill="x", padx=4)
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)

        self.identify_button = self._button(actions, "Identify object", self.identify_object)
        self.identify_button.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=4)
        self.photo_button = self._button(actions, "Choose a photo", self.choose_photo)
        self.photo_button.grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=4)
        self.use_camera_button = self._button(
            actions, "Return to live camera", self.use_live_camera, secondary=True
        )
        self.use_camera_button.grid(row=1, column=0, columnspan=2, sticky="ew", pady=4)

        self.camera_status = tk.Label(
            left,
            text="Camera is starting…",
            bg=PALETTE["background"],
            fg=PALETTE["muted"],
            font=(UI_FONT, 13),
            anchor="w",
            justify="left",
            wraplength=650,
        )
        self.camera_status.pack(fill="x", padx=4, pady=(8, 0))
        left.bind("<Configure>", self._wrap_left_status)

        reading_heading = tk.Frame(right, bg=PALETTE["background"])
        reading_heading.pack(fill="x", pady=(0, 14))
        tk.Label(
            reading_heading,
            text="Result",
            bg=PALETTE["background"],
            fg=PALETTE["text"],
            font=(UI_FONT, 22, "bold"),
            anchor="w",
        ).pack(fill="x")

        reading_layout = tk.Frame(right, bg=PALETTE["background"])
        reading_layout.pack(fill="both", expand=True)
        reading_layout.grid_columnconfigure(0, weight=1)
        reading_layout.grid_rowconfigure(0, weight=1)
        self.explanation_card = tk.Frame(
            reading_layout,
            bg=PALETTE["panel"],
            padx=24,
            pady=20,
            highlightbackground=PALETTE["border"],
            highlightthickness=1,
        )
        self.explanation_card.grid(row=0, column=0, sticky="nsew")
        self.explanation_card.grid_columnconfigure(0, weight=1)
        self.explanation_card.grid_rowconfigure(3, weight=1)
        # Settings sit in a wide strip under the result: Text left, Voice right.
        self.control_panel = tk.Frame(reading_layout, bg=PALETTE["background"])
        self.control_panel.grid(row=1, column=0, sticky="ew", pady=(16, 0))

        self.object_name = tk.Label(
            self.explanation_card,
            text="Ready when you are",
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            font=(UI_FONT, 26, "bold"),
            anchor="w",
            justify="left",
            wraplength=700,
        )
        self.object_name.grid(row=1, column=0, sticky="ew")

        description_frame = tk.Frame(
            self.explanation_card,
            bg=PALETTE["reading_panel"],
            padx=14,
            pady=14,
        )
        description_frame.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
        description_frame.grid_columnconfigure(0, weight=1)
        description_frame.grid_rowconfigure(0, weight=1)
        self.description_label = tk.Text(
            description_frame,
            bg=PALETTE["reading_panel"],
            fg=PALETTE["text"],
            font=(self.font_family.get(), self.font_size.get()),
            wrap="word",
            width=24,
            height=12,
            relief="flat",
            bd=0,
            padx=4,
            pady=4,
            spacing1=0,
            spacing2=self.line_spacing.get(),
            spacing3=self.line_spacing.get(),
            insertbackground=PALETTE["text"],
        )
        self.description_label.grid(row=0, column=0, sticky="nsew")
        description_scrollbar = tk.Scrollbar(
            description_frame,
            orient="vertical",
            command=self.description_label.yview,
            bg=PALETTE["control"],
            troughcolor=PALETTE["panel"],
            activebackground=PALETTE["accent"],
            highlightthickness=0,
            bd=0,
        )
        description_scrollbar.grid(row=0, column=1, sticky="ns")
        self.description_label.configure(yscrollcommand=description_scrollbar.set)
        self.description_label.tag_configure(
            "reading_sentence",
            background=PALETTE["selection_sentence"],
        )
        self.description_label.tag_configure(
            "reading_word",
            background=PALETTE["selection_word"],
            foreground=PALETTE["button_text"],
            font=(self.font_family.get(), self.font_size.get(), "bold"),
        )
        self._render_description()

        self.confidence_label = tk.Label(
            self.explanation_card,
            text="AI confidence: —",
            bg=PALETTE["panel"],
            fg=PALETTE["muted"],
            font=(UI_FONT, 12),
            anchor="w",
        )
        self.confidence_label.grid(row=2, column=0, sticky="ew", pady=(4, 0))

        listen_bar = tk.Frame(self.explanation_card, bg=PALETTE["panel"])
        listen_bar.grid(row=4, column=0, sticky="ew", pady=(16, 0))
        self.read_button = self._button(listen_bar, "Read aloud", self.read_aloud)
        self.read_button.configure(padx=28)
        self.read_button.pack(side="left")
        self.repeat_button = self._button(
            listen_bar, "Repeat", self.read_aloud, secondary=True
        )
        self.repeat_button.configure(padx=24)
        self.repeat_button.pack(side="left", padx=(10, 0))
        tk.Checkbutton(
            listen_bar,
            text="Read results automatically",
            variable=self.auto_speak,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            activebackground=PALETTE["panel"],
            activeforeground=PALETTE["text"],
            selectcolor=PALETTE["reading_panel"],
            font=(UI_FONT, 12),
            anchor="w",
        ).pack(side="left", padx=(18, 0))

        self.status_label = tk.Label(
            self.camera_status.master,
            text="Loading AI model and speech…",
            bg=PALETTE["background"],
            fg=PALETTE["muted"],
            font=(UI_FONT, 12),
            justify="left",
            anchor="w",
            wraplength=600,
        )
        self.status_label.pack(fill="x", padx=4, pady=(4, 0))

        self.control_panel.grid_columnconfigure(0, weight=1, uniform="settings")
        self.control_panel.grid_columnconfigure(1, weight=1, uniform="settings")
        text_group = self._settings_group(self.control_panel, "Text")
        text_group.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        voice_group = self._settings_group(self.control_panel, "Voice")
        voice_group.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self.font_choice = ttk.Combobox(
            text_group,
            textvariable=self.font_family,
            values=self.font_options,
            state="readonly",
            font=(UI_FONT, 12),
            width=16,
        )
        self.font_choice.bind("<<ComboboxSelected>>", self._on_font_change)
        self._setting_row(text_group, 1, "Font", self.font_choice)
        self.bold_reading_check = tk.Checkbutton(
            text_group,
            text="Bold text",
            variable=self.bold_reading_text,
            command=self._update_reading_style,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            activebackground=PALETTE["panel"],
            activeforeground=PALETTE["text"],
            selectcolor=PALETTE["reading_panel"],
            font=(UI_FONT, 12),
            anchor="w",
        )
        self.bold_reading_check.grid(row=2, column=1, sticky="w", pady=(0, 4))
        self.size_scale = self._slider(text_group, 18, 36, 1, self.font_size, self._on_size_change)
        self._setting_row(text_group, 3, "Size", self.size_scale, self.font_size)
        self.letter_spacing_scale = self._slider(
            text_group, 0, 4, 1, self.letter_spacing, self._on_letter_spacing_change
        )
        self._setting_row(
            text_group, 4, "Letter spacing", self.letter_spacing_scale, self.letter_spacing
        )
        self.line_spacing_scale = self._slider(
            text_group, 0, 20, 2, self.line_spacing, self._on_line_spacing_change
        )
        self._setting_row(text_group, 5, "Line spacing", self.line_spacing_scale, self.line_spacing)

        self.voice_choice = ttk.Combobox(
            voice_group,
            textvariable=self.voice_name,
            values=["Default"],
            state="readonly",
            font=(UI_FONT, 12),
            width=16,
        )
        self.voice_choice.bind("<<ComboboxSelected>>", self._on_voice_change)
        self._setting_row(voice_group, 1, "Voice", self.voice_choice)
        self.speed_value = tk.StringVar(value="1.0×")
        self.speed_scale = self._slider(
            voice_group, 0.7, 1.3, 0.1, self.speech_rate, self._on_speech_rate_change
        )
        self._setting_row(voice_group, 2, "Speed", self.speed_scale, self.speed_value)
        self.volume_scale = self._slider(
            voice_group, 0, 100, 1, self.volume, self._on_volume_change
        )
        self._setting_row(voice_group, 3, "Volume", self.volume_scale, self.volume)

    @staticmethod
    def _settings_group(parent, title):
        group = tk.Frame(
            parent,
            bg=PALETTE["panel"],
            padx=20,
            pady=14,
            highlightbackground=PALETTE["border"],
            highlightthickness=1,
        )
        group.grid_columnconfigure(1, weight=1)
        tk.Label(
            group,
            text=title,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            font=(UI_FONT, 14, "bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        return group

    @staticmethod
    def _setting_row(group, row, label, control, value=None):
        """One setting per row: its name, the control, and the current value."""
        tk.Label(
            group,
            text=label,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            font=(UI_FONT, 12),
            anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=4)
        control.grid(row=row, column=1, sticky="ew", pady=4)
        if value is not None:
            tk.Label(
                group,
                textvariable=value,
                bg=PALETTE["panel"],
                fg=PALETTE["text"],
                font=(UI_FONT, 12, "bold"),
                width=4,
                anchor="e",
            ).grid(row=row, column=2, sticky="e", padx=(12, 0))

    @staticmethod
    def _slider(parent, start, end, step, variable, command):
        return tk.Scale(
            parent,
            from_=start,
            to=end,
            resolution=step,
            orient="horizontal",
            variable=variable,
            command=command,
            showvalue=False,
            bg=PALETTE["accent"],
            fg=PALETTE["text"],
            troughcolor=PALETTE["trough"],
            activebackground=PALETTE["accent_hover"],
            highlightthickness=0,
            sliderlength=26,
            width=14,
            sliderrelief="flat",
            bd=0,
        )

    @staticmethod
    def _button(parent, text, command, secondary=False):
        color = PALETTE["control"] if secondary else PALETTE["accent"]
        foreground = PALETTE["text"] if secondary else PALETTE["button_text"]
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=(UI_FONT, 15, "bold"),
            bg=color,
            fg=foreground,
            activebackground=PALETTE["accent_hover"],
            activeforeground=PALETTE["button_text"],
            bd=0,
            padx=12,
            pady=12,
            cursor="hand2",
            wraplength=260,
        )

    def open_brightness_settings(self):
        if self.brightness_window is not None and self.brightness_window.winfo_exists():
            self.brightness_window.lift()
            return

        window = tk.Toplevel(self.root)
        self.brightness_window = window
        window.title("Camera brightness")
        window.geometry("420x190")
        window.resizable(False, False)
        window.transient(self.root)
        window.configure(bg=PALETTE["background"])
        window.protocol(
            "WM_DELETE_WINDOW",
            lambda: self._close_brightness_settings(window),
        )
        tk.Label(
            window,
            text="Camera image brightness",
            bg=PALETTE["background"],
            fg=PALETTE["text"],
            font=(UI_FONT, 16, "bold"),
        ).pack(anchor="w", padx=20, pady=(18, 4))
        value_label = tk.Label(
            window,
            text=f"{self.brightness.get()}%",
            bg=PALETTE["background"],
            fg=PALETTE["accent"],
            font=(UI_FONT, 13, "bold"),
        )
        value_label.pack(anchor="w", padx=20)
        tk.Scale(
            window,
            from_=50,
            to=150,
            resolution=5,
            orient="horizontal",
            variable=self.brightness,
            command=lambda value: (
                self._on_brightness_change(value),
                value_label.configure(text=f"{self.brightness.get()}%"),
            ),
            bg=PALETTE["background"],
            fg=PALETTE["text"],
            troughcolor=PALETTE["trough"],
            activebackground=PALETTE["accent"],
            highlightthickness=0,
            showvalue=False,
            font=(UI_FONT, 12),
            length=360,
            bd=0,
        ).pack(fill="x", padx=20, pady=(4, 8))
        tk.Label(
            window,
            text="Adjusts the camera preview and image used for object identification.",
            bg=PALETTE["background"],
            fg=PALETTE["muted"],
            font=(UI_FONT, 12),
        ).pack(anchor="w", padx=20)

    def _apply_theme(self):
        palette = dict(APP_COLOR_PRESETS[self.app_color_choice.get()])

        previous_palette = dict(PALETTE)
        color_map = {
            previous_palette[key]: palette[key]
            for key in palette
        }
        PALETTE.update(palette)

        style = ttk.Style(self.root)
        style.configure(
            "TCombobox",
            fieldbackground=PALETTE["control"],
            background=PALETTE["control"],
            foreground=PALETTE["text"],
            arrowcolor=PALETTE["text"],
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", PALETTE["control"])],
            foreground=[("readonly", PALETTE["text"])],
            selectbackground=[("readonly", PALETTE["control"])],
            selectforeground=[("readonly", PALETTE["text"])],
        )

        color_options = (
            "background",
            "bg",
            "foreground",
            "fg",
            "activebackground",
            "activeforeground",
            "selectcolor",
            "selectbackground",
            "selectforeground",
            "troughcolor",
            "insertbackground",
            "highlightbackground",
            "highlightcolor",
        )

        def recolor(widget):
            widget_options = widget.keys()
            for option in color_options:
                if option not in widget_options:
                    continue
                current_color = str(widget.cget(option)).lower()
                replacement = color_map.get(current_color)
                if replacement is not None:
                    widget.configure(**{option: replacement})
            for child in widget.winfo_children():
                recolor(child)

        recolor(self.root)
        recolor(self.app_menu)
        recolor(self.background_menu)
        self.description_label.tag_configure(
            "reading_sentence",
            background=PALETTE["selection_sentence"],
            foreground=PALETTE["text"],
        )
        self.description_label.tag_configure(
            "reading_word",
            background=PALETTE["selection_word"],
            foreground=PALETTE["button_text"],
        )

    def _set_app_color(self, color_name):
        self.app_color_choice.set(color_name)
        self._apply_theme()

    def _close_brightness_settings(self, window):
        if self.brightness_window is window:
            self.brightness_window = None
        window.destroy()

    def _on_brightness_change(self, value):
        self.brightness.set(int(float(value)))

    def _on_detector_change(self):
        requested_detector = self.detector_choice.get()
        if self.is_analyzing:
            if self.active_detector is not None:
                self.detector_choice.set(self.active_detector)
            self._set_status(
                "Wait for the current object analysis to finish before changing detectors.",
                "warning",
            )
            return
        if requested_detector == self.active_detector and self.model_ready:
            return

        self.model_error = None
        self.identify_button.configure(state="disabled")
        self._set_status(f"Loading {DETECTOR_NAMES[requested_detector]}…", "info")
        self.analysis.switch_detector(requested_detector)

    def _set_status(self, message, kind="info"):
        if self.model_error and kind != "error":
            message = self.model_error
            kind = "error"
        colors = {
            "info": PALETTE["muted"],
            "success": PALETTE["success"],
            "warning": PALETTE["warning"],
            "error": PALETTE["error"],
        }
        self.status_label.configure(text=message, fg=colors.get(kind, PALETTE["muted"]))

    def _update_reading_style(self):
        font_weight = "bold" if self.bold_reading_text.get() else "normal"
        self.description_label.configure(
            font=(self.font_family.get(), self.font_size.get(), font_weight)
        )
        self.description_label.tag_configure(
            "reading_word",
            font=(self.font_family.get(), self.font_size.get(), "bold"),
        )
        self._render_description()

    def _render_description(self):
        gap = "\u2009" * self.letter_spacing.get()
        display_parts = []
        display_offsets = [0]
        display_length = 0
        for index, character in enumerate(self.current_sentence):
            display_parts.append(character)
            display_length += len(character)
            if (
                gap
                and not character.isspace()
                and index + 1 < len(self.current_sentence)
                and not self.current_sentence[index + 1].isspace()
            ):
                display_parts.append(gap)
                display_length += len(gap)
            display_offsets.append(display_length)
        display_text = "".join(display_parts)
        self.description_label.configure(state="normal")
        self.description_label.delete("1.0", "end")
        self.description_label.insert("1.0", display_text)
        self.description_label.tag_remove("reading_sentence", "1.0", "end")
        self.description_label.tag_remove("reading_word", "1.0", "end")
        for tag, span in (
            ("reading_sentence", self.active_sentence_span),
            ("reading_word", self.active_word_span),
        ):
            if span is not None:
                start, end = span
                self.description_label.tag_add(
                    tag,
                    f"1.0+{display_offsets[start]}c",
                    f"1.0+{display_offsets[end]}c",
                )
        self.description_label.configure(
            state="disabled",
            spacing2=self.line_spacing.get(),
            spacing3=self.line_spacing.get(),
        )

    def _set_description(self, text):
        self.speech_request_id += 1
        self.current_sentence = text
        self.active_sentence_span = None
        self.active_word_span = None
        self._render_description()

    def _set_reading_word(self, word_span):
        word_start, word_end = word_span
        sentence_span = next(
            (
                (match.start(), match.end())
                for match in re.finditer(r"[^.!?]+[.!?]*", self.current_sentence)
                if match.start() <= word_start < match.end()
            ),
            (0, len(self.current_sentence)),
        )
        self.active_sentence_span = sentence_span
        self.active_word_span = (word_start, word_end)
        self._render_description()
        self.description_label.see(f"1.0+{word_start}c")

    def _on_voice_change(self, event):
        self.voice_name.set(event.widget.get())

    def _on_window_resize(self, event):
        if event.widget is not self.root:
            return
        reading_width = max(220, self.explanation_card.winfo_width() - 48)
        self.object_name.configure(wraplength=reading_width)
        description_font = tkfont.Font(
            root=self.root,
            family=self.font_family.get(),
            size=self.font_size.get(),
        )
        available_text_width = self.description_label.master.winfo_width() - 42
        if available_text_width > 100:
            text_columns = max(
                24,
                min(60, available_text_width // max(1, description_font.measure("n"))),
            )
            if int(self.description_label.cget("width")) != text_columns:
                self.description_label.configure(width=text_columns)

    def _wrap_left_status(self, event):
        wrap = max(200, event.width - 48)
        self.camera_status.configure(wraplength=wrap)
        self.status_label.configure(wraplength=wrap)

    def _on_font_change(self, event):
        self.font_family.set(event.widget.get())
        self._update_reading_style()

    def _on_size_change(self, value):
        self.font_size.set(int(float(value)))
        self._update_reading_style()

    def _on_letter_spacing_change(self, value):
        self.letter_spacing.set(int(float(value)))
        self._render_description()

    def _on_line_spacing_change(self, value):
        self.line_spacing.set(int(float(value)))
        self.description_label.configure(
            spacing2=self.line_spacing.get(),
            spacing3=self.line_spacing.get(),
        )

    def _on_volume_change(self, value):
        volume = int(float(value))
        self.volume.set(volume)
        self.speech.set_volume(volume)

    def _on_speech_rate_change(self, value):
        rate = round(float(value), 1)
        self.speech_rate.set(rate)
        self.speed_value.set(f"{rate:.1f}×")
        self.speech.set_rate(rate)

    def _show_frame(self, frame, adjust_brightness=True):
        if Image is None or ImageTk is None:
            self.camera_status.configure(
                text="Install Pillow to show the camera preview. Identification can still work."
            )
            return

        if adjust_brightness and self.brightness.get() != 100:
            frame = cv2.convertScaleAbs(
                frame,
                alpha=self.brightness.get() / 100.0,
                beta=0,
            )
        height, width = frame.shape[:2]
        available_width = self.preview.winfo_width() - 16
        available_height = self.preview.winfo_height() - 16
        if available_width < 100 or available_height < 100:
            available_width, available_height = PREVIEW_SIZE
        available_width = min(available_width, PREVIEW_SIZE[0])
        available_height = min(available_height, PREVIEW_SIZE[1])
        scale = min(available_width / width, available_height / height)
        resized = cv2.resize(frame, (int(width * scale), int(height * scale)))
        rgb_frame = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        self.photo_image = ImageTk.PhotoImage(Image.fromarray(rgb_frame))
        self.preview.configure(image=self.photo_image, text="")

    def _poll_workers(self):
        if self.closing:
            return

        frame = self.camera.get_frame()
        if frame is not None and not self.photo_mode:
            self.last_frame = frame
            self._show_frame(frame)

        self._drain_events(self.camera.events, self._handle_camera_event)
        self._drain_events(self.analysis.events, self._handle_analysis_event)
        self._drain_events(self.speech.events, self._handle_speech_event)
        self.root.after(30, self._poll_workers)

    @staticmethod
    def _drain_events(event_queue, handler):
        while True:
            try:
                event, payload = event_queue.get_nowait()
            except queue.Empty:
                return
            handler(event, payload)

    def _handle_camera_event(self, event, message):
        if event == "ready":
            self.camera_status.configure(text=message, fg=PALETTE["success"])
        else:
            self.camera_status.configure(text=message, fg=PALETTE["error"])

    def _handle_analysis_event(self, event, payload):
        if event == "model_ready":
            self.model_ready = True
            self.model_error = None
            self.active_detector = payload["detector"]
            self.detector_choice.set(self.active_detector)
            self._set_status(
                payload["ocr_error"] or payload["message"],
                "warning" if payload["ocr_error"] else "success",
            )
            self.identify_button.configure(state="normal")
        elif event == "model_loading":
            self.identify_button.configure(state="disabled")
            self._set_status(f"Loading {DETECTOR_NAMES.get(payload, 'the detector')}…", "info")
        elif event == "ocr_loading":
            self._set_status("Loading object and text recognition models…", "info")
        elif event == "model_error":
            self.is_analyzing = False
            self.analysis_frame = None
            self.model_ready = False
            self.active_detector = payload["active_detector"]
            self.model_error = payload["message"]
            self._set_status(self.model_error, "error")
            self.identify_button.configure(state="disabled")
            self.photo_button.configure(state="normal")
            self.use_camera_button.configure(state="normal")
        elif event == "model_switch_error":
            self.is_analyzing = False
            self.analysis_frame = None
            self.active_detector = payload["active_detector"]
            if self.active_detector is None:
                self.model_ready = False
                self.model_error = payload["message"]
                self._set_status(self.model_error, "error")
                self.identify_button.configure(state="disabled")
            else:
                self.detector_choice.set(self.active_detector)
                self.model_ready = True
                self.model_error = None
                self._set_status(payload["message"], "warning")
                self.identify_button.configure(state="normal")
        elif event == "not_found":
            self.is_analyzing = False
            self.analysis_frame = None
            self.identify_button.configure(state="normal", text="Identify object")
            self.photo_button.configure(state="normal")
            self.use_camera_button.configure(state="normal")
            self.object_name.configure(text="No clear match")
            self._set_description(  
                "I could not identify an object with enough confidence. "
                "Try moving closer or improving the lighting."
            )
            self.confidence_label.configure(text="AI confidence: no confident match")
            self._set_status("No object was recognized. Please try again.", "warning")
        elif event == "found":
            self.is_analyzing = False
            self.identify_button.configure(state="normal", text="Identify object")
            self.photo_button.configure(state="normal")
            self.use_camera_button.configure(state="normal")
            self._show_detection(payload)
        elif event == "analysis_error":
            self.is_analyzing = False
            self.analysis_frame = None
            self.identify_button.configure(state="normal", text="Identify object")
            self.photo_button.configure(state="normal")
            self.use_camera_button.configure(state="normal")
            self._set_status(f"Object analysis failed: {payload}", "error")

    def _handle_speech_event(self, event, message):
        if event == "speech_ready":
            if self.model_ready and not self.model_error:
                self._set_status(message, "success")
        elif event == "word":
            request_id, word_span = message
            if request_id == self.speech_request_id:
                self._set_reading_word(word_span)
        elif event == "spoken":
            if message == self.speech_request_id:
                self.active_sentence_span = None
                self.active_word_span = None
                self._render_description()
                self._set_status(
                    "Finished reading. Press Read aloud or Repeat to hear it again.",
                    "success",
                )
        elif event == "speech_error":
            self.active_sentence_span = None
            self.active_word_span = None
            self._render_description()
            if not self.model_error:
                self._set_status(message, "warning")
        elif event == "voices_loaded":
            self.voice_lookup = message.get("lookup", {"Default": None})
            options = message.get("options", ["Default"])
            self.voice_choice.configure(values=options)
            if self.voice_name.get() not in options:
                self.voice_name.set("Default")

    def _show_detection(self, detection):
        label = detection["label"].strip().lower().replace("_", " ")
        confidence = detection["confidence"]
        recognized_text = detection.get("recognized_text", "")
        ocr_error = detection.get("ocr_error")
        cloud_description = detection.get("cloud_description", "")
        cloud_product = detection.get("cloud_product", "")
        cloud_error = detection.get("cloud_error")
        explanation = self.descriptions.get(
            label,
            "It is an everyday object. You can add a simple explanation for it "
            "in object_descriptions.json.",
        )
        article = "an" if label[:1] in "aeiou" else "a"
        if cloud_product:
            description = f"The label suggests this is {cloud_product}. "
        elif cloud_description:
            description = cloud_description
        else:
            description = f"This is {article} {label}. {explanation}"
        if cloud_product and cloud_description:
            description += cloud_description
        if recognized_text:
            description += f" The visible text reads: {recognized_text}."
        other_labels = [
            other for other in detection.get("all_labels", []) if other != label
        ]
        if other_labels:
            description += f" I can also see: {', '.join(other_labels)}."
        self._set_description(description)
        self.object_name.configure(text=(cloud_product or label).title())
        self.confidence_label.configure(text=f"AI confidence: {confidence:.0%}")
        if cloud_error:
            self._set_status(
                f"Object recognized locally, but cloud description was unavailable: {cloud_error}",
                "warning",
            )
        elif ocr_error:
            self._set_status(
                f"Object recognized, but text reading was unavailable: {ocr_error}",
                "warning",
            )
        elif recognized_text:
            self._set_status(
                "Object recognized. Visible text was also read; either result may be incorrect.",
                "success",
            )
        else:
            self._set_status(
                "Object recognized; no readable text was found. The result may not always be correct.",
                "success",
            )

        source_frame = self.analysis_frame
        if source_frame is not None:
            display_frame = source_frame.copy()
            x1, y1, x2, y2 = [int(value) for value in detection["coordinates"]]
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), (143, 79, 31), 3)
            cv2.putText(
                display_frame,
                f"{label.title()} {confidence:.0%}",
                (x1, max(28, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (143, 79, 31),
                2,
                cv2.LINE_AA,
            )
            self.photo_mode = True
            self._show_frame(display_frame, adjust_brightness=False)
            self.camera_status.configure(
                text="Result image paused. Choose Return to live camera when ready.",
                fg=PALETTE["success"],
            )
        self.analysis_frame = None

        if self.auto_speak.get():
            self.read_aloud()

    def identify_object(self):
        if self.is_analyzing:
            return
        if self.last_frame is None:
            self._set_status("Camera has no image yet. Wait a moment or choose a photo.", "warning")
            return
        if cv2 is None:
            self._set_status("OpenCV is not installed. Install the requirements first.", "error")
            return

        self.is_analyzing = True
        self.analysis_frame = self.last_frame.copy()
        if self.brightness.get() != 100:
            self.analysis_frame = cv2.convertScaleAbs(
                self.analysis_frame,
                alpha=self.brightness.get() / 100.0,
                beta=0,
            )
        self.identify_button.configure(state="disabled", text="Analyzing…")
        self.photo_button.configure(state="disabled")
        self.use_camera_button.configure(state="disabled")
        self._set_status("Analyzing the current image…", "info")
        self.analysis.identify(self.analysis_frame.copy())

    def choose_photo(self):
        if cv2 is None:
            self._set_status("OpenCV is required to open a photo.", "error")
            return
        path = filedialog.askopenfilename(
            title="Choose a photo",
            filetypes=(
                ("Image files", "*.jpg *.jpeg *.png *.bmp *.webp"),
                ("All files", "*.*"),
            ),
        )
        if not path:
            return
        frame = cv2.imread(path)
        if frame is None:
            self._set_status("That image could not be opened. Choose another file.", "error")
            return
        self.photo_mode = True
        self.last_frame = frame
        self._show_frame(frame)
        if self.model_ready:
            self.identify_button.configure(state="normal")
        self.camera_status.configure(
            text=f"Photo selected: {Path(path).name}. Choose Identify object.",
            fg=PALETTE["success"],
        )
        if not self.model_ready and not self.model_error:
            self._set_status("Photo selected. The AI model is still loading.", "info")

    def use_live_camera(self):
        self.photo_mode = False
        self.analysis_frame = None
        if not self.camera.is_alive():
            self.camera = CameraWorker()
            self.camera.start()
        self._set_status("Live camera selected.", "info")

    def read_aloud(self):
        if not self.current_sentence:
            return
        self.speech_request_id += 1
        first_word = re.search(r"\w+(?:['’]\w+)*", self.current_sentence)
        if first_word:
            self._set_reading_word((first_word.start(), first_word.end()))
        self.speech.speak(
            self.current_sentence,
            self.speech_rate.get(),
            self.voice_name.get(),
            self.volume.get(),
            self.speech_request_id,
        )
        self._set_status("Reading the explanation aloud…", "info")

    def _restore_settings(self):
        saved = load_settings()
        for name in SAVED_SETTINGS:
            if name in saved:
                try:
                    getattr(self, name).set(saved[name])
                except (tk.TclError, TypeError, ValueError):
                    pass
        # Drop values that no longer make sense (removed tint, uninstalled font, …).
        if self.app_color_choice.get() not in APP_COLOR_PRESETS:
            self.app_color_choice.set(DEFAULT_APP_COLOR)
        if self.font_family.get() not in self.font_options:
            self.font_family.set("Verdana")
        if self.detector_choice.get() not in DETECTOR_NAMES:
            self.detector_choice.set(DETECTOR_CLEARVIEW)

    def close(self):
        save_settings({name: getattr(self, name).get() for name in SAVED_SETTINGS})
        self.closing = True
        self.camera.stop()
        self.analysis.stop()
        self.speech.stop()
        self.root.destroy()


def main():
    if cv2 is None:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Missing dependency",
            "OpenCV is required. In the project folder, run:\n\n"
            "python -m pip install -r requirements.txt",
        )
        root.destroy()
        return

    root = tk.Tk()
    DyslexiaCameraApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
