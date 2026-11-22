"""Analysis worker: detects objects, reads label text and asks the cloud, off the UI thread.

Requests come in on `requests` ("identify", frame) / ("switch_detector", name) /
None to stop; results go out on `events` for the window to show.
"""
import json
import queue
import threading
import urllib.error
import urllib.request

from .config import (
    APP_DIR,
    CLEARVIEW_MODEL_FILE,
    CLOUD_VISION_API_URL,
    DETECTOR_CLEARVIEW,
    DETECTOR_CONFIDENCE,
    DETECTOR_YOLO26,
    DETECTOR_YOLO_WORLD,
    MIN_CONFIDENCE,
    YOLO26_MODEL_FILE,
    YOLO_WORLD_MODEL_FILE,
)
from .deps import YOLO, YOLOWorld, cv2
from .detection import (
    is_person,
    list_labels,
    load_coco_model,
    merge_with_coco,
    plain_label,
    read_detections,
    select_closest,
    worth_cropping,
)

CLOUD_ERRORS = (OSError, TimeoutError, ValueError, json.JSONDecodeError, urllib.error.URLError)


def crop_around(frame, coordinates, ratio, minimum):
    """Crop a box out of the frame with padding; returns (crop, (left, top)) or (None, None)."""
    frame_height, frame_width = frame.shape[:2]
    x1, y1, x2, y2 = coordinates
    pad_x = max(minimum, int((x2 - x1) * ratio))
    pad_y = max(minimum, int((y2 - y1) * ratio))
    left, top = max(0, int(x1) - pad_x), max(0, int(y1) - pad_y)
    right, bottom = min(frame_width, int(x2) + pad_x), min(frame_height, int(y2) + pad_y)
    if right <= left or bottom <= top:
        return None, None
    return frame[top:bottom, left:right], (left, top)


def request_cloud_details(frame, detection):
    """Send the detected object's crop (or the whole photo) to the ClearView cloud for a description."""
    height, width = frame.shape[:2]
    if worth_cropping(detection, width, height):
        crop, _ = crop_around(frame, detection["coordinates"], 0.08, 12)
    else:
        crop = frame
    if crop is None:
        raise ValueError("The detected object crop is empty.")
    crop_height, crop_width = crop.shape[:2]
    scale = min(1.0, 960 / max(crop_width, crop_height))
    if scale < 1:
        crop = cv2.resize(crop, (round(crop_width * scale), round(crop_height * scale)))
    success, encoded = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 78])
    if not success:
        raise ValueError("Could not encode the detected object for cloud analysis.")

    request = urllib.request.Request(
        CLOUD_VISION_API_URL,
        data=encoded.tobytes(),
        # Cloudflare blocks Python's default "Python-urllib" user agent (error 1010).
        headers={
            "Content-Type": "image/jpeg",
            "X-ClearView-Client": "desktop",
            "User-Agent": "ClearView-Desktop/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Cloud vision returned an invalid response.")
    if not payload.get("found"):
        raise ValueError("Cloud vision could not add details for this object.")
    return payload


def combine_text(local, cloud):
    """Join the on-device and cloud label readings without repeating them."""
    cloud = cloud.strip() if isinstance(cloud, str) else ""
    if cloud and local and cloud.casefold() not in local.casefold():
        return f"{local} {cloud}"
    return local or cloud


class AnalysisWorker(threading.Thread):
    """Load the detectors once, then analyse requested frames."""

    def __init__(self, candidate_names, detector_choice=DETECTOR_CLEARVIEW):
        super().__init__(daemon=True, name="analysis-worker")
        self.requests = queue.Queue()
        self.events = queue.Queue()
        self.candidate_names = candidate_names
        self.detector_choice = detector_choice
        self.model = None
        self.model_label = ""
        self.active_detector = None
        self.coco_model = None
        self.coco_loaded = False
        self.ocr_reader = None
        self.ocr_error = None

    def identify(self, frame):
        self.requests.put(("identify", frame))

    def switch_detector(self, detector_choice):
        self.requests.put(("switch_detector", detector_choice))

    def stop(self):
        self.requests.put(None)

    # --- Loading -------------------------------------------------------------

    def _load_detector(self, detector_choice):
        if detector_choice in (DETECTOR_CLEARVIEW, DETECTOR_YOLO26) and YOLO is None:
            raise RuntimeError("Ultralytics YOLO is unavailable.")
        if detector_choice == DETECTOR_CLEARVIEW:
            if not (APP_DIR / CLEARVIEW_MODEL_FILE).exists():
                raise FileNotFoundError(f"{CLEARVIEW_MODEL_FILE} is missing. Run build_detector.py to create it.")
            model = YOLO(str(APP_DIR / CLEARVIEW_MODEL_FILE))
            return model, f"everyday objects, {len(model.names)} types"
        if detector_choice == DETECTOR_YOLO26:
            return YOLO(YOLO26_MODEL_FILE), f"YOLO26 ({YOLO26_MODEL_FILE})"
        if detector_choice == DETECTOR_YOLO_WORLD:
            if YOLOWorld is None:
                raise RuntimeError("Ultralytics YOLO-World is unavailable.")
            if not self.candidate_names:
                raise ValueError("Add at least one object name to object_descriptions.json.")
            model = YOLOWorld(YOLO_WORLD_MODEL_FILE)
            model.set_classes(self.candidate_names)
            return model, f"YOLO-World backup ({YOLO_WORLD_MODEL_FILE})"
        raise ValueError(f"Unknown detector selection: {detector_choice}")

    def _announce_ready(self):
        self.events.put(("model_ready", {
            "message": f"AI model ready ({self.model_label}).",
            "ocr_error": self.ocr_error,
            "detector": self.active_detector,
        }))

    def _start_up(self):
        self.events.put(("model_loading", self.detector_choice))
        try:
            self.model, self.model_label = self._load_detector(self.detector_choice)
            self.active_detector = self.detector_choice
        except Exception as error:
            self.events.put(("model_error", {
                "message": f"Could not load the selected detector: {error}",
                "active_detector": None,
            }))

        self.events.put(("ocr_loading", None))
        try:
            import easyocr

            self.ocr_reader = easyocr.Reader(["en", "ch_tra"], gpu=False, verbose=False)
        except Exception as error:
            self.ocr_error = f"Text reading is unavailable. Install the project requirements and restart the app. {error}"

        if self.model is not None:
            self._announce_ready()

    def _switch_detector(self, requested):
        self.events.put(("model_loading", requested))
        try:
            self.model, self.model_label = self._load_detector(requested)
        except Exception as error:
            self.events.put(("model_switch_error", {
                "message": f"Could not load the requested detector: {error}",
                "active_detector": self.active_detector,
            }))
            return
        self.active_detector = requested
        self._announce_ready()

    # --- Analysing one frame --------------------------------------------------

    def _detect(self, frame):
        """All detections in the frame, from both detectors when using the everyday one."""
        confidence = DETECTOR_CONFIDENCE.get(self.active_detector, MIN_CONFIDENCE)
        results = self.model.predict(frame, verbose=False, conf=confidence)
        detections = read_detections(results[0]) if results else []
        if self.active_detector == DETECTOR_CLEARVIEW:
            if not self.coco_loaded:
                self.coco_model = load_coco_model()
                self.coco_loaded = True
            if self.coco_model is not None:
                coco_results = self.coco_model.predict(frame, verbose=False, conf=MIN_CONFIDENCE)
                detections = merge_with_coco(
                    detections,
                    read_detections(coco_results[0]) if coco_results else [],
                    self.coco_model.names.values(),
                )
        if detections:
            detections += self._recheck_near_hands(frame, detections, confidence)
        return detections

    def _recheck_near_hands(self, frame, detections, confidence):
        """Look again, closer, around a hand or person to catch small held objects."""
        people = [d for d in detections if is_person(d)]
        if not people:
            return []
        hands = [d for d in people if plain_label(d) == "hand"]
        around = max(hands or people, key=lambda d: d["confidence"])
        crop, offset = crop_around(frame, around["coordinates"], 0.15, 24)
        if crop is None:
            return []
        results = self.model.predict(crop, verbose=False, conf=confidence * 0.7)
        if not results or results[0].boxes is None:
            return []
        return read_detections(results[0], offset=offset)

    def _read_label_text(self, frame, detection):
        """Read text on the object with EasyOCR; returns (text, error or None)."""
        if self.ocr_reader is None:
            return "", self.ocr_error
        try:
            crop, _ = crop_around(frame, detection["coordinates"], 0.08, 12)
            if crop is None:
                return "", None
            parts, seen = [], set()
            for _, text, confidence in self.ocr_reader.readtext(crop, detail=1):
                text = text.strip()
                if text and float(confidence) >= 0.30 and text.casefold() not in seen:
                    parts.append(text)
                    seen.add(text.casefold())
            return " ".join(parts)[:240], None
        except Exception as error:
            return "", f"Text reading failed: {error}"

    def _add_cloud_details(self, frame, detection):
        try:
            details = request_cloud_details(frame, detection)
        except CLOUD_ERRORS as error:
            detection.update(cloud_description="", cloud_product="", cloud_label="", cloud_error=str(error))
            return
        detection.update(
            cloud_description=details.get("description", ""),
            cloud_product=details.get("product", ""),
            cloud_label=details.get("label") or "",
            cloud_error=None,
            recognized_text=combine_text(detection["recognized_text"], details.get("recognizedText", ""))[:240],
        )

    def _analyse(self, frame):
        detections = self._detect(frame)
        if not detections:
            self.events.put(("not_found", None))
            return
        detection = select_closest(detections)
        detection["all_labels"] = list_labels(detections)
        detection["recognized_text"], detection["ocr_error"] = self._read_label_text(frame, detection)
        self._add_cloud_details(frame, detection)
        self.events.put(("found", detection))

    def run(self):
        self._start_up()
        while True:
            request = self.requests.get()
            if request is None:
                return
            command, payload = request
            if command == "switch_detector":
                self._switch_detector(payload)
            elif self.model is not None:
                try:
                    self._analyse(payload)
                except Exception as error:
                    self.events.put(("analysis_error", str(error)))
