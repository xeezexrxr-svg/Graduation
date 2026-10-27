"""Accessible camera assistant: identify common objects and describe them aloud."""

from __future__ import annotations

import json
import queue
import re
import threading
import time
import tkinter as tk
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
    from ultralytics import YOLOWorld
except ImportError:
    YOLOWorld = None


APP_DIR = Path(__file__).resolve().parent
DESCRIPTIONS_FILE = APP_DIR / "object_descriptions.json"
MODEL_FILE = "yolov8s-worldv2.pt"
MIN_CONFIDENCE = 0.30
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

PALETTE = {
    "background": "#0e1322",
    "panel": "#1a2032",
    "text": "#e9e9f8",
    "muted": "#b9bad0",
    "accent": "#b49aff",
    "accent_hover": "#c4b2ff",
    "preview": "#202638",
    "success": "#81c995",
    "warning": "#ffcc80",
    "border": "#30384f",
}


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

    def __init__(self, candidate_names):
        super().__init__(daemon=True, name="analysis-worker")
        self.requests = queue.Queue()
        self.events = queue.Queue()
        self.candidate_names = candidate_names

    def identify(self, frame):
        self.requests.put(frame)

    def stop(self):
        self.requests.put(None)

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
        return max(
            object_detections or detections,
            key=lambda detection: detection["confidence"],
        )

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

    def run(self):
        if YOLOWorld is None:
            self.events.put((
                "model_error",
                "Open-vocabulary AI model unavailable. Upgrade ultralytics, then restart the app.",
            ))
            return

        try:
            model = YOLOWorld(MODEL_FILE)
            if not self.candidate_names:
                raise ValueError("Add at least one object name to object_descriptions.json.")
            model.set_classes(self.candidate_names)
        except Exception as error:
            self.events.put((
                "model_error",
                f"Could not load or configure {MODEL_FILE}: {error}",
            ))
            return

        self.events.put(("model_ready", f"AI model ready ({MODEL_FILE})."))

        while True:
            frame = self.requests.get()
            if frame is None:
                return

            try:
                results = model.predict(frame, verbose=False, conf=MIN_CONFIDENCE)
                if not results or results[0].boxes is None or len(results[0].boxes) == 0:
                    self.events.put(("not_found", None))
                    continue

                detections = self._read_detections(results[0])
                detection = self._select_detection(detections)
                if detection["label"].strip().lower().replace("_", " ") in self.HUMAN_LABELS:
                    frame_height, frame_width = frame.shape[:2]
                    x1, y1, x2, y2 = detection["coordinates"]
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
                            conf=MIN_CONFIDENCE * 0.7,
                        )
                        if crop_results and crop_results[0].boxes is not None:
                            crop_detections = self._read_detections(
                                crop_results[0],
                                offset=(crop_x1, crop_y1),
                            )
                            crop_detection = self._select_detection(crop_detections)
                            if (
                                crop_detection
                                and crop_detection["label"].strip().lower().replace("_", " ")
                                not in self.HUMAN_LABELS
                            ):
                                detection = crop_detection
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

    def stop(self):
        self.requests.put(None)

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
        gender_options = {"Female": [], "Male": []}
        try:
            for index in range(voices.Count):
                voice = voices.Item(index)
                raw_name = voice.GetDescription() or f"Voice {index + 1}"
                lower_name = raw_name.lower()
                gender = None
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
                    gender = "Female"
                elif any(marker in lower_name for marker in male_markers):
                    display_name = f"Male - {raw_name}"
                    gender = "Male"
                else:
                    display_name = raw_name
                if display_name in voice_lookup:
                    display_name = f"{display_name} ({index + 1})"
                voice_lookup[display_name] = voice.Id
                if gender:
                    gender_options[gender].append(display_name)
            options = list(voice_lookup)
            self.events.put((
                "voices_loaded",
                {
                    "options": options,
                    "lookup": voice_lookup,
                    "gender_options": gender_options,
                },
            ))
        except Exception:
            self.events.put((
                "voices_loaded",
                {
                    "options": ["Default"],
                    "lookup": {"Default": None},
                    "gender_options": {"Female": [], "Male": []},
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

                    text, rate, voice_name, volume, request_id = payload
                    voice_id = voice_lookup.get(voice_name)
                    if voice_id is None:
                        speaker.Voice = default_voice
                    else:
                        for index in range(voices.Count):
                            voice = voices.Item(index)
                            if voice.Id == voice_id:
                                speaker.Voice = voice
                                break
                    speaker.Rate = max(-10, min(10, round((rate - 155) / 10)))
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
            fieldbackground="#262d42",
            background="#262d42",
            foreground=PALETTE["text"],
            arrowcolor=PALETTE["text"],
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#262d42")],
            foreground=[("readonly", PALETTE["text"])],
            selectbackground=[("readonly", "#262d42")],
            selectforeground=[("readonly", PALETTE["text"])],
        )

        self.descriptions, description_warning = load_descriptions()
        installed_fonts = set(tkfont.families(root))
        self.font_options = ["Arial", "Verdana", "Trebuchet MS"]
        if "OpenDyslexic" in installed_fonts:
            self.font_options.insert(0, "OpenDyslexic")
        self.font_family = tk.StringVar(value="Arial")
        self.font_size = tk.IntVar(value=22)
        self.letter_spacing = tk.IntVar(value=0)
        self.line_spacing = tk.IntVar(value=4)
        self.speech_rate = tk.IntVar(value=155)
        self.volume = tk.IntVar(value=100)
        self.voice_name = tk.StringVar(value="Default")
        self.voice_gender = tk.StringVar(value="Female")
        self.auto_speak = tk.BooleanVar(value=True)
        self.current_sentence = "Point the camera at an object, then choose Identify object."
        self.speech_request_id = 0
        self.active_sentence_span = None
        self.active_word_span = None
        self.typography_expanded = True
        self.audio_expanded = True
        self.voice_lookup = {}
        self.gender_voice_options = {"Female": [], "Male": []}
        self.model_ready = False
        self.model_error = None
        self.last_frame = None
        self.analysis_frame = None
        self.photo_image = None
        self.photo_mode = False
        self.is_analyzing = False
        self.closing = False

        self.camera = CameraWorker()
        self.analysis = AnalysisWorker(list(self.descriptions))
        self.speech = SpeechWorker()

        self._build_ui()
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
        self.root.grid_columnconfigure(0, weight=2)
        self.root.grid_columnconfigure(1, weight=3)
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

        tk.Label(
            left,
            text="ClearView",
            bg=PALETTE["background"],
            fg=PALETTE["text"],
            font=("Arial", 26, "bold"),
            anchor="w",
        ).pack(fill="x", padx=4, pady=(0, 4))
        tk.Label(
            left,
            text="A camera assistant for everyday objects",
            bg=PALETTE["background"],
            fg=PALETTE["muted"],
            font=("Arial", 14),
            anchor="w",
        ).pack(fill="x", padx=4, pady=(0, 12))

        self.preview = tk.Label(
            left,
            text="Starting camera…",
            bg=PALETTE["preview"],
            fg=PALETTE["text"],
            font=("Arial", 18),
            relief="solid",
            bd=1,
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
            font=("Arial", 12),
            anchor="w",
            justify="left",
            wraplength=650,
        )
        self.camera_status.pack(fill="x", padx=4, pady=(8, 0))

        reading_heading = tk.Frame(right, bg=PALETTE["background"])
        reading_heading.pack(fill="x", pady=(0, 14))
        tk.Label(
            reading_heading,
            text="Reading & Processing Support",
            bg=PALETTE["background"],
            fg=PALETTE["text"],
            font=("Arial", 22, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            reading_heading,
            text="Visual and cognitive aids for better comprehension.",
            bg=PALETTE["background"],
            fg=PALETTE["muted"],
            font=("Arial", 11),
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

        reading_layout = tk.Frame(right, bg=PALETTE["background"])
        reading_layout.pack(fill="both", expand=True)
        reading_layout.grid_columnconfigure(0, weight=2, uniform="reading")
        reading_layout.grid_columnconfigure(1, weight=5, uniform="reading")
        reading_layout.grid_rowconfigure(0, weight=1)
        self.control_panel = tk.Frame(
            reading_layout,
            bg=PALETTE["panel"],
            padx=12,
            pady=12,
            highlightbackground=PALETTE["border"],
            highlightthickness=1,
        )
        self.control_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.explanation_card = tk.Frame(
            reading_layout,
            bg=PALETTE["panel"],
            padx=20,
            pady=18,
            highlightbackground=PALETTE["border"],
            highlightthickness=1,
        )
        self.explanation_card.grid(row=0, column=1, sticky="nsew")
        self.explanation_card.grid_columnconfigure(0, weight=1)
        self.explanation_card.grid_rowconfigure(3, weight=1)

        heading = tk.Frame(self.control_panel, bg=PALETTE["panel"])
        heading.pack(fill="x", pady=(0, 16))
        heading.grid_columnconfigure(0, weight=1)
        tk.Label(
            heading,
            text="VOICE",
            bg=PALETTE["panel"],
            fg=PALETTE["accent"],
            font=("Arial", 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self.female_button = self._button(
            heading,
            "Female",
            lambda: self._select_voice_gender("Female"),
            secondary=True,
        )
        self.female_button.configure(
            font=("Arial", 10, "bold"), padx=10, pady=7, wraplength=0
        )
        self.female_button.grid(row=0, column=1, padx=(8, 4))
        self.male_button = self._button(
            heading,
            "Male",
            lambda: self._select_voice_gender("Male"),
            secondary=True,
        )
        self.male_button.configure(
            font=("Arial", 10, "bold"), padx=10, pady=7, wraplength=0
        )
        self.male_button.grid(row=0, column=2, padx=(4, 0))
        self._update_gender_buttons()

        self.object_name = tk.Label(
            self.explanation_card,
            text="Ready when you are",
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            font=("Arial", 26, "bold"),
            anchor="w",
            justify="left",
            wraplength=700,
        )
        tk.Label(
            self.explanation_card,
            text="OBJECT EXPLANATION",
            bg=PALETTE["panel"],
            fg=PALETTE["accent"],
            font=("Arial", 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.object_name.grid(row=1, column=0, sticky="ew")

        description_frame = tk.Frame(
            self.explanation_card,
            bg="#171d2d",
            padx=14,
            pady=14,
        )
        description_frame.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
        description_frame.grid_columnconfigure(0, weight=1)
        description_frame.grid_rowconfigure(0, weight=1)
        self.description_label = tk.Text(
            description_frame,
            bg="#171d2d",
            fg=PALETTE["text"],
            font=(self.font_family.get(), self.font_size.get()),
            wrap="word",
            width=50,
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
            bg="#262d42",
            troughcolor=PALETTE["panel"],
            activebackground=PALETTE["accent"],
            highlightthickness=0,
            bd=0,
        )
        description_scrollbar.grid(row=0, column=1, sticky="ns")
        self.description_label.configure(yscrollcommand=description_scrollbar.set)
        self.description_label.tag_configure(
            "reading_sentence",
            background="#353654",
        )
        self.description_label.tag_configure(
            "reading_word",
            background="#755cff",
            foreground="#ffffff",
            font=(self.font_family.get(), self.font_size.get(), "bold"),
        )
        self._render_description()

        self.confidence_label = tk.Label(
            self.explanation_card,
            text="AI confidence: —",
            bg=PALETTE["panel"],
            fg=PALETTE["muted"],
            font=("Arial", 11),
            anchor="w",
        )
        self.confidence_label.grid(row=2, column=0, sticky="ew", pady=(4, 0))

        speech_actions = tk.Frame(self.control_panel, bg=PALETTE["panel"])
        speech_actions.pack(fill="x", pady=(0, 8))
        speech_actions.grid_columnconfigure(0, weight=3)
        speech_actions.grid_columnconfigure(1, weight=2)
        self.read_button = self._button(speech_actions, "Read aloud", self.read_aloud)
        self.read_button.configure(font=("Arial", 11, "bold"), padx=6, pady=8)
        self.read_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.repeat_button = self._button(
            speech_actions, "Repeat", self.read_aloud, secondary=True
        )
        self.repeat_button.configure(font=("Arial", 11, "bold"), padx=6, pady=8)
        self.repeat_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        tk.Checkbutton(
            self.control_panel,
            text="Read results automatically",
            variable=self.auto_speak,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            activebackground=PALETTE["panel"],
            selectcolor="#343b52",
            activeforeground=PALETTE["text"],
            font=("Arial", 10),
            anchor="w",
            wraplength=180,
        ).pack(fill="x", pady=(0, 8))

        preferences = tk.LabelFrame(
            self.control_panel,
            text="VISUAL COMFORT",
            bg=PALETTE["panel"],
            fg=PALETTE["accent"],
            font=("Arial", 10, "bold"),
            padx=8,
            pady=6,
            highlightbackground=PALETTE["border"],
            bd=1,
        )
        preferences.pack(fill="x", pady=(0, 2))
        tk.Label(
            preferences,
            text="Reading font",
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            font=("Arial", 11, "bold"),
            anchor="w",
        ).pack(fill="x")
        self.font_choice = ttk.Combobox(
            preferences,
            textvariable=self.font_family,
            values=self.font_options,
            state="readonly",
            font=("Arial", 12),
        )
        self.font_choice.pack(fill="x", pady=(3, 6))
        self.font_choice.bind("<<ComboboxSelected>>", self._on_font_change)

        self.typography_toggle = tk.Button(
            preferences,
            text="▼  Typography Preferences",
            command=self._toggle_typography_preferences,
            font=("Arial", 10, "bold"),
            bg="#262d42",
            fg=PALETTE["text"],
            activebackground=PALETTE["accent_hover"],
            activeforeground="#202020",
            anchor="w",
            bd=0,
            padx=8,
            pady=6,
            cursor="hand2",
        )
        self.typography_toggle.pack(fill="x", pady=(2, 4))

        self.typography_controls = tk.Frame(preferences, bg=PALETTE["panel"])
        self.typography_controls.pack(fill="x")

        size_controls = tk.Frame(self.typography_controls, bg=PALETTE["panel"])
        size_controls.pack(fill="x")
        size_controls.grid_columnconfigure(1, weight=1)
        tk.Label(
            size_controls,
            text="A  Text size",
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            font=("Arial", 10, "bold"),
            anchor="w",
            width=8,
        ).grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.size_scale = tk.Scale(
            size_controls,
            from_=18,
            to=32,
            orient="horizontal",
            variable=self.font_size,
            command=self._on_size_change,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            highlightthickness=0,
            showvalue=True,
            font=("Arial", 9),
            sliderlength=14,
            bd=0,
        )
        self.size_scale.grid(row=0, column=1, sticky="ew")

        spacing_controls = tk.Frame(self.typography_controls, bg=PALETTE["panel"])
        spacing_controls.pack(fill="x", pady=(2, 0))
        spacing_controls.grid_columnconfigure(0, weight=1)

        letter_control = tk.Frame(spacing_controls, bg=PALETTE["panel"])
        letter_control.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        letter_control.grid_columnconfigure(1, weight=1)
        tk.Label(
            letter_control,
            text="Aa  Letter",
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            font=("Arial", 9, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.letter_spacing_scale = tk.Scale(
            letter_control,
            from_=0,
            to=4,
            orient="horizontal",
            variable=self.letter_spacing,
            command=self._on_letter_spacing_change,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            troughcolor="#343b52",
            activebackground=PALETTE["accent"],
            highlightthickness=0,
            showvalue=True,
            font=("Arial", 8),
            sliderlength=14,
            bd=0,
        )
        self.letter_spacing_scale.grid(row=0, column=1, sticky="ew")

        line_control = tk.Frame(spacing_controls, bg=PALETTE["panel"])
        line_control.grid(row=1, column=0, sticky="ew")
        line_control.grid_columnconfigure(1, weight=1)
        tk.Label(
            line_control,
            text="↕  Line",
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            font=("Arial", 9, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.line_spacing_scale = tk.Scale(
            line_control,
            from_=0,
            to=20,
            resolution=2,
            orient="horizontal",
            variable=self.line_spacing,
            command=self._on_line_spacing_change,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            troughcolor="#343b52",
            activebackground=PALETTE["accent"],
            highlightthickness=0,
            showvalue=True,
            font=("Arial", 8),
            sliderlength=14,
            bd=0,
        )
        self.line_spacing_scale.grid(row=0, column=1, sticky="ew")

        self.audio_toggle = tk.Button(
            preferences,
            text="▼  VOICE & AUDIO",
            command=self._toggle_audio_settings,
            font=("Arial", 10, "bold"),
            bg="#262d42",
            fg=PALETTE["text"],
            activebackground=PALETTE["accent_hover"],
            activeforeground="#202020",
            anchor="w",
            bd=0,
            padx=8,
            pady=6,
            cursor="hand2",
        )
        self.audio_toggle.pack(fill="x", pady=(2, 0))

        self.audio_controls = tk.Frame(preferences, bg=PALETTE["panel"])
        if self.audio_expanded:
            self.audio_controls.pack(fill="x", pady=(0, 0))
        self.audio_controls.grid_columnconfigure(0, weight=1)
        speed_control = tk.Frame(self.audio_controls, bg=PALETTE["panel"])
        speed_control.grid(row=0, column=0, sticky="ew")
        speed_control.grid_columnconfigure(1, weight=1)
        tk.Label(
            speed_control,
            text="−/+  Speed",
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            font=("Arial", 9, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.speed_scale = tk.Scale(
            speed_control,
            from_=110,
            to=210,
            orient="horizontal",
            variable=self.speech_rate,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            highlightthickness=0,
            showvalue=True,
            font=("Arial", 8),
            sliderlength=14,
            bd=0,
        )
        self.speed_scale.grid(row=0, column=1, sticky="ew")

        volume_control = tk.Frame(self.audio_controls, bg=PALETTE["panel"])
        volume_control.grid(row=1, column=0, sticky="ew")
        volume_control.grid_columnconfigure(1, weight=1)
        tk.Label(
            volume_control,
            text="VOL  Volume",
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            font=("Arial", 9, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.volume_scale = tk.Scale(
            volume_control,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self.volume,
            command=self._on_volume_change,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            troughcolor="#343b52",
            activebackground=PALETTE["accent"],
            highlightthickness=0,
            showvalue=True,
            font=("Arial", 8),
            sliderlength=14,
            bd=0,
        )
        self.volume_scale.grid(row=0, column=1, sticky="ew")

        self.processing_heading = tk.Label(
            self.control_panel,
            text="PROCESSING TOOLS",
            bg=PALETTE["panel"],
            fg=PALETTE["accent"],
            font=("Arial", 10, "bold"),
            anchor="w",
        )
        self.processing_heading.pack(fill="x", pady=(8, 6), before=speech_actions)
        preferences.pack_configure(before=self.processing_heading)

        self.status_label = tk.Label(
            self.control_panel,
            text="Loading AI model and speech…",
            bg="#252c41",
            fg=PALETTE["muted"],
            font=("Arial", 10),
            justify="left",
            anchor="w",
            wraplength=200,
            padx=8,
            pady=8,
        )
        self.status_label.pack(fill="x", side="bottom", pady=(8, 0))

        tk.Label(
            self.control_panel,
            text="Tip: use good lighting and keep one object in view.",
            bg=PALETTE["panel"],
            fg=PALETTE["muted"],
            font=("Arial", 9),
            justify="left",
            anchor="w",
            wraplength=350,
        ).pack(fill="x", pady=(4, 0))

    @staticmethod
    def _button(parent, text, command, secondary=False):
        color = "#262d42" if secondary else PALETTE["accent"]
        foreground = PALETTE["text"] if secondary else "#202020"
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=("Arial", 15, "bold"),
            bg=color,
            fg=foreground,
            activebackground=PALETTE["accent_hover"],
            activeforeground="#202020",
            bd=0,
            padx=12,
            pady=12,
            cursor="hand2",
            wraplength=260,
        )

    def _set_status(self, message, kind="info"):
        if self.model_error and kind != "error":
            message = self.model_error
            kind = "error"
        colors = {
            "info": PALETTE["muted"],
            "success": PALETTE["success"],
            "warning": PALETTE["warning"],
            "error": "#ff8a80",
        }
        self.status_label.configure(text=message, fg=colors.get(kind, PALETTE["muted"]))

    def _toggle_typography_preferences(self):
        self.typography_expanded = not self.typography_expanded
        if self.typography_expanded:
            self.typography_controls.pack(fill="x", after=self.typography_toggle)
            self.typography_toggle.configure(text="▼  Typography Preferences")
        else:
            self.typography_controls.pack_forget()
            self.typography_toggle.configure(text="▶  Typography Preferences")

    def _toggle_audio_settings(self):
        self.audio_expanded = not self.audio_expanded
        if self.audio_expanded:
            self.audio_controls.pack(fill="x", after=self.audio_toggle)
            self.audio_toggle.configure(text="▼  Voice & Audio Settings")
        else:
            self.audio_controls.pack_forget()
            self.audio_toggle.configure(text="▶  Voice & Audio Settings")

    def _update_reading_style(self):
        self.description_label.configure(
            font=(self.font_family.get(), self.font_size.get())
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

    def _update_gender_buttons(self):
        for gender, button in (
            ("Female", self.female_button),
            ("Male", self.male_button),
        ):
            selected = self.voice_gender.get() == gender
            button.configure(
                bg=PALETTE["accent"] if selected else "#262d42",
                fg="#202020" if selected else PALETTE["text"],
                activebackground=PALETTE["accent_hover"],
                activeforeground="#202020",
            )

    def _select_voice_gender(self, gender, announce=True):
        self.voice_gender.set(gender)
        self._update_gender_buttons()
        voices = self.gender_voice_options.get(gender, [])
        self.voice_name.set(voices[0] if voices else "Default")
        if announce and not voices and not self.model_error:
            self._set_status(
                f"No {gender.lower()} voice was identified. Using the system default voice.",
                "warning",
            )

    def _on_window_resize(self, event):
        if event.widget is not self.root:
            return
        reading_width = max(220, self.explanation_card.winfo_width() - 48)
        control_width = max(160, self.control_panel.winfo_width() - 28)
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
        self.status_label.configure(wraplength=control_width)

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

    def _show_frame(self, frame):
        if Image is None or ImageTk is None:
            self.camera_status.configure(
                text="Install Pillow to show the camera preview. Identification can still work."
            )
            return

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
            self.camera_status.configure(text=message, fg="#ff8a80")

    def _handle_analysis_event(self, event, payload):
        if event == "model_ready":
            self.model_ready = True
            self.model_error = None
            self._set_status(payload, "success")
            self.identify_button.configure(state="normal")
        elif event == "model_error":
            self.is_analyzing = False
            self.analysis_frame = None
            self.model_ready = False
            self.model_error = payload
            self._set_status(payload, "error")
            self.identify_button.configure(state="disabled")
            self.photo_button.configure(state="normal")
            self.use_camera_button.configure(state="normal")
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
            self.gender_voice_options = message.get(
                "gender_options", {"Female": [], "Male": []}
            )
            self._select_voice_gender(self.voice_gender.get(), announce=False)

    def _show_detection(self, detection):
        label = detection["label"].strip().lower().replace("_", " ")
        confidence = detection["confidence"]
        explanation = self.descriptions.get(
            label,
            "It is an everyday object. You can add a simple explanation for it "
            "in object_descriptions.json.",
        )
        article = "an" if label[:1] in "aeiou" else "a"
        self._set_description(f"This is {article} {label}. {explanation}")
        self.object_name.configure(text=label.title())
        self.confidence_label.configure(text=f"AI confidence: {confidence:.0%}")
        self._set_status(
            "Object recognized. The result may not always be correct.",
            "success",
        )

        source_frame = self.analysis_frame
        if source_frame is not None:
            display_frame = source_frame.copy()
            x1, y1, x2, y2 = [int(value) for value in detection["coordinates"]]
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), (36, 130, 76), 3)
            cv2.putText(
                display_frame,
                f"{label.title()} {confidence:.0%}",
                (x1, max(28, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (36, 130, 76),
                2,
                cv2.LINE_AA,
            )
            self.photo_mode = True
            self._show_frame(display_frame)
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

    def close(self):
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

