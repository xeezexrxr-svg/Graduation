"""The six reading tints, matching the phone site's.

Soft tinted backgrounds and dark grey (never pure black) text follow dyslexia
style guidance. PALETTE is the live palette: theme switching updates it in place.
"""


def mix(first, second, amount):
    """Blend two #rrggbb colours; amount 0 keeps first, 1 gives second."""
    channels = [
        round(int(first[i:i + 2], 16) * (1 - amount) + int(second[i:i + 2], 16) * amount)
        for i in (1, 3, 5)
    ]
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def reading_palette(ground, paper, raised, line, ink, muted, dark=False):
    """Build a full palette from one reading tint.

    Every value must be unique, because theme switching recolours widgets by
    mapping old colour values to new ones.
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
        "reading_panel": mix(paper, ground, 0.3),
        "preview": raised,
        "control": mix(raised, line, 0.3),
        "status_panel": mix(ground, raised, 0.5),
        "border": line,
        "trough": mix(line, raised, 0.5),
        "text": ink,
        "muted": muted,
        "accent": accent,
        "accent_hover": accent_hover,
        "button_text": on_accent,
        "selection_sentence": mix(paper, accent, 0.16),
        "selection_word": mix(accent, ink, 0.06),
        "success": success,
        "warning": warning,
        "error": error,
    }
    assert len(set(palette.values())) == len(palette), "palette colours must be unique"
    return palette


APP_COLOR_PRESETS = {
    "Cream": reading_palette("#faf6ec", "#fffcf4", "#f1ead8", "#d9cfb8", "#2b2a28", "#5c584f"),
    "Yellow": reading_palette("#fcf5c7", "#fffadb", "#f3e9ae", "#dccf8a", "#2b2a26", "#5b5640"),
    "Blue": reading_palette("#e3eef8", "#f1f6fc", "#d2e2f1", "#b3c8dd", "#24292f", "#4d5a68"),
    "Mint": reading_palette("#e6f2e4", "#f2f8f0", "#d5e8d2", "#b6cfb2", "#263026", "#4e5c4c"),
    "Peach": reading_palette("#fcebdd", "#fff5ec", "#f4dcc8", "#dfc2a9", "#2e2925", "#62554a"),
    "Dark": reading_palette(
        "#1e2227", "#2a3038", "#282d34", "#3a414b", "#e8e4d9", "#b0b4ba", dark=True
    ),
}
DEFAULT_APP_COLOR = "Cream"
PALETTE = dict(APP_COLOR_PRESETS[DEFAULT_APP_COLOR])
