"""Camera worker: captures frames away from Tk's UI thread."""
import queue
import threading
import time

from .deps import cv2


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
