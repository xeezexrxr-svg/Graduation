"""Speech worker: owns the Windows text-to-speech engine on its own thread.

Requests come in on `requests`: ("speak", (text, rate, voice, volume, id)),
("volume", n), ("rate", r), or None to stop. Progress goes out on `events`:
"voices_loaded", "speech_ready", "word" (to highlight), "spoken", "speech_error".
"""
import queue
import re
import threading

from .deps import CreateObject, comtypes
from .language import find_chinese_sapi_voice, is_mostly_chinese

FEMALE_MARKERS = ("female", "zira", "hazel", "heera", "susan", "sara", "jenny", "aria", "eva", "samantha")
MALE_MARKERS = ("male", "david", "mark", "george", "guy", "ryan", "james", "thomas", "andrew", "jason")
SPEAK_ASYNC = 1
SPEAK_PURGE = 2
WORD_BOUNDARY_EVENTS = 32


def voice_menu(voices):
    """{menu name: voice id} for the voice dropdown, starting with "Default".

    Names get "Female - " or "Male - " when the voice's name makes that clear.
    """
    lookup = {"Default": None}
    for index in range(voices.Count):
        voice = voices.Item(index)
        name = voice.GetDescription() or f"Voice {index + 1}"
        lower = name.lower()
        if any(marker in lower for marker in FEMALE_MARKERS):
            name = f"Female - {name}"
        elif any(marker in lower for marker in MALE_MARKERS):
            name = f"Male - {name}"
        if name in lookup:
            name = f"{name} ({index + 1})"
        lookup[name] = voice.Id
    return lookup


def word_positions(text):
    """Map SAPI's (start, length) word positions, counted in UTF-16 units, to
    Python string offsets, so the spoken word can be highlighted."""
    positions = {}
    for match in re.finditer(r"\w+(?:['’]\w+)*", text):
        start = len(text[:match.start()].encode("utf-16-le")) // 2
        length = len(match.group().encode("utf-16-le")) // 2
        positions[(start, length)] = (match.start(), match.end())
    return positions


def to_sapi_rate(rate):
    """App speed (0.7×–1.3×) to SAPI's -10…10 scale."""
    return max(-10, min(10, round((float(rate) - 1.0) * (5 / 0.3))))


class SpeechWorker(threading.Thread):
    """Own the TTS engine on one thread to keep speech and UI responsive."""

    def __init__(self):
        super().__init__(daemon=True, name="speech-worker")
        self.requests = queue.Queue()
        self.events = queue.Queue()
        # Speak requests that arrived while something else was being read.
        self.waiting = queue.Queue()
        self.speaker = None
        self.voices = None
        self.default_voice = None
        self.chinese_voice = None
        self.voice_lookup = {"Default": None}

    def speak(self, text, rate, voice_name=None, volume=100, request_id=0):
        self.requests.put(("speak", (text, rate, voice_name, volume, request_id)))

    def set_volume(self, volume):
        self.requests.put(("volume", int(volume)))

    def set_rate(self, rate):
        self.requests.put(("rate", float(rate)))

    def stop(self):
        self.requests.put(None)

    # --- Engine ---------------------------------------------------------------

    def _open_engine(self):
        """Start SAPI and list the voices. Returns False if speech is unavailable."""
        if comtypes is None or CreateObject is None:
            self.events.put(("speech_error", "Windows text-to-speech is unavailable. Install the project requirements."))
            return False
        initialized = False
        try:
            comtypes.CoInitialize()
            initialized = True
            self.speaker = CreateObject("SAPI.SpVoice")
            self.speaker.EventInterests = WORD_BOUNDARY_EVENTS
            self.voices = self.speaker.GetVoices()
            self.default_voice = self.speaker.Voice
        except Exception as error:
            if initialized:
                comtypes.CoUninitialize()
            self.events.put(("speech_error", f"Could not start Windows text-to-speech: {error}"))
            return False

        self.chinese_voice = find_chinese_sapi_voice(self.voices)
        try:
            self.voice_lookup = voice_menu(self.voices)
        except Exception:
            self.voice_lookup = {"Default": None}
        self.events.put(("voices_loaded", {"options": list(self.voice_lookup), "lookup": self.voice_lookup}))
        self.events.put(("speech_ready", "Text-to-speech ready."))
        return True

    def _apply_setting(self, command, value):
        """Volume and speed changes, which also apply in the middle of reading."""
        if command == "volume":
            self.speaker.Volume = max(0, min(100, int(value)))
        elif command == "rate":
            self.speaker.Rate = to_sapi_rate(value)

    def _choose_voice(self, text, voice_name):
        """The reader's chosen voice; with "Default", Chinese text gets a Chinese voice."""
        voice_id = self.voice_lookup.get(voice_name)
        if voice_id is None:
            use_chinese = self.chinese_voice is not None and is_mostly_chinese(text)
            self.speaker.Voice = self.chinese_voice if use_chinese else self.default_voice
            return
        for index in range(self.voices.Count):
            voice = self.voices.Item(index)
            if voice.Id == voice_id:
                self.speaker.Voice = voice
                return

    # --- Reading ----------------------------------------------------------------

    def _spoken_word(self, positions, reported_error):
        """The word being spoken now, as (start, end) in the text, or None."""
        try:
            status = self.speaker.Status
            return positions.get((int(status.InputWordPosition), int(status.InputWordLength))), reported_error
        except Exception as error:
            if not reported_error:
                self.events.put(("speech_error", f"Could not track the currently spoken word: {error}"))
            return None, True

    def _read_aloud(self, text, rate, voice_name, volume, request_id):
        """Speak text, reporting each word. Returns False if asked to stop."""
        self._choose_voice(text, voice_name)
        self.speaker.Rate = to_sapi_rate(rate)
        self.speaker.Volume = max(0, min(100, int(volume)))
        positions = word_positions(text)
        self.speaker.Speak(text, SPEAK_ASYNC)
        last_word = None
        reported_error = False
        while True:
            done = self.speaker.WaitUntilDone(25)
            word, reported_error = self._spoken_word(positions, reported_error)
            if word is not None and word != last_word:
                last_word = word
                self.events.put(("word", (request_id, word)))
            if done:
                break
            try:
                update = self.requests.get_nowait()
            except queue.Empty:
                continue
            if update is None:
                self.speaker.Speak("", SPEAK_PURGE)
                return False
            if update[0] in ("volume", "rate"):
                self._apply_setting(*update)
            else:
                self.waiting.put(update)
        self.events.put(("spoken", request_id))
        return True

    def _next_request(self):
        try:
            return self.waiting.get_nowait()
        except queue.Empty:
            return self.requests.get()

    def run(self):
        if not self._open_engine():
            return
        try:
            while True:
                request = self._next_request()
                if request is None:
                    self.speaker.Speak("", SPEAK_PURGE)
                    return
                command, payload = request
                try:
                    if command in ("volume", "rate"):
                        self._apply_setting(command, payload)
                    elif not self._read_aloud(*payload):
                        return
                except Exception as error:
                    self.events.put(("speech_error", f"Could not read the text aloud: {error}"))
        finally:
            comtypes.CoUninitialize()
