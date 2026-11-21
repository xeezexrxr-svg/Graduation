"""Optional libraries, imported once. Each is None when not installed, so the
app can start and explain what's missing instead of crashing."""

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

__all__ = ["cv2", "Image", "ImageTk", "comtypes", "CreateObject", "YOLO", "YOLOWorld"]
