"""Spotting Chinese text, so it can be read with a Chinese voice."""
import re

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
