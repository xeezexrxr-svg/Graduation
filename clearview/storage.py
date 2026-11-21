"""Saved reading settings, and the object descriptions shared with the phone site."""
import json

from .config import DESCRIPTIONS_FILE, SETTINGS_FILE

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


def load_descriptions(path=None):
    """Return ({object name: short description}, warning message or "").

    Without the file the app still works: results just use a general sentence.
    """
    path = path or DESCRIPTIONS_FILE
    try:
        with path.open("r", encoding="utf-8") as description_file:
            loaded = json.load(description_file)
    except FileNotFoundError:
        return {}, f"{path.name} is missing, so short object descriptions are unavailable."
    except (OSError, json.JSONDecodeError) as error:
        return {}, f"Could not read {path.name}: {error}."

    if not isinstance(loaded, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in loaded.items()
    ):
        return {}, f"{path.name} must contain object names and description text."

    descriptions = {key.strip().lower(): value.strip() for key, value in loaded.items()}
    return {key: value for key, value in descriptions.items() if key and value}, ""
