"""The ClearView window: camera on the left, result and reading settings on the right."""
import queue
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from .analysis import AnalysisWorker
from .camera import CameraWorker
from .config import (
    DETECTOR_CLEARVIEW,
    DETECTOR_NAMES,
    DETECTOR_YOLO26,
    DETECTOR_YOLO_WORLD,
    PREVIEW_SIZE,
    UNSURE_BELOW,
)
from .deps import Image, ImageTk, cv2
from .palette import APP_COLOR_PRESETS, DEFAULT_APP_COLOR, PALETTE
from .speech import SpeechWorker
from .storage import SAVED_SETTINGS, load_descriptions, load_settings, save_settings

# Interface font; upgraded at start-up if a dyslexia-friendly face is installed.
UI_FONT = "Segoe UI"
PREFERRED_UI_FONTS = ("Atkinson Hyperlegible Next", "Atkinson Hyperlegible", "Segoe UI")


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

        self._build_title_bar(left)
        self._build_camera_area(left)
        self._build_result_card(right)
        self._build_settings_strip()

    def _build_title_bar(self, parent):
        """The ☰ menu, the app name and a one-line explanation."""
        title_bar = tk.Frame(parent, bg=PALETTE["background"])
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
        menu_button.configure(menu=self._build_app_menu(menu_button))
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

    def _build_app_menu(self, menu_button):
        """Background colour, detector choice and camera brightness."""
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
        return app_menu

    def _build_camera_area(self, parent):
        """Camera preview, the main buttons and the two status lines."""
        self.preview = tk.Label(
            parent,
            text="Starting camera…",
            bg=PALETTE["preview"],
            fg=PALETTE["text"],
            font=(UI_FONT, 18),
            relief="flat",
            bd=0,
        )
        self.preview.pack(fill="both", expand=True, padx=4, pady=(0, 12))

        actions = tk.Frame(parent, bg=PALETTE["background"])
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
            parent,
            text="Camera is starting…",
            bg=PALETTE["background"],
            fg=PALETTE["muted"],
            font=(UI_FONT, 13),
            anchor="w",
            justify="left",
            wraplength=650,
        )
        self.camera_status.pack(fill="x", padx=4, pady=(8, 0))
        self.status_label = tk.Label(
            parent,
            text="Loading AI model and speech…",
            bg=PALETTE["background"],
            fg=PALETTE["muted"],
            font=(UI_FONT, 12),
            justify="left",
            anchor="w",
            wraplength=600,
        )
        self.status_label.pack(fill="x", padx=4, pady=(4, 0))
        parent.bind("<Configure>", self._wrap_left_status)

    def _build_result_card(self, parent):
        """The result: object name, confidence, the reading text and the listen buttons."""
        reading_heading = tk.Frame(parent, bg=PALETTE["background"])
        reading_heading.pack(fill="x", pady=(0, 14))
        tk.Label(
            reading_heading,
            text="Result",
            bg=PALETTE["background"],
            fg=PALETTE["text"],
            font=(UI_FONT, 22, "bold"),
            anchor="w",
        ).pack(fill="x")

        reading_layout = tk.Frame(parent, bg=PALETTE["background"])
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
        self._build_reading_text(self.explanation_card)

        self.confidence_label = tk.Label(
            self.explanation_card,
            text="AI confidence: —",
            bg=PALETTE["panel"],
            fg=PALETTE["muted"],
            font=(UI_FONT, 12),
            anchor="w",
        )
        self.confidence_label.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        self._build_listen_bar(self.explanation_card)

    def _build_reading_text(self, card):
        """The text box the result is read from, with sentence and word highlighting."""
        description_frame = tk.Frame(
            card,
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

    def _build_listen_bar(self, card):
        """Read aloud, Repeat, and the automatic reading switch."""
        listen_bar = tk.Frame(card, bg=PALETTE["panel"])
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

    def _build_settings_strip(self):
        """Text settings on the left, voice settings on the right, under the result."""
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
        cloud_label = detection.get("cloud_label", "")
        cloud_error = detection.get("cloud_error")
        unsure = not (cloud_description or cloud_label) and confidence < UNSURE_BELOW
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
            description = f"This {'might be' if unsure else 'is'} {article} {label}. {explanation}"
        if cloud_product and cloud_description:
            description += cloud_description
        if recognized_text:
            description += f" The visible text reads: {recognized_text}."
        other_labels = [
            other for other in detection.get("all_labels", [])
            if other not in (label, cloud_label)
        ]
        if other_labels:
            description += f" I can also see: {', '.join(other_labels)}."
        self._set_description(description)
        title = (cloud_product or cloud_label or label).title()
        self.object_name.configure(text=f"{title}?" if unsure else title)
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
