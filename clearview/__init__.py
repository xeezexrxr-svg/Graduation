"""ClearView desktop app: names the closest object in view and reads it aloud.

Modules, by job:
    config      file paths, detector names and confidence thresholds
    deps        optional libraries (OpenCV, Pillow, Windows speech, Ultralytics)
    palette     the six reading tints
    detection   box maths, the closest-object rule, merging the two detectors
    language    spotting Chinese text and choosing a Chinese voice
    storage     saved settings and object descriptions
    camera      camera worker thread
    analysis    analysis worker thread (detect, read text, ask the cloud)
    speech      speech worker thread
    ui          the window
Start it with `python app.py`.
"""
